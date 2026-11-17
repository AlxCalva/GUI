"""Bloques y flechas del diagrama (Qt gráfico; las reglas y el cálculo viven en signal_graph)."""
import math
from typing import Callable, NamedTuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QIcon, QPainter, QPainterPath, QPainterPathStroker, QPen, QPixmap, QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsPathItem, QStyle, QStyleOptionGraphicsItem,
)

from .signal_graph import default_value

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


def _triangle() -> QPolygonF:  # apunta a la derecha (símbolo de ganancia / multiplicación)
    return QPolygonF([QPointF(-15, -20), QPointF(-15, 20), QPointF(25, 0)])


Line = tuple[float, float, float, float]


def _plus() -> list[Line]:
    return [(-9, 0, 9, 0), (0, -9, 0, 9)]


def _asterisk() -> list[Line]:
    out = []
    for deg in (90, 30, 150):
        a = math.radians(deg)
        out.append((-9 * math.cos(a), 9 * math.sin(a), 9 * math.cos(a), -9 * math.sin(a)))
    return out


class BlockSpec(NamedTuple):
    title: str
    polygon: Callable[[], QPolygonF]
    symbol: Callable[[], list[Line]]


BLOCK_SPECS = {
    "circle": BlockSpec("Component", _circle, lambda: []),
    "gain": BlockSpec("Gain (multiplication)", _triangle, lambda: []),
    "sum": BlockSpec("Sum", _circle, _plus),
    "convolution": BlockSpec("Convolution", _square, _asterisk),
}
OPERATION_KINDS = ("gain", "sum", "convolution")


def _block_path(kind: str) -> tuple[QPainterPath, QPolygonF]:
    spec = BLOCK_SPECS[kind]
    polygon = spec.polygon()
    path = QPainterPath()
    path.addPolygon(polygon)
    path.closeSubpath()
    for x1, y1, x2, y2 in spec.symbol():
        path.moveTo(x1, y1)
        path.lineTo(x2, y2)
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
        self.name = ""                       # «Señal 1», «Multiplicación 2»… (lo asigna el editor)
        self.value = default_value(kind)     # None si el bloque no tiene valor configurable

    def set_name(self, name: str) -> None:
        self.name = name
        self.setToolTip(name)

    def set_value(self, value: int) -> None:
        self.value = value
        self.update()

    def _apply_pen(self, selected: bool) -> None:
        pen = QPen(COLOR_SELECTED if selected else COLOR_NORMAL)
        pen.setWidthF(OUTLINE_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
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
        if self.value is None:
            return
        painter.save()
        font = painter.font()
        font.setBold(True)
        if self.kind == "gain":   # el triángulo apunta a la derecha: el texto va en su parte ancha
            font.setPixelSize(8)
            rect, text = QRectF(-15, -10, 20, 20), f"\u00d7{self.value}"
        else:
            font.setPixelSize(13)
            half = BLOCK_SIZE / 2
            rect, text = QRectF(-half, -half, BLOCK_SIZE, BLOCK_SIZE), str(self.value)
        painter.setFont(font)
        painter.setPen(self.pen().color())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


# --- Flecha ------------------------------------------------------------------------
class ArrowItem(QGraphicsPathItem):
    """Flecha unidireccional: la salida de `source` es la entrada de `target`."""

    HEAD_LENGTH = 11.0
    HEAD_HALF_WIDTH = 5.0
    PARALLEL_OFFSET = 5.0   # separación si existen flechas en ambos sentidos
    HIT_WIDTH = 10.0        # zona clicable alrededor de la línea

    def __init__(self, source: BlockItem, target: BlockItem) -> None:
        super().__init__()
        self.source, self.target = source, target
        self.setZValue(0.5)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._apply_style(False)
        # El registro en los bloques se hace en attach() (lo llaman los comandos de deshacer).

    def _apply_style(self, selected: bool) -> None:
        color = COLOR_SELECTED if selected else COLOR_NORMAL
        pen = QPen(color)
        pen.setWidthF(OUTLINE_WIDTH)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        self.setPen(pen)
        self.setBrush(QBrush(color))

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
        return any(o.source is self.target and o.target is self.source for o in self.source.arrows)

    def update_geometry(self) -> None:
        a, b = self.source.scenePos(), self.target.scenePos()
        path = QPainterPath()
        dist = math.hypot(b.x() - a.x(), b.y() - a.y())
        if dist > 1e-6:
            ux, uy = (b.x() - a.x()) / dist, (b.y() - a.y()) / dist
            nx, ny = -uy, ux
            off = self.PARALLEL_OFFSET if self._has_reverse() else 0.0
            shift = QPointF(nx * off, ny * off)
            start = self.source.boundary_point(b) + shift
            tip = self.target.boundary_point(a) + shift
            length = math.hypot(tip.x() - start.x(), tip.y() - start.y())
            if length > self.HEAD_LENGTH + 2:  # si los bloques se tocan, no se dibuja
                base = QPointF(tip.x() - ux * self.HEAD_LENGTH, tip.y() - uy * self.HEAD_LENGTH)
                hw = self.HEAD_HALF_WIDTH
                path.moveTo(start)
                path.lineTo(base)
                path.moveTo(tip)
                path.lineTo(QPointF(base.x() + nx * hw, base.y() + ny * hw))
                path.lineTo(QPointF(base.x() - nx * hw, base.y() - ny * hw))
                path.closeSubpath()
        self.prepareGeometryChange()
        self.setPath(path)

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(self.HIT_WIDTH)
        return stroker.createStroke(self.path()).united(self.path())

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._apply_style(bool(value))
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None) -> None:
        super().paint(painter, _no_selection(option), widget)
