"""Elemento gráfico que representa un componente colocado en el área de trabajo."""
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem

CIRCLE_DIAMETER = 40.0  # px en escala 1:1 (rango pedido: 30-40)
OUTLINE_WIDTH = 1.5


class CircleItem(QGraphicsEllipseItem):
    """Círculo centrado en su propia posición (setPos = centro), contorno negro fino."""

    def __init__(self) -> None:
        radius = CIRCLE_DIAMETER / 2
        super().__init__(-radius, -radius, CIRCLE_DIAMETER, CIRCLE_DIAMETER)
        pen = QPen(QColor("#000000"))
        pen.setWidthF(OUTLINE_WIDTH)
        self.setPen(pen)
        self.setBrush(QBrush(QColor("#FFFFFF")))
        self.setZValue(1)  # siempre por encima de la cuadrícula
