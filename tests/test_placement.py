"""Pruebas de la lógica de colocación (no requieren Qt). Ejecutar: python -m unittest discover -s tests -v"""
import importlib.util
import math
import unittest
from pathlib import Path

# placement.py no usa Qt; se carga el archivo directamente para que la prueba funcione
# aunque PySide6 no esté instalado.
_spec = importlib.util.spec_from_file_location(
    "placement", Path(__file__).resolve().parent.parent / "circuit_ui" / "placement.py"
)
placement = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(placement)

GRID, SPACING, MIN_DIST = 20, 60, 60
BOUNDS = (28.0, 28.0, 972.0, 572.0)


def fill(n, bounds=BOUNDS, preferred=(500.0, 300.0)):
    occupied = []
    for _ in range(n):
        pos = placement.find_free_position(preferred, bounds, occupied, GRID, SPACING, MIN_DIST)
        if pos is None:
            break
        occupied.append(pos)
    return occupied


class PlacementTests(unittest.TestCase):
    def test_first_circle_is_at_snapped_center(self):
        self.assertEqual(fill(1)[0], (500.0, 300.0))
        self.assertEqual(fill(1, preferred=(507.0, 293.0))[0], (500.0, 300.0))

    def test_positions_are_on_grid_intersections(self):
        for x, y in fill(40):
            self.assertAlmostEqual(x % GRID, 0)
            self.assertAlmostEqual(y % GRID, 0)

    def test_no_overlap_and_all_unique(self):
        pts = fill(60)
        self.assertEqual(len(pts), 60)
        for i, a in enumerate(pts):
            for b in pts[i + 1:]:
                self.assertGreaterEqual(math.hypot(a[0] - b[0], a[1] - b[1]), MIN_DIST - 1e-6)

    def test_all_inside_bounds(self):
        left, top, right, bottom = BOUNDS
        for x, y in fill(100):
            self.assertTrue(left <= x <= right and top <= y <= bottom)

    def test_returns_none_when_area_is_full(self):
        small = (0.0, 0.0, 100.0, 100.0)  # slots anclados en 40: x,y in {40, 100}
        pts = fill(50, bounds=small, preferred=(50.0, 50.0))
        self.assertEqual(len(pts), 4)
        self.assertIsNone(placement.find_free_position((50, 50), small, pts, GRID, SPACING, MIN_DIST))

    def test_degenerate_bounds_return_none(self):
        self.assertIsNone(placement.find_free_position((5, 5), (10, 10, 0, 0), [], GRID, SPACING, MIN_DIST))

    def test_preferred_point_outside_bounds_still_finds_slot(self):
        self.assertIsNotNone(placement.find_free_position((5000, 5000), BOUNDS, [], GRID, SPACING, MIN_DIST))

    def test_second_circle_is_adjacent_to_first(self):
        a, b = fill(2)
        self.assertAlmostEqual(math.hypot(a[0] - b[0], a[1] - b[1]), SPACING)

    def test_deterministic(self):
        self.assertEqual(fill(30), fill(30))


if __name__ == "__main__":
    unittest.main()
