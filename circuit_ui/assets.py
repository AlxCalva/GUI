"""Carga de recursos gráficos desde la carpeta assets/ del proyecto."""
from pathlib import Path

from PySide6.QtGui import QPixmap

# Ruta relativa a la ubicación del proyecto (no depende de la máquina del usuario).
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

# Orden = orden de los botones en la barra lateral.
COMPONENT_ICON_FILES = ("component_1.png", "component_2.png")


class AssetLoadError(RuntimeError):
    """Un recurso gráfico no existe o no pudo decodificarse."""


def load_pixmap(file_name: str) -> QPixmap:
    """Carga un PNG de assets/. Nunca sustituye la imagen por otra: si falla, lanza error."""
    path = ASSETS_DIR / file_name

    if not path.is_file():
        raise AssetLoadError(
            f"No se encontró el recurso gráfico:\n  {path}\n\n"
            f"Cómo corregirlo: copia el archivo '{file_name}' en la carpeta\n"
            f"  {ASSETS_DIR}\n"
            f"o ajusta el nombre en COMPONENT_ICON_FILES (circuit_ui/assets.py)."
        )

    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        raise AssetLoadError(
            f"El archivo existe pero Qt no pudo leerlo como imagen:\n  {path}\n\n"
            f"Cómo corregirlo: comprueba que sea un PNG válido y no esté dañado."
        )
    return pixmap
