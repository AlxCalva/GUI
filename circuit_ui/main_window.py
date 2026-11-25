"""Ventana principal: menú superior + barra lateral + área de trabajo."""
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

from .dialogs import show_report
from .editor_view import EditorView
from .sidebar import ComponentSidebar
from .signal_graph import evaluate, format_report
from .styles import STYLESHEET

MENU_TITLES = ("Project", "Analysis", "View", "Plot")  # sin acciones en esta PoC
PROJECT_TITLE = "New Project"  # etiqueta estática, como en la referencia

# Qué crea cada botón con imagen de la barra lateral.
COMPONENT_KINDS = {"component_1": "integrator", "component_2": "circle"}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DSSIM - PoC de interfaz")
        self.resize(1100, 650)
        self.setMinimumSize(640, 560)
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

        # Modo flecha: botón <-> editor (Esc en el editor desmarca el botón).
        self.sidebar.connect_mode_toggled.connect(self.editor.set_connect_mode)
        self.editor.connect_mode_changed.connect(self.sidebar.set_connect_checked)

        # Botón Ejecutar -> ventana con el resultado.
        self.sidebar.run_requested.connect(self._on_run_requested)

        # Ctrl+Z (Cmd+Z en macOS): deshace la última acción. La acción se habilita/deshabilita sola.
        undo_action = self.editor.undo_stack.createUndoAction(self, "Deshacer")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.addAction(undo_action)

    def _on_component_requested(self, component_key: str) -> None:
        if component_key.startswith("op_"):
            self.editor.add_block(component_key[len("op_"):])  # sin / cos / gain / sum / convolution
        else:
            self.editor.add_block(COMPONENT_KINDS[component_key])

    def _on_run_requested(self) -> None:
        nodes, edges = self.editor.build_graph()
        show_report(self, "Resultado", format_report(evaluate(nodes, edges)))
