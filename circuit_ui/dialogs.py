"""Ventanas de diálogo: edición de valores (máx. 3 dígitos) y resultado de la ejecución."""
from typing import Optional

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QFontDatabase, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from .signal_graph import MAX_DIGITS, MAX_WAVE_VALUE, default_params

WAVE_FIELDS = (
    ("amplitude", "Amplitud (A)"),
    ("frequency", "Frecuencia (\u03c9, rad/muestra)"),
    ("phase", "Fase (\u03c6, rad)"),
    ("offset", "Desplazamiento vertical (C)"),
)


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


def ask_wave_params(parent: QWidget, kind: str, name: str, current: dict) -> Optional[dict]:
    """Edita x[n] = A·sin(ω·n + φ) + C (o cos). Devuelve None si se cancela."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Seno" if kind == "sin" else "Coseno")
    dialog.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(f"\u00ab{name}\u00bb:   x[n] = A\u00b7{kind}(\u03c9\u00b7n + \u03c6) + C"))

    form = QFormLayout()
    spins: dict[str, QDoubleSpinBox] = {}
    for key, label in WAVE_FIELDS:
        spin = QDoubleSpinBox()
        spin.setRange(-MAX_WAVE_VALUE, MAX_WAVE_VALUE)
        spin.setDecimals(3)
        spin.setSingleStep(0.1)
        spin.setValue(current[key])
        spins[key] = spin
        form.addRow(label, spin)
    layout.addLayout(form)

    reset = QPushButton("Restablecer est\u00e1ndar")
    reset.setAutoDefault(False)   # que Intro no lo active
    reset.clicked.connect(lambda: [spins[k].setValue(v) for k, v in default_params(kind).items()])
    layout.addWidget(reset)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Aceptar")
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        return {key: spin.value() for key, spin in spins.items()}
    return None


def show_report(parent: QWidget, title: str, text: str) -> None:
    """Ventana de solo lectura con el resultado de la ejecución."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
    dialog.resize(700, 460)

    layout = QVBoxLayout(dialog)
    view = QPlainTextEdit()
    view.setReadOnly(True)
    view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
    view.setPlainText(text)
    layout.addWidget(view)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
