"""Reglas de conexión y evaluación del diagrama de señales. Python puro (sin Qt).

El editor construye una «foto» del diagrama (nodos + aristas dirigidas) y este módulo
decide si una conexión es válida y calcula el resultado de la ejecución.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

# Límite de los valores editables (señales de entrada y factores de multiplicación).
MAX_DIGITS = 3
MIN_VALUE = 0
MAX_VALUE = 10 ** MAX_DIGITS - 1  # 999


@dataclass(frozen=True)
class KindRules:
    name: str                    # nombre base mostrado al usuario («Señal 1», «Multiplicación 2»…)
    can_receive: bool            # ¿admite flechas entrantes?
    max_inputs: Optional[int]    # None = ilimitadas
    implemented: bool            # ¿se puede conectar y ejecutar ya?
    default_value: Optional[int]  # None = el bloque no tiene valor configurable


RULES: dict[str, KindRules] = {
    # Señal de entrada: solo emite. Valor editable (0-999).
    "circle": KindRules("Señal", can_receive=False, max_inputs=0, implemented=True, default_value=0),
    # Multiplicación (triángulo): exactamente UNA entrada, salidas ilimitadas. Factor editable.
    "gain": KindRules("Multiplicación", can_receive=True, max_inputs=1, implemented=True, default_value=1),
    # Pendientes de implementar (la suma admitirá varias entradas).
    "sum": KindRules("Suma", can_receive=True, max_inputs=None, implemented=False, default_value=None),
    "convolution": KindRules("Convolución", can_receive=True, max_inputs=None, implemented=False, default_value=None),
}


def default_value(kind: str) -> Optional[int]:
    return RULES[kind].default_value


def has_value(kind: str) -> bool:
    return RULES[kind].default_value is not None


@dataclass
class Node:
    kind: str
    name: str
    value: Optional[int] = None


Edge = tuple[int, int]  # (id_origen, id_destino)


def _reaches(edges: list[Edge], start: int, goal: int) -> bool:
    """¿Existe un camino dirigido start → … → goal?"""
    outgoing: dict[int, list[int]] = {}
    for s, d in edges:
        outgoing.setdefault(s, []).append(d)
    stack, seen = [start], set()
    while stack:
        current = stack.pop()
        if current == goal:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(outgoing.get(current, []))
    return False


def validate_connection(nodes: dict[int, Node], edges: list[Edge], source: int, target: int) -> Optional[str]:
    """Devuelve el motivo del rechazo (texto para el usuario) o None si la conexión es válida."""
    src, dst = nodes[source], nodes[target]
    src_rules, dst_rules = RULES[src.kind], RULES[dst.kind]

    if source == target:
        return "Un bloque no se puede conectar consigo mismo."
    if (source, target) in edges:
        return "Esa conexión ya existe."
    for node, rules in ((src, src_rules), (dst, dst_rules)):
        if not rules.implemented:
            return f"El bloque «{rules.name}» todavía no está disponible en esta versión."
    if not dst_rules.can_receive:
        return (f"«{dst_rules.name}» es una señal de entrada: no puede recibir flechas. "
                f"Las flechas solo pueden llegar a un bloque de operación.")
    if dst_rules.max_inputs is not None:
        incoming = sum(1 for _, d in edges if d == target)
        if incoming >= dst_rules.max_inputs:
            plural = "una sola señal" if dst_rules.max_inputs == 1 else f"{dst_rules.max_inputs} señales"
            return f"«{dst.name}» solo acepta {plural} de entrada y ya la tiene conectada."
    if _reaches(edges, target, source):
        return "La conexión crearía un ciclo: la señal volvería a su propio origen."
    return None


# --- Evaluación --------------------------------------------------------------------
@dataclass
class Result:
    output_name: str
    path: list[str]          # nombres desde la señal hasta la salida
    signal_value: int
    factors: list[int]
    total: int

    @property
    def expression(self) -> str:
        parts = [str(self.signal_value)] + [str(f) for f in self.factors]
        return f"{' × '.join(parts)} = {self.total}"


@dataclass
class Evaluation:
    results: list[Result] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _natural_key(text: str) -> list:
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", text)]


def evaluate(nodes: dict[int, Node], edges: list[Edge]) -> Evaluation:
    """Calcula la salida de cada multiplicación final (sin flechas de salida)."""
    ev = Evaluation()
    incoming: dict[int, list[int]] = {nid: [] for nid in nodes}
    outgoing: dict[int, list[int]] = {nid: [] for nid in nodes}
    for s, d in edges:
        outgoing[s].append(d)
        incoming[d].append(s)

    if not nodes:
        ev.errors.append("El área de trabajo está vacía: no hay nada que ejecutar.")
        return ev

    for node in nodes.values():
        if not RULES[node.kind].implemented:
            ev.errors.append(f"«{node.name}» todavía no está disponible; elimínalo para poder ejecutar.")

    gains = [nid for nid, n in nodes.items() if n.kind == "gain"]
    if not gains and not ev.errors:
        ev.errors.append("No hay ninguna multiplicación: conecta una señal a un triángulo.")
    for gid in gains:
        count = len(incoming[gid])
        if count == 0:
            ev.errors.append(f"«{nodes[gid].name}» no tiene señal de entrada.")
        elif count > 1:
            ev.errors.append(f"«{nodes[gid].name}» recibe {count} señales y solo admite una.")
    if any(_reaches(edges, d, s) for s, d in edges):
        ev.errors.append("El diagrama contiene un ciclo.")
    if ev.errors:
        return ev

    for nid, node in nodes.items():
        if node.kind == "circle" and not outgoing[nid]:
            ev.warnings.append(f"«{node.name}» no está conectada y se ignoró.")

    for gid in sorted(gains, key=lambda g: _natural_key(nodes[g].name)):
        if outgoing[gid]:
            continue  # intermedia: su resultado alimenta a otra multiplicación
        chain, current = [], gid
        while nodes[current].kind == "gain":
            chain.append(current)
            current = incoming[current][0]
        chain.reverse()
        signal = nodes[current]
        factors = [nodes[g].value for g in chain]
        total = signal.value
        for factor in factors:
            total *= factor
        ev.results.append(Result(
            output_name=nodes[gid].name,
            path=[signal.name] + [nodes[g].name for g in chain],
            signal_value=signal.value,
            factors=factors,
            total=total,
        ))
    return ev


def format_report(ev: Evaluation) -> str:
    """Texto que se muestra en la ventana de resultados."""
    lines: list[str] = []
    if ev.errors:
        lines.append("No se pudo ejecutar:")
        lines += [f"  • {e}" for e in ev.errors]
    else:
        lines.append("Resultado de la ejecución")
        lines.append("")
        for r in ev.results:
            lines.append(f"{r.output_name}:  {r.expression}")
            lines.append(f"    camino: {' → '.join(r.path)}")
    if ev.warnings:
        lines.append("")
        lines.append("Advertencias:")
        lines += [f"  • {w}" for w in ev.warnings]
    return "\n".join(lines)
