"""Reglas de conexión y simulación en tiempo discreto del diagrama de señales. Python puro (sin Qt).

El editor construye una «foto» del diagrama (nodos + aristas dirigidas) y este módulo
decide si una conexión es válida y calcula la salida de cada bloque, muestra a muestra
(n = 0, 1, 2…). Así los lazos de realimentación funcionan: basta con que pasen por un
integrador digital (que solo depende de muestras pasadas).
"""
import math
import re
from dataclasses import dataclass, field
from typing import Optional

# Límite de los valores enteros editables (señal constante y factor de multiplicación).
MAX_DIGITS = 3
MIN_VALUE = 0
MAX_VALUE = 10 ** MAX_DIGITS - 1  # 999

MAX_WAVE_VALUE = 999.0            # límite de los parámetros de seno / coseno
SAMPLES = 16                      # muestras que se simulan: n = 0 … SAMPLES-1

# Seno / coseno estándar: x[n] = A·sin(ω·n + φ) + C  con A=1, ω=1, φ=0, C=0.
WAVE_DEFAULTS = {"amplitude": 1.0, "frequency": 1.0, "phase": 0.0, "offset": 0.0}


@dataclass(frozen=True)
class KindRules:
    name: str                              # nombre base mostrado («Señal 1», «Suma 2»…)
    min_inputs: int
    max_inputs: Optional[int]              # None = ilimitadas; 0 = no admite flechas entrantes
    default_value: Optional[int] = None    # valor entero configurable (constante / factor)
    default_params: Optional[dict] = None  # parámetros reales configurables (seno / coseno)
    is_source: bool = False                # genera señal sin entradas
    is_delay: bool = False                 # su salida en n depende solo de entradas en n-1


RULES: dict[str, KindRules] = {
    "circle": KindRules("Señal", 0, 0, default_value=0, is_source=True),           # constante
    "sin": KindRules("Seno", 0, 0, default_params=WAVE_DEFAULTS, is_source=True),
    "cos": KindRules("Coseno", 0, 0, default_params=WAVE_DEFAULTS, is_source=True),
    "gain": KindRules("Multiplicación", 1, 1, default_value=1),                    # triángulo
    "sum": KindRules("Suma", 1, None),                                             # n entradas
    "convolution": KindRules("Convolución", 2, 2),                                 # dos entradas
    "integrator": KindRules("Integrador", 1, 1, is_delay=True),                    # z⁻¹/(1−z⁻¹)
}


def default_value(kind: str) -> Optional[int]:
    return RULES[kind].default_value


def default_params(kind: str) -> Optional[dict]:
    params = RULES[kind].default_params
    return dict(params) if params else None


def has_value(kind: str) -> bool:
    return RULES[kind].default_value is not None


def has_params(kind: str) -> bool:
    return RULES[kind].default_params is not None


def wave_formula(kind: str, p: dict) -> str:
    """Texto legible de la función, omitiendo los parámetros estándar."""
    amp, freq, phase, offset = p["amplitude"], p["frequency"], p["phase"], p["offset"]
    arg = "n" if freq == 1 else f"{freq:g}·n"
    if phase:
        arg += f" {'+' if phase > 0 else '−'} {abs(phase):g}"
    text = f"{kind}({arg})"
    if amp == -1:
        text = "−" + text
    elif amp != 1:
        text = f"{amp:g}·{text}"
    if offset:
        text += f" {'+' if offset > 0 else '−'} {abs(offset):g}"
    return f"x[n] = {text}"


@dataclass
class Node:
    kind: str
    name: str
    value: Optional[int] = None
    params: Optional[dict] = None


Edge = tuple[int, int]  # (id_origen, id_destino)


# --- Validación --------------------------------------------------------------------
def _creates_algebraic_loop(nodes: dict[int, Node], edges: list[Edge], source: int, target: int) -> bool:
    """Un lazo es válido solo si contiene un retardo. La flecha s→d es «instantánea»
    (la salida de d en n depende de la de s en n) salvo que d sea un integrador."""
    if RULES[nodes[target].kind].is_delay:
        return False   # la nueva flecha entra en un retardo: no puede cerrar un lazo instantáneo
    outgoing: dict[int, list[int]] = {}
    for s, d in edges:
        if not RULES[nodes[d].kind].is_delay:
            outgoing.setdefault(s, []).append(d)
    stack, seen = [target], set()
    while stack:
        current = stack.pop()
        if current == source:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(outgoing.get(current, []))
    return False


def validate_connection(nodes: dict[int, Node], edges: list[Edge], source: int, target: int) -> Optional[str]:
    """Devuelve el motivo del rechazo (texto para el usuario) o None si la conexión es válida."""
    src, dst = nodes[source], nodes[target]
    dst_rules = RULES[dst.kind]

    if source == target:
        return "Un bloque no se puede conectar consigo mismo."
    if (source, target) in edges:
        return "Esa conexión ya existe."
    if dst_rules.max_inputs == 0:
        return (f"«{dst.name}» es una fuente de señal: no puede recibir flechas. "
                f"Las flechas solo pueden llegar a un bloque de operación.")
    if dst_rules.max_inputs is not None:
        incoming = sum(1 for _, d in edges if d == target)
        if incoming >= dst_rules.max_inputs:
            plural = "una sola señal" if dst_rules.max_inputs == 1 else f"{dst_rules.max_inputs} señales"
            return f"«{dst.name}» solo acepta {plural} de entrada y ya la tiene conectada."
    if _creates_algebraic_loop(nodes, edges, source, target):
        return ("La conexión crearía un lazo sin retardo. Todo lazo de realimentación debe "
                "pasar por un integrador digital.")
    return None


# --- Simulación --------------------------------------------------------------------
@dataclass
class Series:
    name: str
    values: list
    is_output: bool          # bloque sin flechas de salida


@dataclass
class Evaluation:
    samples: int = 0
    series: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def _natural_key(text: str) -> list:
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", text)]


def _arity_text(rules: KindRules) -> str:
    if rules.min_inputs == rules.max_inputs:
        return "exactamente una señal" if rules.min_inputs == 1 else f"exactamente {rules.min_inputs} señales"
    return "al menos una señal"


def _schedule(nodes: dict[int, Node], incoming: dict[int, list[int]]) -> Optional[list[int]]:
    """Orden de cálculo dentro de una misma muestra (solo cuentan las flechas instantáneas)."""
    pending = {nid: 0 for nid in nodes}
    successors: dict[int, list[int]] = {nid: [] for nid in nodes}
    for dst, sources in incoming.items():
        if RULES[nodes[dst].kind].is_delay:
            continue
        for src in sources:
            pending[dst] += 1
            successors[src].append(dst)
    ready = sorted(nid for nid, count in pending.items() if count == 0)
    order: list[int] = []
    while ready:
        nid = ready.pop()
        order.append(nid)
        for dst in successors[nid]:
            pending[dst] -= 1
            if pending[dst] == 0:
                ready.append(dst)
    return order if len(order) == len(nodes) else None


def _step(node: Node, own: list, ins: list, n: int) -> float:
    """Salida del bloque en la muestra n. `own` = sus salidas anteriores; `ins` = señales de entrada."""
    kind = node.kind
    if kind == "circle":
        return float(node.value)
    if kind in ("sin", "cos"):
        p = node.params
        fn = math.sin if kind == "sin" else math.cos
        return p["amplitude"] * fn(p["frequency"] * n + p["phase"]) + p["offset"]
    if kind == "gain":
        return node.value * ins[0][n]
    if kind == "sum":
        return sum(signal[n] for signal in ins)
    if kind == "convolution":
        a, b = ins
        return sum(a[k] * b[n - k] for k in range(n + 1))      # y[n] = Σ a[k]·b[n−k]
    if kind == "integrator":
        return 0.0 if n == 0 else own[n - 1] + ins[0][n - 1]   # y[n] = y[n−1] + x[n−1]
    raise ValueError(kind)


def evaluate(nodes: dict[int, Node], edges: list[Edge], samples: int = SAMPLES) -> Evaluation:
    ev = Evaluation(samples=samples)
    if not nodes:
        ev.errors.append("El área de trabajo está vacía: no hay nada que ejecutar.")
        return ev

    incoming: dict[int, list[int]] = {nid: [] for nid in nodes}
    outgoing: dict[int, list[int]] = {nid: [] for nid in nodes}
    for s, d in sorted(edges):
        outgoing[s].append(d)
        incoming[d].append(s)

    by_name = sorted(nodes, key=lambda i: _natural_key(nodes[i].name))
    for nid in by_name:
        node, rules = nodes[nid], RULES[nodes[nid].kind]
        count = len(incoming[nid])
        if count < rules.min_inputs:
            ev.errors.append(f"«{node.name}» necesita {_arity_text(rules)} de entrada y tiene {count}.")
        elif rules.max_inputs is not None and count > rules.max_inputs:
            ev.errors.append(f"«{node.name}» recibe {count} señales y solo admite {rules.max_inputs}.")

    if all(RULES[n.kind].is_source for n in nodes.values()):
        ev.errors.append("No hay ninguna operación: conecta una señal a un bloque de operación.")

    order = _schedule(nodes, incoming)
    if order is None:
        ev.errors.append("Hay un lazo sin retardo: todo lazo de realimentación debe pasar por un integrador.")
    if ev.errors:
        return ev

    active = []
    for nid in by_name:
        node = nodes[nid]
        if RULES[node.kind].is_source and not outgoing[nid]:
            ev.warnings.append(f"«{node.name}» no está conectada y se ignoró.")
        else:
            active.append(nid)

    out: dict[int, list[float]] = {nid: [] for nid in nodes}
    for n in range(samples):
        for nid in order:
            ins = [out[i] for i in incoming[nid]]
            out[nid].append(_step(nodes[nid], out[nid], ins, n))

    sources = [i for i in active if RULES[nodes[i].kind].is_source]
    operations = [i for i in active if not RULES[nodes[i].kind].is_source]
    for nid in sources + operations:
        is_output = not RULES[nodes[nid].kind].is_source and not outgoing[nid]
        ev.series.append(Series(nodes[nid].name, out[nid], is_output))

    kinds = {nodes[i].kind for i in active}
    if kinds & {"sin", "cos"}:
        ev.notes.append("Seno/coseno: x[n] = A·sin(ω·n + φ) + C  (ω y φ en radianes; n = índice de muestra).")
    if "integrator" in kinds:
        ev.notes.append("Integrador z⁻¹/(1−z⁻¹): y[n] = y[n−1] + x[n−1], condiciones iniciales = 0.")
    if "convolution" in kinds:
        ev.notes.append("Convolución: y[n] = Σ x₁[k]·x₂[n−k], k = 0…n (señales causales).")
    return ev


def _fmt(value: float) -> str:
    if not math.isfinite(value):
        return str(value)
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.5f}".rstrip("0").rstrip(".")


def format_report(ev: Evaluation) -> str:
    """Texto que se muestra en la ventana de resultados."""
    lines: list[str] = []
    if ev.errors:
        lines.append("No se pudo ejecutar:")
        lines += [f"  • {e}" for e in ev.errors]
    else:
        outputs = [s.name for s in ev.series if s.is_output]
        lines.append(f"Resultado de la ejecución  (n = 0 … {ev.samples - 1})")
        lines.append("Salidas (*): " + (", ".join(outputs) if outputs
                                        else "ninguna (todas las señales alimentan a otros bloques)"))
        lines.append("")
        labels = [s.name + (" *" if s.is_output else "") for s in ev.series]
        cells = [[_fmt(v) for v in s.values] for s in ev.series]
        widths = [max(len(label), *(len(c) for c in col)) for label, col in zip(labels, cells)]
        header = "  n | " + " | ".join(label.rjust(w) for label, w in zip(labels, widths))
        lines.append(header)
        lines.append("-" * len(header))
        for n in range(ev.samples):
            row = " | ".join(col[n].rjust(w) for col, w in zip(cells, widths))
            lines.append(f"{n:3d} | {row}")
        if ev.notes:
            lines.append("")
            lines += ev.notes
    if ev.warnings:
        lines.append("")
        lines.append("Advertencias:")
        lines += [f"  • {w}" for w in ev.warnings]
    return "\n".join(lines)
