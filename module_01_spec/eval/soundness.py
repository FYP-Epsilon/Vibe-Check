"""soundness.py -- primary M01 evaluation metric: suite soundness.

A synthesised LTLf property suite is **sound** on the diagram it was derived
from iff every property in it holds on every trace of that diagram's own
*unmutated* semantic graph. A suite that rejects its own source diagram
cannot be a faithful formalisation of it, and any mutation-kill figure
computed against such a suite is uninterpretable -- which is why this is the
gate the secondary metric is reported behind (see ``mutate_eval.py``).

Scope statement, carried deliberately (memo Section 4, "the recursive
check"): soundness is computed with M01's *own* trace generator and *own*
LTLf evaluator, so it detects **internal inconsistency** between property
synthesis and execution semantics. It does not establish that the suite
faithfully formalises the BPMN diagram's intended meaning -- that needs an
external oracle. What rescues it from vacuity is that it is not a
fixed-point check: the synthesiser instantiates templates over node types
while the trace generator enumerates paths, so agreement is a real
constraint, and empirically the check *fails* on identifiable diagrams
rather than returning 1.0 by construction.

Unlike the pilot scripts this harness replaces, **no property is filtered
out of the suite here.** The pilots stripped the ``/* loop_bound=10 */``
P2 property because it was unparseable by M01's own evaluator; PR #89 fixed
that at the source by moving the bound to a typed ``spec_metadata`` field.
Filtering is therefore no longer correct: it would hide a regression of that
defect. Instead every property is parse-probed and unparseable ones are
counted and reported as a *separate defect count*, never silently dropped
(memo Section 5: "drop unparseable properties (logging them as a separate
defect count, never silently)" -- the count is now expected to be zero, and
a non-zero value is a finding, not a filter trigger).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:  # package import (pytest from the repo root), then script import
    from .gold_bpmn import CORPORA, MODULE01_DIR, corpus_files, gold_label, uid_of
except ImportError:  # pragma: no cover - exercised by `python eval/soundness.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from gold_bpmn import CORPORA, MODULE01_DIR, corpus_files, gold_label, uid_of

# The harness evaluates the system under test, so importing from src/ is
# correct *here* -- the anti-circularity rule binds gold_bpmn.py alone.
sys.path.insert(0, str(MODULE01_DIR / "src"))

from ltlf_eval import evaluate_ltlf  # noqa: E402
from ltlf_synthesizer import FLTLSynthesizer  # noqa: E402
from mutation_refiner import LTLfAuditor  # noqa: E402
from semantic_extractor import SemanticExtractionEngine  # noqa: E402

#: Trace-generation depth. Matches LTLfAuditor.classify_kill's own call, so
#: soundness is judged against exactly the traces the auditor would use.
TRACE_DEPTH = 10

#: Diagrams the design memo scoped out as a *distinct defect class*: two
#: task node-ids collapsing onto one atomic proposition, which makes a P1
#: ordering property self-contradictory. Not excluded from any denominator
#: -- labelled, so the two defect classes are never conflated. See the
#: harness report for the hard-exclusion vs labelled-bucket decision.
KNOWN_DUPLICATE_PROPOSITION_DIAGRAMS = {
    ("output", "uid_67"),
    ("output", "uid_8"),
    ("context", "uid_92"),
}


@dataclass
class DiagramSoundness:
    """Per-diagram soundness record. One row of the per-diagram CSV."""

    corpus: str
    uid: str
    path: str
    sound: bool
    has_branch: bool
    n_nodes: int
    n_edges: int
    n_traces: int
    n_properties: int
    properties_by_tier: Dict[str, int] = field(default_factory=dict)
    rejecting_tier: Optional[str] = None
    rejecting_property: Optional[str] = None
    unparseable_properties: List[str] = field(default_factory=list)
    duplicate_proposition_names: Dict[str, List[str]] = field(default_factory=dict)
    known_duplicate_proposition_class: bool = False
    extraction_error: Optional[str] = None

    @property
    def n_unparseable(self) -> int:
        return len(self.unparseable_properties)


def _flatten_suite(suite: Dict[str, List[str]]) -> List[Tuple[str, str]]:
    """Suite dict -> [(tier, property)], in LTLfAuditor's own iteration order.

    LTLfAuditor.__init__ extends self.properties by iterating
    ``property_suite.values()``, so preserving dict order here keeps this
    module's tier attribution consistent with the auditor's verdict.
    """
    return [(tier, prop) for tier, props in suite.items() for prop in props]


def find_unparseable(
    suite: Dict[str, List[str]], probe_trace: Sequence[Any]
) -> List[str]:
    """Properties M01's own evaluator cannot parse.

    Reported as a defect count, never used to filter the suite. Parse
    failure is distinguished from a property that merely evaluates False:
    ``evaluate_ltlf`` raises on the former and returns a bool on the latter,
    whereas ``LTLfAuditor._evaluate`` collapses both to False.
    """
    unparseable: List[str] = []
    for _tier, prop in _flatten_suite(suite):
        try:
            evaluate_ltlf(prop, list(probe_trace))
        except Exception:
            unparseable.append(prop)
    return unparseable


def first_rejecting_property(
    suite: Dict[str, List[str]], traces: Sequence[Sequence[Any]]
) -> Optional[Tuple[str, str]]:
    """First ``(tier, property)`` that fails on some trace, else ``None``.

    Mirrors ``LTLfAuditor.classify_kill``'s trace-major / property-minor
    scan order so the property named here is the one that actually drove the
    auditor's verdict, and treats a parse exception as a failure exactly as
    ``LTLfAuditor._evaluate`` does.
    """
    flat = _flatten_suite(suite)
    for trace in traces:
        for tier, prop in flat:
            try:
                holds = evaluate_ltlf(prop, list(trace))
            except Exception:
                holds = False
            if not holds:
                return tier, prop
    return None


def evaluate_diagram(path: Path, corpus: str) -> DiagramSoundness:
    """Synthesise a suite for one diagram and test it against that diagram."""
    xml_text = Path(path).read_text(encoding="utf-8")
    gold = gold_label(xml_text)
    uid = uid_of(path)

    record = DiagramSoundness(
        corpus=corpus,
        uid=uid,
        path=str(Path(path).relative_to(MODULE01_DIR.parent)),
        sound=False,
        has_branch=bool(gold["has_branch"]),
        n_nodes=len(gold["nodes"]),
        n_edges=len(gold["edges"]),
        n_traces=0,
        n_properties=0,
        duplicate_proposition_names={
            k: list(v) for k, v in gold["duplicate_names"].items()
        },
        known_duplicate_proposition_class=(corpus, uid)
        in KNOWN_DUPLICATE_PROPOSITION_DIAGRAMS,
    )

    try:
        extraction = SemanticExtractionEngine(xml_text).run_pipeline()
        graph = extraction["semantic_graph"]
        suite = FLTLSynthesizer(extraction).run_pipeline()["ltlf_property_suite"]
    except Exception as exc:  # pragma: no cover - no corpus diagram hits this
        record.extraction_error = "%s: %s" % (type(exc).__name__, exc)
        return record

    auditor = LTLfAuditor(suite)
    traces = auditor._generate_traces(graph, depth=TRACE_DEPTH)

    record.n_traces = len(traces)
    record.n_properties = sum(len(v) for v in suite.values())
    record.properties_by_tier = {tier: len(props) for tier, props in suite.items()}
    record.unparseable_properties = find_unparseable(
        suite, traces[0] if traces else []
    )

    # The auditor's own verdict is the definition of soundness: the suite is
    # sound iff it does NOT kill the unmutated graph. classify_kill is used
    # rather than is_killed so a disconnected original (which no FLOW-BENCH
    # diagram is) could never be misread as a property rejection.
    killed, mechanism, _detail = auditor.classify_kill(graph)
    record.sound = not killed

    if killed and mechanism == LTLfAuditor.KILL_BY_PROPERTY:
        hit = first_rejecting_property(suite, traces)
        if hit is not None:
            record.rejecting_tier, record.rejecting_property = hit
    elif killed:
        record.rejecting_tier = mechanism

    return record


def run_corpus(corpus: str) -> List[DiagramSoundness]:
    """Soundness for every diagram of one corpus."""
    return [evaluate_diagram(path, corpus) for path in corpus_files(corpus)]


def run_all() -> Dict[str, List[DiagramSoundness]]:
    """Soundness for both corpora, reported separately (never pooled)."""
    return {corpus: run_corpus(corpus) for corpus in CORPORA}


def summarize(records: Sequence[DiagramSoundness]) -> Dict[str, Any]:
    """Counts for a set of records, stratified by branch/no-branch."""
    branch = [r for r in records if r.has_branch]
    nobranch = [r for r in records if not r.has_branch]
    return {
        "n": len(records),
        "sound": sum(1 for r in records if r.sound),
        "branch_n": len(branch),
        "branch_sound": sum(1 for r in branch if r.sound),
        "nobranch_n": len(nobranch),
        "nobranch_sound": sum(1 for r in nobranch if r.sound),
        "unparseable_properties": sum(r.n_unparseable for r in records),
        "extraction_errors": sum(1 for r in records if r.extraction_error),
    }


if __name__ == "__main__":  # pragma: no cover - manual smoke run
    for corpus_name, rows in run_all().items():
        stats = summarize(rows)
        print(
            "%-8s sound %d/%d  (branch %d/%d, no-branch %d/%d)  unparseable=%d"
            % (
                corpus_name,
                stats["sound"],
                stats["n"],
                stats["branch_sound"],
                stats["branch_n"],
                stats["nobranch_sound"],
                stats["nobranch_n"],
                stats["unparseable_properties"],
            )
        )
