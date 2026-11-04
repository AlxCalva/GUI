"""Barra lateral vertical: componentes (PNG), operaciones y modo de conexión."""
from PySide6.QtCore import QPointF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QFrame, QToolButton, QVBoxLayout

from .assets import COMPONENT_ICON_FILES, load_pixmap
from .blocks import BLOCK_SPECS, OPERATION_KINDS, make_block_icon

SIDEBAR_WIDTH = 74
BUTTON_SIZE = QSize(50, 40)
ICON_SIZE = QSize(30, 30)
BUTTON_SPACING = 3
GROUP_SPACING = 12


def _make_arrow_icon(size: int = 60) -> QIcon:
    """Icono de 'conectar bloques': una flecha diagonal."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor("#000000"))
    pen.setWidthF(3)
    p.setPen(pen)
    p.setBrush(QBrush(QColor("#000000")))
    p.drawLine(QPointF(8, size - 8), QPointF(size - 20, 20))
    p.drawPolygon(QPolygonF([QPointF(size - 6, 6), QPointF(size - 28, 12), QPointF(size - 12, 28)]))
    p.end()
    return QIcon(pixmap)


class ComponentSidebar(QFrame):
    """Emite `component_requested(clave)` al pulsar un componente u operación
    y `connect_mode_toggled(bool)` al activar/desactivar el modo flecha."""

    component_requested = Signal(str)
    connect_mode_toggled = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins((SIDEBAR_WIDTH - BUTTON_SIZE.width()) // 2, 10, 0, 10)
        self._layout.setSpacing(BUTTON_SPACING)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        for index, file_name in enumerate(COMPONENT_ICON_FILES, start=1):
            key = f"component_{index}"
            icon = QIcon(load_pixmap(file_name))  # lanza AssetLoadError si falla
            button = self._add_button(icon, key, f"Component {index}")
            button.clicked.connect(lambda _c=False, k=key: self.component_requested.emit(k))

        self._layout.addSpacing(GROUP_SPACING)
        for kind in OPERATION_KINDS:
            key = f"op_{kind}"
            button = self._add_button(make_block_icon(kind), key, BLOCK_SPECS[kind].title)
            button.clicked.connect(lambda _c=False, k=key: self.component_requested.emit(k))

        self._layout.addSpacing(GROUP_SPACING)
        self._connect_button = self._add_button(
            _make_arrow_icon(), "connect_mode", "Connect blocks: drag from one block to another (Esc to exit)"
        )
        self._connect_button.setCheckable(True)
        self._connect_button.toggled.connect(self.connect_mode_toggled.emit)

    def _add_button(self, icon: QIcon, key: str, tooltip: str) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("ComponentButton")
        button.setAccessibleName(key)
        button.setToolTip(tooltip)
        button.setIcon(icon)
        button.setIconSize(ICON_SIZE)
        button.setFixedSize(BUTTON_SIZE)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._layout.addWidget(button)
        return button

    def set_connect_checked(self, checked: bool) -> None:
        """Sincroniza el botón cuando el modo se cambia desde fuera (p. ej. con Esc)."""
        if self._connect_button.isChecked() != checked:
            self._connect_button.setChecked(checked)
