"""
property_ingest.py
===================
Loads Module 01's exported property suite (``module_03_input.json``,
produced by ``module_01_spec.api.export_for_module_03``) and produces the
tier-gated, SPOT-ready property list Phase D can model-check.

Pure Python, no C++/SPOT dependency -- testable without the toolchain.

Module 03 deploys as its own container with no access to module_01_spec's
source (module_03_equiv/Dockerfile only copies this module's own ``src/``),
so the LTLf syntax normalization Module 01's own (uncalled) FormulaNormalizer
performs is ported here in miniature rather than cross-imported, to keep the
dual-track independence the whole project is built on: Module 03 consumes
Module 01's JSON *output*, never its source.

Scope, deliberately narrow (see Bridge Investigation/E2E Integration
Verification Findings for the corpus measurements this is based on):
  - Only "P1_Structural_Control_Flow" properties that do not reference a
    spec-only node(...) atom are checkable against code today (17.6% of the
    tier's own properties, corpus-measured). Everything else is reported as
    excluded with a reason, never silently dropped.
  - Atoms are collapsed from Module 01's start(T)/done(T) lifecycle events to
    a single flat, quoted atom per task ("Option B" in the design docs) --
    the code side has no lifecycle events to distinguish start from done, and
    this is lossless for the sequential-only corpus this project covers today
    (see the design docs for the tradeoff and its limits).
  - P0 (excluded by construction -- a lifting self-test, not a conformance
    check), P2 (contains a "<=" comparison SPOT's LTL grammar cannot parse,
    and references code-side atoms that do not exist), and P3 (needs the
    LTLf->LTL "X"-operator bridge, not designed here) are all excluded.
  - "P4_Task_Coverage" is checkable ONLY in its unconditional shape,
    "F(done(X))" -> "F(X)". Its conditional shape, "G(start(X) -> F(done(X)))"
    (emitted by Module 01 for tasks that are not on every start->end path --
    see ltlf_synthesizer.py's _generate_sentinels), collapses under the same
    Option-B atom merge to G("X" -> F("X")) -- verified (evaluate_ltlf over
    all traces up to length 4) to be an unfalsifiable tautology, the exact
    same failure mode ap_gap_memo.md already documented for P0's
    "!done(T) W start(T)" -> "!T W T". Excluded with a reason, not silently
    checked as if it meant something.
  - Exact intra-tier duplicate formulas are de-duplicated (measured at 34 of
    412 properties in the real corpus). Exact cross-tier duplicates (e.g.
    "synthesized_mutant_killers" entries mutation_refiner.py already copied
    into "P1_Structural_Control_Flow" at synthesis time) are also
    de-duplicated by formula text -- checked once, under whichever tier is
    processed first, not once per tier it happens to appear in.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Property:
    """One conformance-checkable property, ready for check_compliance()."""
    formula: str            # SPOT-ready infix string (quoted, flat atoms)
    origin_formula: str     # the exact string Module 01 exported
    tier: str


@dataclass(frozen=True)
class ExcludedProperty:
    """A property Module 01 exported that this ingestion does not check."""
    origin_formula: str
    tier: str
    reason: str


class PropertySuite:
    def __init__(
        self,
        properties: list[Property],
        excluded: list[ExcludedProperty],
    ) -> None:
        self._properties = properties
        self._excluded = excluded

    def conformance_properties(self) -> list[Property]:
        return list(self._properties)

    def excluded_properties(self) -> list[ExcludedProperty]:
        return list(self._excluded)

    def __repr__(self) -> str:
        return (
            f"<PropertySuite checkable={len(self._properties)} "
            f"excluded={len(self._excluded)}>"
        )


# Tiers this ingestion layer has an explicit policy for. A tier present in
# the exported suite but absent here (or from the export's own
# tier_semantics) is an ingestion error, not a silent skip -- a tier quietly
# vanishing would corrupt every downstream result with no trace.
_KNOWN_TIERS = {
    "P0_Critical_Sentinels",
    "P1_Structural_Control_Flow",
    "P2_Quality_Limits",
    "P3_Adversarial_Defenses",
    "P4_Task_Coverage",
    "synthesized_mutant_killers",
}

_LIFECYCLE_ATOM_RE = re.compile(r"(?:start|done)\(([^)]+)\)")
_NODE_ATOM_RE = re.compile(r"\bnode\(")
_QUOTED_RE = re.compile(r'"[^"]*"')
_DISALLOWED_OPERATOR_RE = re.compile(r"<=|>=|==|!=|<|>")

# P4_Task_Coverage's conditional shape: "G(start(X) -> F(done(X)))". Under
# Option B's start/done merge this becomes G("X" -> F("X")), a tautology
# (verified with evaluate_ltlf) -- excluded explicitly rather than checked
# as if it carried meaning. The unconditional shape, "F(done(X))", has no
# start(X) on the same task and is NOT matched by this pattern; it collapses
# to a genuine, falsifiable "F(X)" omission check and is checked normally.
_P4_VACUOUS_CONDITIONAL_RE = re.compile(
    r"^G\(start\(([^)]+)\) -> F\(done\(\1\)\)\)$"
)


def _to_spot_option_b(formula: str) -> str:
    """
    Converts an M01 LTLf string to SPOT infix syntax: && -> &, || -> |, and
    start(T)/done(T) -> "T" (Option B: the lifecycle prefix is dropped, and
    the bare task name is quoted).

    Quoting is required, not cosmetic: SPOT's infix parser reads an
    unquoted atom starting with a reserved operator letter (G, F, X, U, W,
    R, M) as that operator applied to the remainder -- e.g. GitHub_thing
    parses as G(itHub_thing). Many real BPMN/connector task names start
    with one of these letters. (Found verifying the vacuity-channel fix
    against real FLOW-BENCH task names -- see Module 03 Knowledge.)
    """
    f = formula.replace("&&", "&").replace("||", "|")
    f = _LIFECYCLE_ATOM_RE.sub(lambda m: f'"{m.group(1)}"', f)
    return f


def _rejects_spot_grammar(spot_formula: str) -> str | None:
    """
    Returns a rejection reason if spot_formula contains a construct outside
    SPOT's propositional/temporal grammar (e.g. P2's "iteration_count <=
    10" -- a numeric comparison, not an atom), else None. Checked on the
    formula with quoted atoms stripped out first, so a comparison-looking
    character inside a real task name can never trigger a false rejection.
    """
    unquoted = _QUOTED_RE.sub("", spot_formula)
    if _DISALLOWED_OPERATOR_RE.search(unquoted):
        return "contains a comparison operator SPOT's LTL grammar cannot parse as an atom"
    return None


def load_property_suite(source: str | dict) -> PropertySuite:
    """
    source: a path to module_03_input.json, or an already-parsed dict (the
    payload module_01_spec.api.export_for_module_03() writes).
    """
    if isinstance(source, str):
        with open(source) as f:
            payload = json.load(f)
    else:
        payload = source

    if "ltlf_property_suite" not in payload:
        raise ValueError("module_03_input payload missing 'ltlf_property_suite'")
    if "tier_semantics" not in payload:
        raise ValueError("module_03_input payload missing 'tier_semantics'")

    suite = payload["ltlf_property_suite"]
    tier_semantics = payload["tier_semantics"]

    unknown_tiers = set(suite.keys()) - _KNOWN_TIERS
    if unknown_tiers:
        raise ValueError(
            f"module_03_input contains tier(s) this ingestion layer does not "
            f"recognize: {sorted(unknown_tiers)}. Add explicit handling "
            f"before proceeding."
        )

    properties: list[Property] = []
    excluded: list[ExcludedProperty] = []
    seen: set[tuple[str, str]] = set()
    # Raw formula text -> tier it was first checked under. Some tiers are
    # populated by copying formulas that already live in another
    # conformance-checked tier verbatim (e.g. mutation_refiner.py appends
    # every self-healing killer into both P1_Structural_Control_Flow and
    # synthesized_mutant_killers at synthesis time). Checking the same
    # formula twice under two tier names doesn't add detection power, it
    # just double-counts one violation as two "properties" -- so dedupe by
    # content across tiers, not just within one.
    checked_formula_origin: dict[str, str] = {}

    for tier, formulas in suite.items():
        tier_info = tier_semantics.get(tier)
        if tier_info is None:
            raise ValueError(
                f"tier '{tier}' has properties but no entry in "
                f"tier_semantics -- ingestion has no conformance-check "
                f"policy for it."
            )

        conformance_check = bool(tier_info.get("conformance_check", False))

        for raw in formulas:
            key = (tier, raw)
            if key in seen:
                continue  # exact intra-tier duplicate
            seen.add(key)

            if not conformance_check:
                excluded.append(ExcludedProperty(
                    origin_formula=raw, tier=tier,
                    reason=f"tier_semantics.{tier}.conformance_check is False",
                ))
                continue

            if raw in checked_formula_origin:
                excluded.append(ExcludedProperty(
                    origin_formula=raw, tier=tier,
                    reason=(
                        f"exact duplicate of a property already checked "
                        f"under tier '{checked_formula_origin[raw]}' -- "
                        f"checking it again here would double-count one "
                        f"violation as two, not add new detection power"
                    ),
                ))
                continue

            if _NODE_ATOM_RE.search(raw):
                excluded.append(ExcludedProperty(
                    origin_formula=raw, tier=tier,
                    reason="references a spec-only node(...) atom with no code counterpart",
                ))
                continue

            if tier == "P4_Task_Coverage" and _P4_VACUOUS_CONDITIONAL_RE.match(raw):
                excluded.append(ExcludedProperty(
                    origin_formula=raw, tier=tier,
                    reason=(
                        "conditional task-coverage obligation collapses to a "
                        "tautology (G(\"X\" -> F(\"X\"))) under Option B's "
                        "start/done atom merge -- unfalsifiable, same failure "
                        "mode as P0's excluded sentinels"
                    ),
                ))
                continue

            spot_formula = _to_spot_option_b(raw)
            rejection = _rejects_spot_grammar(spot_formula)
            if rejection is not None:
                excluded.append(ExcludedProperty(
                    origin_formula=raw, tier=tier, reason=rejection,
                ))
                continue

            properties.append(Property(
                formula=spot_formula, origin_formula=raw, tier=tier,
            ))
            checked_formula_origin[raw] = tier

    return PropertySuite(properties, excluded)
