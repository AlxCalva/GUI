"""Comandos de deshacer (QUndoStack). Cada acción del usuario es un QUndoCommand.

Los comandos guardan referencias a los elementos para que Python no los destruya
mientras están fuera de la escena (deshacer una creación, rehacer un borrado…).
"""
from PySide6.QtCore import QPointF
from PySide6.QtGui import QUndoCommand
from PySide6.QtWidgets import QGraphicsScene

from .blocks import ArrowItem, BlockItem


def refresh_arrows(scene: QGraphicsScene) -> None:
    """Recoloca todas las flechas (las inversas se separan / se vuelven a centrar)."""
    for item in scene.items():
        if isinstance(item, ArrowItem):
            item.update_geometry()


class AddBlockCommand(QUndoCommand):
    def __init__(self, scene: QGraphicsScene, block: BlockItem) -> None:
        super().__init__("Crear bloque")
        self._scene, self._block = scene, block

    def redo(self) -> None:
        self._scene.addItem(self._block)

    def undo(self) -> None:
        self._scene.removeItem(self._block)


class AddArrowCommand(QUndoCommand):
    def __init__(self, scene: QGraphicsScene, arrow: ArrowItem) -> None:
        super().__init__("Conectar bloques")
        self._scene, self._arrow = scene, arrow

    def redo(self) -> None:
        self._arrow.attach()
        self._scene.addItem(self._arrow)

    def undo(self) -> None:
        self._arrow.detach()
        self._scene.removeItem(self._arrow)
        refresh_arrows(self._scene)


class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene: QGraphicsScene, blocks: list, arrows: list) -> None:
        super().__init__("Eliminar")
        self._scene, self._blocks, self._arrows = scene, list(blocks), list(arrows)

    def redo(self) -> None:
        for arrow in self._arrows:
            arrow.detach()
            self._scene.removeItem(arrow)
        for block in self._blocks:
            self._scene.removeItem(block)
        refresh_arrows(self._scene)

    def undo(self) -> None:
        for block in self._blocks:
            self._scene.addItem(block)
        for arrow in self._arrows:
            arrow.attach()
            self._scene.addItem(arrow)
        refresh_arrows(self._scene)


class MoveBlocksCommand(QUndoCommand):
    def __init__(self, moves: list[tuple[BlockItem, QPointF, QPointF]]) -> None:
        super().__init__("Mover bloques")
        self._moves = moves  # (bloque, posición_anterior, posición_nueva)

    def redo(self) -> None:
        for block, _old, new in self._moves:
            block.setPos(new)

    def undo(self) -> None:
        for block, old, _new in self._moves:
            block.setPos(old)


class SetValueCommand(QUndoCommand):
    def __init__(self, block: BlockItem, old: int, new: int) -> None:
        super().__init__("Cambiar valor")
        self._block, self._old, self._new = block, old, new

    def redo(self) -> None:
        self._block.set_value(self._new)

    def undo(self) -> None:
        self._block.set_value(self._old)


class SetParamsCommand(QUndoCommand):
    """Cambia los parámetros de un seno / coseno."""

    def __init__(self, block: BlockItem, old: dict, new: dict) -> None:
        super().__init__("Cambiar parámetros")
        self._block, self._old, self._new = block, dict(old), dict(new)

    def redo(self) -> None:
        self._block.set_params(self._new)

    def undo(self) -> None:
        self._block.set_params(self._old)


class SetWaypointsCommand(QUndoCommand):
    """Añade, mueve o elimina articulaciones de una flecha."""

    def __init__(self, arrow: ArrowItem, old: list, new: list) -> None:
        super().__init__("Editar flecha")
        self._arrow = arrow
        self._old = [QPointF(p) for p in old]
        self._new = [QPointF(p) for p in new]

    def redo(self) -> None:
        self._arrow.set_waypoints(self._new)

    def undo(self) -> None:
        self._arrow.set_waypoints(self._old)
