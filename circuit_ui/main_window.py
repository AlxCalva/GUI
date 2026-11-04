"""Ventana principal: menú superior + barra lateral + área de trabajo."""
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

from .editor_view import EditorView
from .sidebar import ComponentSidebar
from .styles import STYLESHEET

MENU_TITLES = ("Project", "Analysis", "View", "Plot")  # sin acciones en esta PoC
PROJECT_TITLE = "New Project"  # etiqueta estática, como en la referencia


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DSSIM - PoC de interfaz")
        self.resize(1100, 650)
        self.setMinimumSize(640, 420)
        self.setStyleSheet(STYLESHEET)

        self._build_menu_bar()
        self._build_central_area()

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        menu_bar.setNativeMenuBar(False)  # misma apariencia en macOS (sin barra global)
        for title in MENU_TITLES:
            menu_bar.addMenu(title)

    def _build_central_area(self) -> None:
        central = QWidget()
        central.setObjectName("Central")
        row = QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.sidebar = ComponentSidebar()
        self.editor = EditorView()

        work_column = QWidget()
        work_column.setObjectName("WorkColumn")
        column = QVBoxLayout(work_column)
        column.setContentsMargins(8, 6, 0, 0)
        column.setSpacing(4)
        title = QLabel(PROJECT_TITLE)
        title.setObjectName("ProjectTitle")
        column.addWidget(title)
        column.addWidget(self.editor, stretch=1)

        row.addWidget(self.sidebar)                 # ancho fijo
        row.addWidget(work_column, stretch=1)       # absorbe el redimensionamiento
        self.setCentralWidget(central)

        # Ambos botones ejecutan exactamente la misma acción.
        self.sidebar.component_requested.connect(self._on_component_requested)

    def _on_component_requested(self, _component_key: str) -> None:
        self.editor.add_circle()
