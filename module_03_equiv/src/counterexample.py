"""
counterexample.py -- readable rendering of check_compliance()'s raw
counter_example_trace.

The raw trace (see lifter.cpp's counter-example extraction) is a full BDD
state dump: every atom registered on the automaton, positive or negated,
including bookkeeping atoms a property author never wrote (the LTLf->LTL
bridge's own ``alive``) and gateway guard atoms unrelated to any given
property. That's the right level of detail for debugging the engine; it is
not what item #6 ("first e2e demo") means by "readable counterexample" for a
human looking at a PASS/FAIL report.

This module does not change what check_compliance() returns -- the raw
trace remains the ground truth, unmodified. It's a presentation layer on
top: given the trace and the specific property that was violated, extract
just the property's own atoms' truth values, in order, and render them as a
plain task sequence.
"""

from __future__ import annotations

import re

_STEP_RE = re.compile(r"\[\d+\]\s+state=\S+\s+label=(.*)")
_ATOM_RE = re.compile(r"(?:start|done)\(([^)]+)\)")


def _relevant_atoms(origin_formula: str) -> list[str]:
    """Extract the task names a property's own formula refers to (its
    start(T)/done(T) atoms), deduplicated, in first-appearance order --
    the set this trace should be filtered down to."""
    seen: dict[str, None] = {}
    for m in _ATOM_RE.finditer(origin_formula):
        seen.setdefault(m.group(1), None)
    return list(seen)


def _parse_step(label: str) -> dict[str, bool]:
    """Parse one 'label=A & !B & C' string into {atom: truth_value}."""
    truth: dict[str, bool] = {}
    for literal in label.split("&"):
        literal = literal.strip()
        if not literal:
            continue
        negated = literal.startswith("!")
        atom = literal[1:] if negated else literal
        truth[atom] = not negated
    return truth


def format_counterexample(raw_trace: str, origin_formula: str) -> str:
    """
    Render *raw_trace* (a check_compliance() VIOLATION's counter_example_trace)
    as a plain task sequence, filtered to the atoms *origin_formula* actually
    refers to. Returns "" if there's nothing to show (e.g. a COMPLIANT
    result, whose trace is already empty).
    """
    if not raw_trace.strip():
        return ""

    atoms_of_interest = _relevant_atoms(origin_formula)
    if not atoms_of_interest:
        return raw_trace  # nothing to filter against -- show it verbatim

    prefix_part, _, cycle_part = raw_trace.partition("Counter-example trace (cycle):")

    events: list[str] = []
    for line in prefix_part.splitlines():
        m = _STEP_RE.search(line)
        if not m:
            continue
        truth = _parse_step(m.group(1))
        occurred = [a for a in atoms_of_interest if truth.get(a) is True]
        events.extend(occurred)

    cycle_events: list[str] = []
    for line in cycle_part.splitlines():
        m = _STEP_RE.search(line)
        if not m:
            continue
        truth = _parse_step(m.group(1))
        cycle_events.extend(a for a in atoms_of_interest if truth.get(a) is True)

    if not events and not cycle_events:
        return "(the violating run never touches this property's own tasks -- see the raw trace for the actual counter-model)"

    rendered = " → ".join(events) if events else "(no relevant task before the loop)"
    if cycle_events:
        rendered += f", then repeats: {' → '.join(cycle_events)}"
    return rendered
