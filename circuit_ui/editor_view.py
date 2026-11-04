"""Área de trabajo: escena con cuadrícula, bloques movibles, flechas, zoom y desplazamiento."""
import math
from typing import Optional

from PySide6.QtCore import QLineF, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene, QGraphicsView

from .blocks import BLOCK_SIZE, ArrowItem, BlockItem
from .placement import Point, find_free_position, snap_to_grid

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

    # --- API pública -------------------------------------------------------------
    def add_block(self, kind: str = "circle") -> None:
        """Crea un bloque en una posición libre, preferentemente centrada y visible."""
        x, y = self._choose_position()
        item = BlockItem(kind)
        item.setPos(x, y)
        self._scene.addItem(item)

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
        for arrow in arrows:
            arrow.detach()
            self._scene.removeItem(arrow)
        for block in blocks:
            self._scene.removeItem(block)
        for item in self._scene.items():       # las flechas inversas vuelven a centrarse
            if isinstance(item, ArrowItem):
                item.update_geometry()

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
        super().mousePressEvent(event)

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
            self._cancel_link()
            if target is not None:
                self._connect_blocks(source, target)
            event.accept()
            return
        super().mouseReleaseEvent(event)

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
    def _connect_blocks(self, source: BlockItem, target: BlockItem) -> None:
        if source is target:
            return
        if any(a.source is source and a.target is target for a in source.arrows):
            return   # ya existe esa conexión
        self._scene.addItem(ArrowItem(source, target))

    def _block_centers(self) -> list[Point]:
        return [(i.pos().x(), i.pos().y()) for i in self._scene.items() if isinstance(i, BlockItem)]

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
