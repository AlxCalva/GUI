"""Barra lateral vertical con los dos botones de componentes."""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QToolButton, QVBoxLayout

from .assets import COMPONENT_ICON_FILES, load_pixmap

SIDEBAR_WIDTH = 74
BUTTON_SIZE = QSize(50, 40)
ICON_SIZE = QSize(30, 30)   # iconos cuadrados (50x50 originales): se conserva la proporción
BUTTON_SPACING = 3


class ComponentSidebar(QFrame):
    """Emite `component_requested(clave)` al pulsar cualquiera de sus botones."""

    component_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)  # no cambia al redimensionar la ventana

        layout = QVBoxLayout(self)
        layout.setContentsMargins((SIDEBAR_WIDTH - BUTTON_SIZE.width()) // 2, 10, 0, 10)
        layout.setSpacing(BUTTON_SPACING)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        for index, file_name in enumerate(COMPONENT_ICON_FILES, start=1):
            key = f"component_{index}"
            button = QToolButton(self)
            button.setObjectName("ComponentButton")
            button.setAccessibleName(key)
            button.setIcon(QIcon(load_pixmap(file_name)))  # lanza AssetLoadError si falla
            button.setIconSize(ICON_SIZE)
            button.setFixedSize(BUTTON_SIZE)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, k=key: self.component_requested.emit(k))
            layout.addWidget(button)
