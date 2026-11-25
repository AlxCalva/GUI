"""Bloques y flechas del diagrama (Qt gráfico; las reglas y el cálculo viven en signal_graph)."""
import math
from typing import Callable, NamedTuple

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetricsF, QIcon, QPainter, QPainterPath, QPainterPathStroker,
    QPen, QPixmap, QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsPathItem, QGraphicsRectItem, QStyle, QStyleOptionGraphicsItem,
)

from .signal_graph import default_params, default_value, wave_formula

BLOCK_SIZE = 40.0            # diámetro / lado / altura en escala 1:1
OUTLINE_WIDTH = 1.5
COLOR_NORMAL = QColor("#000000")
COLOR_SELECTED = QColor("#2F6FDE")


# --- Formas ------------------------------------------------------------------------
def _circle() -> QPolygonF:
    r = BLOCK_SIZE / 2
    return QPolygonF([QPointF(r * math.cos(2 * math.pi * i / 64), r * math.sin(2 * math.pi * i / 64))
                      for i in range(64)])


def _square() -> QPolygonF:
    h = BLOCK_SIZE / 2
    return QPolygonF([QPointF(-h, -h), QPointF(h, -h), QPointF(h, h), QPointF(-h, h)])


def _rectangle() -> QPolygonF:  # integrador digital: 60 x 40
    return QPolygonF([QPointF(-30, -20), QPointF(30, -20), QPointF(30, 20), QPointF(-30, 20)])


def _triangle() -> QPolygonF:  # apunta a la derecha (símbolo de ganancia / multiplicación)
    return QPolygonF([QPointF(-15, -20), QPointF(-15, 20), QPointF(25, 0)])


Polyline = list[tuple[float, float]]


def _plus() -> list[Polyline]:
    return [[(-9, 0), (9, 0)], [(0, -9), (0, 9)]]


def _asterisk() -> list[Polyline]:
    out = []
    for deg in (90, 30, 150):
        a = math.radians(deg)
        out.append([(-9 * math.cos(a), 9 * math.sin(a)), (9 * math.cos(a), -9 * math.sin(a))])
    return out


def _wave(is_sin: bool) -> list[Polyline]:
    """Un periodo de seno (empieza en 0) o de coseno (empieza en el máximo) dentro del círculo."""
    steps = 32
    pts = []
    for i in range(steps + 1):
        u = i / steps
        y = -8 * (math.sin(2 * math.pi * u) if is_sin else math.cos(2 * math.pi * u))
        pts.append((-12 + 24 * u, y))
    return [pts]


class BlockSpec(NamedTuple):
    title: str
    polygon: Callable[[], QPolygonF]
    symbol: Callable[[], list[Polyline]]


BLOCK_SPECS = {
    "circle": BlockSpec("Constant signal", _circle, lambda: []),
    "sin": BlockSpec("Sine function", _circle, lambda: _wave(True)),
    "cos": BlockSpec("Cosine function", _circle, lambda: _wave(False)),
    "gain": BlockSpec("Gain (multiplication)", _triangle, lambda: []),
    "sum": BlockSpec("Sum", _circle, _plus),
    "convolution": BlockSpec("Convolution", _square, _asterisk),
    "integrator": BlockSpec("Digital integrator  z\u207b\u00b9 / (1 \u2212 z\u207b\u00b9)", _rectangle, lambda: []),
}
WAVE_KINDS = ("sin", "cos")
OPERATION_KINDS = ("gain", "sum", "convolution")


def _block_path(kind: str) -> tuple[QPainterPath, QPolygonF]:
    spec = BLOCK_SPECS[kind]
    polygon = spec.polygon()
    path = QPainterPath()
    path.addPolygon(polygon)
    path.closeSubpath()
    for polyline in spec.symbol():
        path.moveTo(*polyline[0])
        for x, y in polyline[1:]:
            path.lineTo(x, y)
    return path, polygon


def make_block_icon(kind: str, size: int = 60) -> QIcon:
    """Icono de botón dibujado con la misma forma que el bloque."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(size / 2, size / 2)
    scale = size * 0.85 / BLOCK_SIZE
    painter.scale(scale, scale)
    pen = QPen(COLOR_NORMAL)
    pen.setWidthF(OUTLINE_WIDTH * 1.6)
    painter.setPen(pen)
    painter.setBrush(QBrush(QColor("#FFFFFF")))
    painter.drawPath(_block_path(kind)[0])
    painter.end()
    return QIcon(pixmap)


def _no_selection(option: QStyleOptionGraphicsItem) -> QStyleOptionGraphicsItem:
    """Quita el rectángulo punteado de selección de Qt (usamos el color en su lugar)."""
    clean = QStyleOptionGraphicsItem(option)
    clean.state &= ~QStyle.StateFlag.State_Selected
    return clean


def _cross(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def _draw_runs(painter: QPainter, base: QFont, runs: list, cx: float, baseline: float, size: int) -> None:
    """Dibuja texto con exponentes sin depender de que la fuente tenga los caracteres ⁻¹.
    `runs` = [(texto, es_exponente)]; el conjunto queda centrado en `cx`."""
    big, small = QFont(base), QFont(base)
    big.setPixelSize(size)
    small.setPixelSize(max(6, int(size * 0.65)))
    widths = [QFontMetricsF(small if sup else big).horizontalAdvance(text) for text, sup in runs]
    x = cx - sum(widths) / 2
    for (text, sup), width in zip(runs, widths):
        painter.setFont(small if sup else big)
        painter.drawText(QPointF(x, baseline - (size * 0.4 if sup else 0.0)), text)
        x += width


# --- Bloque ------------------------------------------------------------------------
class BlockItem(QGraphicsPathItem):
    """Bloque movible y seleccionable; setPos = centro del bloque."""

    def __init__(self, kind: str = "circle") -> None:
        super().__init__()
        self.kind = kind
        path, self._outline = _block_path(kind)
        self.setPath(path)
        self.setBrush(QBrush(QColor("#FFFFFF")))
        self._apply_pen(False)
        self.setZValue(1)  # por encima de la cuadrícula y de las flechas
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.arrows: list["ArrowItem"] = []
        self.name = ""
        self.value = default_value(kind)     # entero (constante / factor) o None
        self.params = default_params(kind)   # dict (seno / coseno) o None

    def set_name(self, name: str) -> None:
        self.name = name
        self._refresh_tooltip()

    def set_value(self, value: int) -> None:
        self.value = value
        self.update()

    def set_params(self, params: dict) -> None:
        self.params = dict(params)
        self._refresh_tooltip()
        self.update()

    def _refresh_tooltip(self) -> None:
        lines = [self.name]
        if self.params is not None:
            lines.append(wave_formula(self.kind, self.params))
        elif self.kind == "integrator":
            lines.append("y[n] = y[n\u22121] + x[n\u22121]")
        elif self.kind == "convolution":
            lines.append("y[n] = \u03a3 x\u2081[k]\u00b7x\u2082[n\u2212k]")
        self.setToolTip("\n".join(lines))

    def _apply_pen(self, selected: bool) -> None:
        pen = QPen(COLOR_SELECTED if selected else COLOR_NORMAL)
        pen.setWidthF(OUTLINE_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setPen(pen)

    def boundary_point(self, towards: QPointF) -> QPointF:
        """Punto del contorno donde el rayo centro→`towards` sale del bloque."""
        center = self.scenePos()
        dx, dy = towards.x() - center.x(), towards.y() - center.y()
        length = math.hypot(dx, dy)
        if length < 1e-9:
            return center
        dx, dy = dx / length, dy / length
        pts = list(self._outline)
        best = None
        for i, p1 in enumerate(pts):
            p2 = pts[(i + 1) % len(pts)]
            ex, ey = p2.x() - p1.x(), p2.y() - p1.y()
            denom = _cross(dx, dy, ex, ey)
            if abs(denom) < 1e-9:
                continue
            t = _cross(p1.x(), p1.y(), ex, ey) / denom
            u = _cross(p1.x(), p1.y(), dx, dy) / denom
            if t > 0 and -1e-9 <= u <= 1 + 1e-9 and (best is None or t < best):
                best = t
        best = best if best is not None else BLOCK_SIZE / 2
        return QPointF(center.x() + dx * best, center.y() + dy * best)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene() is not None:
            scene = self.scene()
            size = getattr(scene, "grid_size", 0)
            x, y = value.x(), value.y()
            rect = scene.sceneRect()
            margin = BLOCK_SIZE / 2
            x = min(max(x, rect.left() + margin), rect.right() - margin)
            y = min(max(y, rect.top() + margin), rect.bottom() - margin)
            if size:
                x, y = round(x / size) * size, round(y / size) * size
            return QPointF(x, y)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for arrow in self.arrows:
                arrow.update_geometry()
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._apply_pen(bool(value))
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None) -> None:
        super().paint(painter, _no_selection(option), widget)
        painter.save()
        painter.setPen(self.pen().color())
        font = painter.font()
        font.setBold(True)
        if self.kind == "integrator":   # fracción z⁻¹ / (1 − z⁻¹)
            _draw_runs(painter, font, [("z", False), ("\u22121", True)], 0, -4, 12)
            painter.drawLine(QLineF(-22, 1, 22, 1))
            _draw_runs(painter, font, [("1 \u2212 z", False), ("\u22121", True)], 0, 14, 12)
        elif self.value is not None:
            if self.kind == "gain":   # el triángulo apunta a la derecha: el texto va en su parte ancha
                font.setPixelSize(8)
                rect, text = QRectF(-15, -10, 20, 20), f"\u00d7{self.value}"
            else:
                font.setPixelSize(13)
                half = BLOCK_SIZE / 2
                rect, text = QRectF(-half, -half, BLOCK_SIZE, BLOCK_SIZE), str(self.value)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


# --- Articulaciones de las flechas -------------------------------------------------
class WaypointHandle(QGraphicsRectItem):
    """Cuadradito arrastrable en cada articulación de una flecha seleccionada."""

    SIZE = 8.0

    def __init__(self, arrow: "ArrowItem") -> None:
        h = self.SIZE / 2
        super().__init__(-h, -h, self.SIZE, self.SIZE, arrow)
        self.arrow = arrow
        self.setBrush(QBrush(COLOR_SELECTED))
        self.setPen(QPen(QColor("#FFFFFF"), 1))
        self.setZValue(3)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
            | QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations  # tamaño fijo con el zoom
        )

    def itemChange(self, change, value):
        if not self.arrow.syncing:
            if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene() is not None:
                size = getattr(self.scene(), "grid_size", 0)
                if size:
                    return QPointF(round(value.x() / size) * size, round(value.y() / size) * size)
            elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
                self.arrow.handle_moved(self)
        return super().itemChange(change, value)


def _distance_to_segment(p: QPointF, a: QPointF, b: QPointF) -> float:
    abx, aby = b.x() - a.x(), b.y() - a.y()
    length2 = abx * abx + aby * aby
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p.x() - a.x()) * abx + (p.y() - a.y()) * aby) / length2))
    return math.hypot(p.x() - (a.x() + t * abx), p.y() - (a.y() + t * aby))


# --- Flecha ------------------------------------------------------------------------
class ArrowItem(QGraphicsPathItem):
    """Flecha unidireccional (salida de `source` → entrada de `target`) con articulaciones
    opcionales (`waypoints`, en coordenadas de escena) para dibujar lazos."""

    HEAD_LENGTH = 11.0
    HEAD_HALF_WIDTH = 5.0
    PARALLEL_OFFSET = 5.0   # separación si existen flechas rectas en ambos sentidos
    HIT_WIDTH = 10.0        # zona clicable alrededor de la línea

    def __init__(self, source: BlockItem, target: BlockItem, waypoints=None) -> None:
        super().__init__()
        self.source, self.target = source, target
        self.waypoints: list[QPointF] = [QPointF(p) for p in (waypoints or [])]
        self.syncing = False                    # True mientras se recolocan los tiradores
        self._handles: list[WaypointHandle] = []
        self._polyline: list[QPointF] = []
        self.setZValue(0.5)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._apply_style(False)
        self._rebuild_handles()
        # El registro en los bloques se hace en attach() (lo llaman los comandos de deshacer).

    def _apply_style(self, selected: bool) -> None:
        color = COLOR_SELECTED if selected else COLOR_NORMAL
        pen = QPen(color)
        pen.setWidthF(OUTLINE_WIDTH)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setPen(pen)
        self.setBrush(QBrush(color))

    # --- Articulaciones ---
    def set_waypoints(self, points) -> None:
        self.waypoints = [QPointF(p) for p in points]
        self._rebuild_handles()
        self.update_geometry()

    def _rebuild_handles(self) -> None:
        for handle in self._handles:
            handle.setParentItem(None)
            if handle.scene() is not None:
                handle.scene().removeItem(handle)
        self._handles = []
        for _ in self.waypoints:
            handle = WaypointHandle(self)
            handle.setVisible(self.isSelected())
            self._handles.append(handle)

    def _sync_handles(self) -> None:
        self.syncing = True
        for handle, point in zip(self._handles, self.waypoints):
            if handle.pos() != point:
                handle.setPos(point)
        self.syncing = False

    def handle_index(self, handle: WaypointHandle) -> int:
        return next(i for i, h in enumerate(self._handles) if h is handle)

    def handle_moved(self, handle: WaypointHandle) -> None:
        self.waypoints[self.handle_index(handle)] = QPointF(handle.pos())
        self.update_geometry()

    def insertion_index(self, scene_point: QPointF) -> int:
        """Posición de la lista de articulaciones donde insertar un punto nuevo en `scene_point`."""
        poly = self._polyline
        if len(poly) < 2:
            return len(self.waypoints)
        distances = [_distance_to_segment(scene_point, poly[i], poly[i + 1]) for i in range(len(poly) - 1)]
        return distances.index(min(distances))

    # --- Registro en los bloques ---
    def attach(self) -> None:
        """Registra la flecha en sus dos bloques y recoloca las flechas afectadas."""
        for block in (self.source, self.target):
            if self not in block.arrows:
                block.arrows.append(self)
        for arrow in list(self.source.arrows):  # incluye la inversa, para separarlas
            arrow.update_geometry()

    def detach(self) -> None:
        for block in (self.source, self.target):
            if self in block.arrows:
                block.arrows.remove(self)

    def _has_reverse(self) -> bool:
        return any(o.source is self.target and o.target is self.source and not o.waypoints
                   for o in self.source.arrows)

    # --- Geometría ---
    def update_geometry(self) -> None:
        a, b = self.source.scenePos(), self.target.scenePos()
        wps = self.waypoints
        path = QPainterPath()
        poly: list[QPointF] = []
        if wps or math.hypot(b.x() - a.x(), b.y() - a.y()) > 1e-6:
            shift = QPointF(0.0, 0.0)
            if not wps and self._has_reverse():
                dist = math.hypot(b.x() - a.x(), b.y() - a.y())
                shift = QPointF(-(b.y() - a.y()) / dist * self.PARALLEL_OFFSET,
                                (b.x() - a.x()) / dist * self.PARALLEL_OFFSET)
            start = self.source.boundary_point(wps[0] if wps else b) + shift
            tip = self.target.boundary_point(wps[-1] if wps else a) + shift
            poly = [start, *wps, tip]
            last_dx, last_dy = tip.x() - poly[-2].x(), tip.y() - poly[-2].y()
            last_len = math.hypot(last_dx, last_dy)
            total = math.hypot(tip.x() - start.x(), tip.y() - start.y())
            if last_len > 1e-6 and (wps or total > self.HEAD_LENGTH + 2):  # bloques pegados: sin flecha
                ux, uy = last_dx / last_len, last_dy / last_len
                nx, ny = -uy, ux
                head = min(self.HEAD_LENGTH, last_len)
                base = QPointF(tip.x() - ux * head, tip.y() - uy * head)
                hw = self.HEAD_HALF_WIDTH
                path.moveTo(poly[0])
                for point in poly[1:-1]:
                    path.lineTo(point)
                path.lineTo(base)
                path.moveTo(tip)
                path.lineTo(QPointF(base.x() + nx * hw, base.y() + ny * hw))
                path.lineTo(QPointF(base.x() - nx * hw, base.y() - ny * hw))
                path.closeSubpath()
            else:
                poly = []
        self._polyline = poly
        self.prepareGeometryChange()
        self.setPath(path)
        self._sync_handles()

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(self.HIT_WIDTH)
        return stroker.createStroke(self.path()).united(self.path())

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._apply_style(bool(value))
            for handle in self._handles:
                handle.setVisible(bool(value))
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None) -> None:
        super().paint(painter, _no_selection(option), widget)
