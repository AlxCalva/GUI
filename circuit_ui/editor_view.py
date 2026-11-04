"""Área de trabajo: escena con cuadrícula (parte del sistema de coordenadas) y su vista."""
import math

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from .circle_item import CIRCLE_DIAMETER, CircleItem
from .placement import Point, find_free_position, snap_to_grid

GRID_SIZE = 20                       # px entre líneas (unidades de escena)
GRID_COLOR = QColor("#DEDEDE")
SCENE_WIDTH = 4000                   # tamaño fijo y generoso: aparecen barras de
SCENE_HEIGHT = 3000                  # desplazamiento cuando la ventana es menor

SLOT_SPACING = 3 * GRID_SIZE         # separación entre centros candidatos (60 px)
MIN_CENTER_DISTANCE = SLOT_SPACING   # 40 px de círculo + 20 px de hueco visible
VISIBLE_MARGIN = 8                   # aire entre el círculo y el borde visible


class GridScene(QGraphicsScene):
    """Dibuja la cuadrícula en drawBackground, en coordenadas de escena.

    Al no ser una imagen, siempre queda alineada con los elementos y cubre cualquier
    zona expuesta de la vista (incluso fuera del sceneRect).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(0, 0, SCENE_WIDTH, SCENE_HEIGHT, parent)
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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # líneas nítidas de 1 px
        painter.setPen(QPen(GRID_COLOR, 0))                             # ancho 0 = 1 px siempre
        painter.drawLines(lines)
        painter.restore()


class EditorView(QGraphicsView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # La escena se guarda como atributo (y se le da la vista como padre): si solo se
        # pasara inline, Python la recolectaría, Qt la destruiría y scene() devolvería None.
        self._scene = GridScene(self)
        self.setScene(self._scene)
        self.setObjectName("Workspace")
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)  # círculos suaves
        # El origen de la escena queda anclado arriba-izquierda: al redimensionar, la
        # cuadrícula no se desplaza ni se descentra.
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        self._circle_centers: list[Point] = []

    # --- API pública -------------------------------------------------------------
    def add_circle(self) -> None:
        """Crea un círculo nuevo en una posición libre, preferentemente centrada y visible."""
        x, y = self._choose_position()
        item = CircleItem()
        item.setPos(x, y)
        self._scene.addItem(item)
        self._circle_centers.append((x, y))

    # --- Internos ----------------------------------------------------------------
    def _visible_scene_rect(self) -> QRectF:
        return self.mapToScene(self.viewport().rect()).boundingRect().intersected(self.sceneRect())

    @staticmethod
    def _inset(rect: QRectF, margin: float) -> tuple[float, float, float, float]:
        return (rect.left() + margin, rect.top() + margin, rect.right() - margin, rect.bottom() - margin)

    def _choose_position(self) -> Point:
        visible = self._visible_scene_rect()
        preferred = (visible.center().x(), visible.center().y())
        margin = CIRCLE_DIAMETER / 2 + VISIBLE_MARGIN

        # 1.º dentro del área visible; 2.º (si está llena) en la escena, lo más cerca posible.
        for area in (visible, self.sceneRect()):
            position = find_free_position(
                preferred,
                self._inset(area, margin),
                self._circle_centers,
                GRID_SIZE,
                SLOT_SPACING,
                MIN_CENTER_DISTANCE,
            )
            if position is not None:
                return position

        # Escena agotada (~3000 círculos): se crea igualmente, en el centro, aunque se solape.
        return (snap_to_grid(preferred[0], GRID_SIZE), snap_to_grid(preferred[1], GRID_SIZE))