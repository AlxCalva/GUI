"""Estrategia de colocación de círculos. Python puro (sin Qt) para poder probarla aislada.

Idea: se parte del punto preferido (centro del área visible), se ajusta a la malla y se
recorren posiciones separadas `slot_spacing` en espiral hacia fuera. Se devuelve la primera
que esté dentro de los límites y no choque con ninguna ocupada.
"""
import math
from typing import Iterator, Optional, Sequence

Point = tuple[float, float]
Bounds = tuple[float, float, float, float]  # (izquierda, arriba, derecha, abajo)


def snap_to_grid(value: float, grid_size: float) -> float:
    return round(value / grid_size) * grid_size


def _spiral_offsets(max_ring: int) -> Iterator[tuple[int, int]]:
    """Desplazamientos enteros (dx, dy) por anillos concéntricos; dentro de cada anillo,
    de menor a mayor distancia al centro. Orden determinista."""
    yield (0, 0)
    for ring in range(1, max_ring + 1):
        cells = [
            (dx, dy)
            for dx in range(-ring, ring + 1)
            for dy in range(-ring, ring + 1)
            if max(abs(dx), abs(dy)) == ring
        ]
        cells.sort(key=lambda c: (c[0] ** 2 + c[1] ** 2, c[1], c[0]))
        yield from cells


def find_free_position(
    preferred: Point,
    bounds: Bounds,
    occupied: Sequence[Point],
    grid_size: float,
    slot_spacing: float,
    min_distance: float,
) -> Optional[Point]:
    """Primera posición libre (centro del círculo) o None si no queda ninguna."""
    left, top, right, bottom = bounds
    if right < left or bottom < top:
        return None

    anchor_x = snap_to_grid(preferred[0], grid_size)
    anchor_y = snap_to_grid(preferred[1], grid_size)

    # Radio de búsqueda suficiente para cubrir todo `bounds` desde el ancla.
    farthest = max(
        math.hypot(anchor_x - x, anchor_y - y)
        for x in (left, right)
        for y in (top, bottom)
    )
    max_ring = math.ceil(farthest / slot_spacing) + 1

    for dx, dy in _spiral_offsets(max_ring):
        x = anchor_x + dx * slot_spacing
        y = anchor_y + dy * slot_spacing
        if not (left <= x <= right and top <= y <= bottom):
            continue
        if all(math.hypot(x - ox, y - oy) >= min_distance - 1e-6 for ox, oy in occupied):
            return (x, y)
    return None
