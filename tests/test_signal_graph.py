"""Pruebas de reglas de conexión y evaluación (no requieren Qt).
Ejecutar: python -m unittest discover -s tests -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from circuit_ui.signal_graph import (  # noqa: E402
    MAX_VALUE, Node, evaluate, format_report, validate_connection,
)


def graph(*kinds_values):
    """graph(('circle', 5), ('gain', 3), ...) -> nodes con ids 0..n-1 y nombres automáticos."""
    counters, nodes = {}, {}
    names = {"circle": "Señal", "gain": "Multiplicación", "sum": "Suma", "convolution": "Convolución"}
    for i, (kind, value) in enumerate(kinds_values):
        counters[kind] = counters.get(kind, 0) + 1
        nodes[i] = Node(kind, f"{names[kind]} {counters[kind]}", value)
    return nodes


class ConnectionRules(unittest.TestCase):
    def setUp(self):
        # 0,1 = señales; 2,3,4 = multiplicaciones; 5 = suma; 6 = convolución
        self.nodes = graph(("circle", 5), ("circle", 7), ("gain", 3), ("gain", 2), ("gain", 4),
                           ("sum", None), ("convolution", None))

    def ok(self, edges, s, d):
        self.assertIsNone(validate_connection(self.nodes, edges, s, d))

    def bad(self, edges, s, d):
        self.assertIsNotNone(validate_connection(self.nodes, edges, s, d))

    def test_signal_to_gain_is_valid(self):
        self.ok([], 0, 2)

    def test_circle_to_circle_blocked(self):
        self.bad([], 0, 1)

    def test_gain_to_circle_blocked(self):
        self.bad([], 2, 0)

    def test_self_connection_blocked(self):
        self.bad([], 2, 2)
        self.bad([], 0, 0)

    def test_duplicate_blocked(self):
        self.bad([(0, 2)], 0, 2)

    def test_gain_accepts_only_one_input(self):
        self.bad([(0, 2)], 1, 2)          # segunda señal a la misma multiplicación
        self.bad([(0, 2)], 3, 2)          # ni siquiera desde otra multiplicación

    def test_gain_can_have_many_outputs(self):
        edges = [(0, 2), (2, 3)]
        self.ok(edges, 2, 4)              # misma multiplicación alimenta a otra más
        self.ok([(0, 2), (2, 3)], 2, 4)   # n salidas desde la misma multiplicación

    def test_signal_can_feed_many_gains(self):
        self.ok([(0, 2)], 0, 3)

    def test_gain_chain_is_valid(self):
        self.ok([(0, 2)], 2, 3)

    def test_cycle_blocked(self):
        self.bad([(0, 2), (2, 3)], 3, 2)  # 2->3 ya existe, 3->2 cierra ciclo
        self.bad([(0, 2), (2, 3), (3, 4)], 4, 2)

    def test_unimplemented_blocks_blocked(self):
        self.bad([], 0, 5)                # señal -> suma
        self.bad([], 0, 6)
        self.bad([], 5, 2)                # suma -> multiplicación


class Evaluation(unittest.TestCase):
    def test_signal_times_factor(self):
        nodes = graph(("circle", 5), ("gain", 3))
        ev = evaluate(nodes, [(0, 1)])
        self.assertEqual([r.total for r in ev.results], [15])
        self.assertEqual(ev.results[0].expression, "5 × 3 = 15")
        self.assertFalse(ev.errors)

    def test_chain_of_gains(self):
        nodes = graph(("circle", 5), ("gain", 3), ("gain", 2))
        ev = evaluate(nodes, [(0, 1), (1, 2)])
        self.assertEqual(len(ev.results), 1)            # solo la salida final
        self.assertEqual(ev.results[0].total, 30)
        self.assertEqual(ev.results[0].path, ["Señal 1", "Multiplicación 1", "Multiplicación 2"])

    def test_gain_with_multiple_outputs(self):
        nodes = graph(("circle", 4), ("gain", 2), ("gain", 10), ("gain", 3))
        ev = evaluate(nodes, [(0, 1), (1, 2), (1, 3)])
        self.assertEqual(sorted(r.total for r in ev.results), [24, 80])

    def test_one_signal_feeds_two_gains(self):
        nodes = graph(("circle", 6), ("gain", 2), ("gain", 5))
        ev = evaluate(nodes, [(0, 1), (0, 2)])
        self.assertEqual([r.total for r in ev.results], [12, 30])

    def test_zero_and_max_values(self):
        nodes = graph(("circle", 0), ("gain", MAX_VALUE))
        self.assertEqual(evaluate(nodes, [(0, 1)]).results[0].total, 0)
        nodes = graph(("circle", MAX_VALUE), ("gain", MAX_VALUE))
        self.assertEqual(evaluate(nodes, [(0, 1)]).results[0].total, 998001)

    def test_errors(self):
        self.assertTrue(evaluate({}, []).errors)                                  # vacío
        self.assertTrue(evaluate(graph(("circle", 1)), []).errors)                # sin multiplicación
        self.assertTrue(evaluate(graph(("circle", 1), ("gain", 2)), []).errors)   # gain sin entrada
        self.assertTrue(evaluate(graph(("circle", 1), ("sum", None)), []).errors)  # no implementado

    def test_unconnected_signal_is_warning_not_error(self):
        nodes = graph(("circle", 5), ("circle", 9), ("gain", 3))
        ev = evaluate(nodes, [(0, 2)])
        self.assertFalse(ev.errors)
        self.assertEqual(len(ev.warnings), 1)
        self.assertIn("Señal 2", ev.warnings[0])

    def test_report_text(self):
        nodes = graph(("circle", 5), ("gain", 3))
        text = format_report(evaluate(nodes, [(0, 1)]))
        self.assertIn("5 × 3 = 15", text)
        text = format_report(evaluate({}, []))
        self.assertIn("No se pudo ejecutar", text)


if __name__ == "__main__":
    unittest.main()
