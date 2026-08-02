"""mutate_eval.py -- secondary M01 metric: *discriminative* mutation kills.

The headline finding this module exists to keep visible: a raw
``mutants_killed_ratio`` of 1.0 is not evidence of property-suite strength.
``LTLfAuditor`` kills a mutant whenever it has no complete trace, so a
mutation that severs the graph is scored a kill even though an **empty**
property suite would have "detected" it just as reliably. PR #89 split the
two mechanisms at the source (``classify_kill`` returns
``KILL_BY_PROPERTY`` vs ``KILL_BY_DISCONNECTION``); this module reports them
separately and defines the secondary metric on the property mechanism only:

    discriminative kill ratio = property-mechanism kills / mutants generated

Reporting rule (inherited from the memo, not re-derived): this ratio is
reported **only on diagrams whose suite is sound**. A kill ratio computed
against a suite that already rejects its own unmutated diagram is
uninterpretable -- the suite would "detect" anything, including the truth.
Unsound-suite diagrams are still measured and reported, in a separate
bucket, precisely so the difference stays visible.

Mutant generation uses ``BPMNMutationEngine`` with a fixed seed (42) and
``MUTANTS_PER_DIAGRAM`` = 20, matching Phase 3's own configuration, so the
harness measures the pipeline as it actually runs rather than a variant of
it. The engine already discards behaviourally-equivalent mutants (it
compares canonical trace sets against the original), so the denominator is
"mutants generated", which can fall short of 20 when the engine exhausts
its attempt budget on a small diagram -- that shortfall is recorded per
diagram rather than assumed away.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Sequence

try:  # package import (pytest from the repo root), then script import
    from .gold_bpmn import CORPORA, MODULE01_DIR, corpus_files, gold_label, uid_of
    from .soundness import (
        KNOWN_DUPLICATE_PROPOSITION_DIAGRAMS,
        TRACE_DEPTH,
        first_rejecting_property,
    )
except ImportError:  # pragma: no cover - exercised by direct script run
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from gold_bpmn import CORPORA, MODULE01_DIR, corpus_files, gold_label, uid_of
    from soundness import (
        KNOWN_DUPLICATE_PROPOSITION_DIAGRAMS,
        TRACE_DEPTH,
        first_rejecting_property,
    )

sys.path.insert(0, str(MODULE01_DIR / "src"))

from ltlf_synthesizer import FLTLSynthesizer  # noqa: E402
from mutation_refiner import BPMNMutationEngine, LTLfAuditor  # noqa: E402
from semantic_extractor import SemanticExtractionEngine  # noqa: E402

#: Phase 3's own defaults, so the harness measures the shipped configuration.
MUTANTS_PER_DIAGRAM = 20
SEED = 42

#: Kill-mechanism labels, re-exported from the source of truth so this
#: module can never drift from ``LTLfAuditor``'s own vocabulary.
KILL_BY_PROPERTY = LTLfAuditor.KILL_BY_PROPERTY
KILL_BY_DISCONNECTION = LTLfAuditor.KILL_BY_DISCONNECTION
SURVIVED = "survived"


@dataclass
class DiagramMutationResult:
    """Per-diagram mutation record. One row of the per-diagram CSV."""

    corpus: str
    uid: str
    sound: bool
    has_branch: bool
    mutants_requested: int
    mutants_generated: int
    killed_by_property: int
    killed_by_disconnection: int
    survived: int
    property_kill_tiers: Dict[str, int] = field(default_factory=dict)
    known_duplicate_proposition_class: bool = False

    @property
    def raw_kill_ratio(self) -> float:
        """Kills by ANY mechanism / generated. The misleading 1.0 figure."""
        if not self.mutants_generated:
            return 0.0
        killed = self.killed_by_property + self.killed_by_disconnection
        return killed / self.mutants_generated

    @property
    def discriminative_kill_ratio(self) -> float:
        """Property-mechanism kills / generated. The interpretable figure."""
        if not self.mutants_generated:
            return 0.0
        return self.killed_by_property / self.mutants_generated


def evaluate_diagram(path: Path, corpus: str) -> DiagramMutationResult:
    """Generate mutants for one diagram and classify each kill by mechanism."""
    xml_text = Path(path).read_text(encoding="utf-8")
    gold = gold_label(xml_text)
    uid = uid_of(path)

    extraction = SemanticExtractionEngine(xml_text).run_pipeline()
    graph = extraction["semantic_graph"]
    suite = FLTLSynthesizer(extraction).run_pipeline()["ltlf_property_suite"]
    auditor = LTLfAuditor(suite)

    sound = not auditor.classify_kill(graph)[0]

    engine = BPMNMutationEngine(graph)
    mutants = engine.generate_mutants(count=MUTANTS_PER_DIAGRAM, seed=SEED)

    result = DiagramMutationResult(
        corpus=corpus,
        uid=uid,
        sound=sound,
        has_branch=bool(gold["has_branch"]),
        mutants_requested=MUTANTS_PER_DIAGRAM,
        mutants_generated=len(mutants),
        killed_by_property=0,
        killed_by_disconnection=0,
        survived=0,
        known_duplicate_proposition_class=(corpus, uid)
        in KNOWN_DUPLICATE_PROPOSITION_DIAGRAMS,
    )

    for mutant in mutants:
        killed, mechanism, _detail = auditor.classify_kill(mutant)
        if not killed:
            result.survived += 1
        elif mechanism == KILL_BY_PROPERTY:
            result.killed_by_property += 1
            traces = auditor._generate_traces(mutant, depth=TRACE_DEPTH)
            hit = first_rejecting_property(suite, traces)
            if hit is not None:
                tier = hit[0]
                result.property_kill_tiers[tier] = (
                    result.property_kill_tiers.get(tier, 0) + 1
                )
        else:
            result.killed_by_disconnection += 1

    return result


def run_corpus(corpus: str) -> List[DiagramMutationResult]:
    """Mutation results for every diagram of one corpus."""
    return [evaluate_diagram(path, corpus) for path in corpus_files(corpus)]


def run_all() -> Dict[str, List[DiagramMutationResult]]:
    """Mutation results for both corpora, reported separately."""
    return {corpus: run_corpus(corpus) for corpus in CORPORA}


def summarize(results: Sequence[DiagramMutationResult]) -> Dict[str, Any]:
    """Mutant-level totals, split by suite soundness and by branch."""

    def _bucket(rows: Sequence[DiagramMutationResult]) -> Dict[str, int]:
        return {
            "diagrams": len(rows),
            "mutants": sum(r.mutants_generated for r in rows),
            "killed_by_property": sum(r.killed_by_property for r in rows),
            "killed_by_disconnection": sum(r.killed_by_disconnection for r in rows),
            "survived": sum(r.survived for r in rows),
        }

    sound_rows = [r for r in results if r.sound]
    unsound_rows = [r for r in results if not r.sound]
    return {
        "all": _bucket(results),
        "sound_suite": _bucket(sound_rows),
        "unsound_suite": _bucket(unsound_rows),
        "sound_branch": _bucket([r for r in sound_rows if r.has_branch]),
        "sound_nobranch": _bucket([r for r in sound_rows if not r.has_branch]),
        "shortfall_diagrams": sum(
            1 for r in results if r.mutants_generated < r.mutants_requested
        ),
    }


if __name__ == "__main__":  # pragma: no cover - manual smoke run
    for corpus_name, rows in run_all().items():
        stats = summarize(rows)
        sound = stats["sound_suite"]
        print(
            "%-8s sound-suite mutants=%d  property_kills=%d  disconnection=%d  survived=%d"
            % (
                corpus_name,
                sound["mutants"],
                sound["killed_by_property"],
                sound["killed_by_disconnection"],
                sound["survived"],
            )
        )
