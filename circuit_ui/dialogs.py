"""Ventanas de diálogo: edición de valores (máx. 3 dígitos) y resultado de la ejecución."""
from typing import Optional

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QFontDatabase, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget,
)

from .signal_graph import MAX_DIGITS


def ask_value(parent: QWidget, title: str, prompt: str, current: int) -> Optional[int]:
    """Pide un entero de hasta MAX_DIGITS dígitos. Devuelve None si se cancela."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(prompt))

    edit = QLineEdit(str(current))
    edit.setMaxLength(MAX_DIGITS)
    edit.setValidator(QRegularExpressionValidator(QRegularExpression(rf"\d{{0,{MAX_DIGITS}}}"), edit))
    edit.selectAll()
    layout.addWidget(edit)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
    ok_button.setText("Aceptar")
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
    ok_button.setEnabled(bool(edit.text()))
    edit.textChanged.connect(lambda text: ok_button.setEnabled(bool(text)))
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    edit.setFocus()
    if dialog.exec() == QDialog.DialogCode.Accepted and edit.text():
        return int(edit.text())
    return None


def show_report(parent: QWidget, title: str, text: str) -> None:
    """Ventana de solo lectura con el resultado de la ejecución."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
    dialog.resize(480, 300)

    layout = QVBoxLayout(dialog)
    view = QPlainTextEdit()
    view.setReadOnly(True)
    view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
    view.setPlainText(text)
    layout.addWidget(view)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
