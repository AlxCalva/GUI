"""Área de trabajo: escena con cuadrícula, bloques movibles, flechas, zoom, desplazamiento,
edición de valores (doble clic) y deshacer (QUndoStack)."""
import math
from typing import Optional

from PySide6.QtCore import QLineF, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QUndoStack
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene, QGraphicsView, QMessageBox

from .blocks import BLOCK_SIZE, ArrowItem, BlockItem, WaypointHandle
from .commands import (
    AddArrowCommand, AddBlockCommand, MoveBlocksCommand, RemoveItemsCommand, SetParamsCommand,
    SetValueCommand, SetWaypointsCommand,
)
from .dialogs import ask_value, ask_wave_params
from .placement import Point, find_free_position, snap_to_grid
from .signal_graph import (
    RULES, MAX_VALUE, Edge, Node, has_params, has_value, validate_connection,
)

GRID_SIZE = 20                       # px entre líneas (unidades de escena)
GRID_COLOR = QColor("#DEDEDE")
SCENE_WIDTH = 4000
SCENE_HEIGHT = 3000

SLOT_SPACING = 3 * GRID_SIZE         # separación entre centros candidatos (60 px)
MIN_CENTER_DISTANCE = SLOT_SPACING
VISIBLE_MARGIN = 8

ZOOM_MIN = 0.25
ZOOM_MAX = 4.0
ZOOM_SPEED = 1.0015                  # factor por unidad de angleDelta (120 ≈ x1.2)


class GridScene(QGraphicsScene):
    """Dibuja la cuadrícula en drawBackground, en coordenadas de escena."""

    def __init__(self, parent=None) -> None:
        super().__init__(0, 0, SCENE_WIDTH, SCENE_HEIGHT, parent)
        self.grid_size = GRID_SIZE   # los bloques lo leen para ajustarse a la malla
        self.setBackgroundBrush(QColor("#FFFFFF"))

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, self.backgroundBrush())

        first_x = math.floor(rect.left() / GRID_SIZE) * GRID_SIZE
        first_y = math.floor(rect.top() / GRID_SIZE) * GRID_SIZE

        lines: list[QLineF] = []
        x = first_x
        while x <= rect.right():
            lines.append(QLineF(x, rect.top(), x, rect.bottom()))
            x += GRID_SIZE
        y = first_y
        while y <= rect.bottom():
            lines.append(QLineF(rect.left(), y, rect.right(), y))
            y += GRID_SIZE

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(GRID_COLOR, 0))
        painter.drawLines(lines)
        painter.restore()


class EditorView(QGraphicsView):
    connect_mode_changed = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = GridScene(self)
        self.setScene(self._scene)
        self.setObjectName("Workspace")
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)   # selección múltiple
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self._zoom = 1.0
        self._panning = False
        self._pan_last = QPoint()
        self._connect_mode = False
        self._link_source: Optional[BlockItem] = None
        self._preview: Optional[QGraphicsLineItem] = None
        self._press_positions: dict[BlockItem, QPointF] = {}   # para detectar movimientos
        self._handle_drag = None   # (flecha, articulaciones_antes) mientras se arrastra un tirador

        self.undo_stack = QUndoStack(self)   # Ctrl+Z lo conecta MainWindow

    # --- API pública -------------------------------------------------------------
    def add_block(self, kind: str = "circle") -> None:
        """Crea un bloque en una posición libre, preferentemente centrada y visible."""
        x, y = self._choose_position()
        item = BlockItem(kind)
        item.set_name(self._next_name(kind))
        item.setPos(x, y)
        self.undo_stack.push(AddBlockCommand(self._scene, item))   # push ejecuta redo() = addItem

    def add_circle(self) -> None:
        self.add_block("circle")

    def set_connect_mode(self, enabled: bool) -> None:
        if enabled == self._connect_mode:
            return
        self._connect_mode = enabled
        self._cancel_link()
        if enabled:
            self._scene.clearSelection()
        self._apply_cursor()
        self.connect_mode_changed.emit(enabled)

    def reset_zoom(self) -> None:
        self.resetTransform()
        self._zoom = 1.0

    def delete_selected(self) -> None:
        selected = self._scene.selectedItems()
        arrows = {i for i in selected if isinstance(i, ArrowItem)}
        blocks = [i for i in selected if isinstance(i, BlockItem)]
        for block in blocks:
            arrows.update(block.arrows)
        if blocks or arrows:
            self.undo_stack.push(RemoveItemsCommand(self._scene, blocks, list(arrows)))

    def build_graph(self) -> tuple[dict[int, Node], list[Edge]]:
        """Foto del diagrama (sin Qt) para validar y ejecutar."""
        nodes, edges, _ids = self._snapshot()
        return nodes, edges

    # --- Ratón / teclado ---------------------------------------------------------
    def _apply_cursor(self) -> None:
        if self._panning:
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        elif self._connect_mode:
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.viewport().unsetCursor()

    def _block_at(self, pos: QPoint) -> Optional[BlockItem]:
        for item in self.items(pos):
            if isinstance(item, BlockItem):
                return item
        return None

    def _cancel_link(self) -> None:
        if self._preview is not None:
            self._scene.removeItem(self._preview)
        self._preview = None
        self._link_source = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_last = event.position().toPoint()
            self._apply_cursor()
            event.accept()
            return
        if self._connect_mode and event.button() == Qt.MouseButton.LeftButton:
            block = self._block_at(event.position().toPoint())
            if block is not None:
                self._link_source = block
                pen = QPen(QColor("#2F6FDE"), 1.5, Qt.PenStyle.DashLine)
                self._preview = QGraphicsLineItem(QLineF(block.scenePos(), block.scenePos()))
                self._preview.setPen(pen)
                self._preview.setZValue(2)
                self._scene.addItem(self._preview)
            event.accept()   # en modo conexión no se mueve ni se selecciona nada
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_positions = {b: b.pos() for b in self._blocks()}
            top = self._top_item_at(event.position().toPoint())
            self._handle_drag = ((top.arrow, [QPointF(p) for p in top.arrow.waypoints])
                                 if isinstance(top, WaypointHandle) else None)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """Doble clic: en un bloque edita sus valores; en una flecha añade una articulación;
        en una articulación la elimina."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._connect_mode:
                event.accept()   # en modo conexión el doble clic no hace nada
                return
            pos = event.position().toPoint()
            item = self._top_item_at(pos)
            if isinstance(item, WaypointHandle):
                self._remove_waypoint(item)
            elif isinstance(item, BlockItem):
                if has_value(item.kind) or has_params(item.kind):
                    self._edit_block_value(item)
            elif isinstance(item, ArrowItem):
                self._add_waypoint(item, self.mapToScene(pos))
            else:
                super().mouseDoubleClickEvent(event)
                return
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._panning:
            pos = event.position().toPoint()
            delta = pos - self._pan_last
            self._pan_last = pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        if self._link_source is not None and self._preview is not None:
            end = self.mapToScene(event.position().toPoint())
            self._preview.setLine(QLineF(self._link_source.scenePos(), end))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._panning and event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self._apply_cursor()
            event.accept()
            return
        if self._link_source is not None and event.button() == Qt.MouseButton.LeftButton:
            source = self._link_source
            target = self._block_at(event.position().toPoint())
            if target is None or target is source:
                self._cancel_link()   # soltó en vacío (o fue un clic): el modo sigue activo
            else:
                # El modo flecha es de un solo uso: se desactiva al intentar conectar
                # (haya o no flecha), y también desmarca el botón de la barra lateral.
                self.set_connect_mode(False)
                self._connect_blocks(source, target)
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self._commit_moves()
        self._commit_handle_drag()

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        new_zoom = min(ZOOM_MAX, max(ZOOM_MIN, self._zoom * ZOOM_SPEED ** delta))
        factor = new_zoom / self._zoom
        if abs(factor - 1.0) > 1e-9:
            self.scale(factor, factor)   # el ancla bajo el ratón mantiene el punto fijo
            self._zoom = new_zoom
        event.accept()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.set_connect_mode(False)
        elif key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
        elif key == Qt.Key.Key_0 and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.reset_zoom()
        else:
            super().keyPressEvent(event)

    # --- Internos ----------------------------------------------------------------
    def _blocks(self) -> list[BlockItem]:
        return [i for i in self._scene.items() if isinstance(i, BlockItem)]

    def _snapshot(self) -> tuple[dict[int, Node], list[Edge], dict[BlockItem, int]]:
        blocks = sorted(self._blocks(), key=lambda b: (b.kind, b.name))
        ids = {block: index for index, block in enumerate(blocks)}
        nodes = {ids[b]: Node(b.kind, b.name, b.value, b.params) for b in blocks}
        edges = [(ids[a.source], ids[a.target]) for a in self._scene.items()
                 if isinstance(a, ArrowItem) and a.source in ids and a.target in ids]
        return nodes, edges, ids

    def _next_name(self, kind: str) -> str:
        base = RULES[kind].name
        numbers = [int(b.name.rsplit(" ", 1)[-1]) for b in self._blocks()
                   if b.kind == kind and b.name.rsplit(" ", 1)[-1].isdigit()]
        return f"{base} {max(numbers, default=0) + 1}"

    def _warn(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def _connect_blocks(self, source: BlockItem, target: BlockItem) -> None:
        nodes, edges, ids = self._snapshot()
        error = validate_connection(nodes, edges, ids[source], ids[target])
        if error is not None:
            self._warn("Conexión no válida", error)
            return

        new_factor = None
        if target.kind == "gain":   # al conectar una señal a un triángulo se elige el factor
            new_factor = ask_value(
                self, "Factor de multiplicación",
                f"Valor por el que «{target.name}» multiplica la señal (0-{MAX_VALUE}):", target.value)
            if new_factor is None:
                return   # canceló: no se crea la flecha

        arrow = ArrowItem(source, target)
        self.undo_stack.beginMacro("Conectar bloques")   # un solo Ctrl+Z deshace factor + flecha
        if new_factor is not None and new_factor != target.value:
            self.undo_stack.push(SetValueCommand(target, target.value, new_factor))
        self.undo_stack.push(AddArrowCommand(self._scene, arrow))
        self.undo_stack.endMacro()

    def _edit_block_value(self, block: BlockItem) -> None:
        if block.params is not None:   # seno / coseno
            params = ask_wave_params(self, block.kind, block.name, block.params)
            if params is not None and params != block.params:
                self.undo_stack.push(SetParamsCommand(block, block.params, params))
            return
        if block.kind == "circle":
            title, prompt = "Señal de entrada", f"Valor de «{block.name}» (0-{MAX_VALUE}):"
        else:
            title, prompt = "Factor de multiplicación", f"Factor de «{block.name}» (0-{MAX_VALUE}):"
        value = ask_value(self, title, prompt, block.value)
        if value is not None and value != block.value:
            self.undo_stack.push(SetValueCommand(block, block.value, value))

    def _top_item_at(self, pos: QPoint):
        for item in self.items(pos):
            if isinstance(item, (WaypointHandle, BlockItem, ArrowItem)):
                return item
        return None

    def _add_waypoint(self, arrow: ArrowItem, scene_pos: QPointF) -> None:
        snapped = QPointF(snap_to_grid(scene_pos.x(), GRID_SIZE), snap_to_grid(scene_pos.y(), GRID_SIZE))
        index = arrow.insertion_index(scene_pos)
        old = [QPointF(p) for p in arrow.waypoints]
        self.undo_stack.push(SetWaypointsCommand(arrow, old, old[:index] + [snapped] + old[index:]))

    def _remove_waypoint(self, handle: WaypointHandle) -> None:
        arrow = handle.arrow
        index = arrow.handle_index(handle)
        old = [QPointF(p) for p in arrow.waypoints]
        self.undo_stack.push(SetWaypointsCommand(arrow, old, old[:index] + old[index + 1:]))

    def _commit_handle_drag(self) -> None:
        """Si se arrastró un tirador, lo registra como una sola acción deshacible."""
        if self._handle_drag is None:
            return
        arrow, old = self._handle_drag
        self._handle_drag = None
        new = [QPointF(p) for p in arrow.waypoints]
        if new != old:
            self.undo_stack.push(SetWaypointsCommand(arrow, old, new))

    def _commit_moves(self) -> None:
        """Si el arrastre movió bloques, lo registra como una sola acción deshacible."""
        moves = [(b, old, b.pos()) for b, old in self._press_positions.items()
                 if b.scene() is self._scene and b.pos() != old]
        self._press_positions = {}
        if moves:
            self.undo_stack.push(MoveBlocksCommand(moves))

    def _block_centers(self) -> list[Point]:
        return [(b.pos().x(), b.pos().y()) for b in self._blocks()]

    def _visible_scene_rect(self) -> QRectF:
        return self.mapToScene(self.viewport().rect()).boundingRect().intersected(self.sceneRect())

    @staticmethod
    def _inset(rect: QRectF, margin: float) -> tuple[float, float, float, float]:
        return (rect.left() + margin, rect.top() + margin, rect.right() - margin, rect.bottom() - margin)

    def _choose_position(self) -> Point:
        visible = self._visible_scene_rect()
        preferred = (visible.center().x(), visible.center().y())
        margin = BLOCK_SIZE / 2 + VISIBLE_MARGIN
        centers = self._block_centers()

        for area in (visible, self.sceneRect()):
            position = find_free_position(
                preferred, self._inset(area, margin), centers,
                GRID_SIZE, SLOT_SPACING, MIN_CENTER_DISTANCE,
            )
            if position is not None:
                return position

        return (snap_to_grid(preferred[0], GRID_SIZE), snap_to_grid(preferred[1], GRID_SIZE))
