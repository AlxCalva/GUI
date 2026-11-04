"""Punto de entrada de la PoC de interfaz de simulación (referencia visual: DSSIM).

Uso:
    python main.py                 # abre la aplicación
    python main.py --check-assets  # solo verifica que los iconos se cargan
"""
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from circuit_ui.assets import COMPONENT_ICON_FILES, AssetLoadError, load_pixmap
from circuit_ui.main_window import MainWindow


def check_assets() -> None:
    """Carga cada icono y muestra su tamaño original. Lanza AssetLoadError si falla."""
    for file_name in COMPONENT_ICON_FILES:
        pixmap = load_pixmap(file_name)
        print(f"OK  {file_name}: {pixmap.width()}x{pixmap.height()} px")


def main(argv: list[str]) -> int:
    app = QApplication(argv)
    app.setStyle("Fusion")  # mismo aspecto base en Windows, Linux y macOS

    try:
        if "--check-assets" in argv:
            check_assets()
            return 0
        window = MainWindow()
    except AssetLoadError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        QMessageBox.critical(None, "No se pudo cargar un recurso gráfico", str(error))
        return 1

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
