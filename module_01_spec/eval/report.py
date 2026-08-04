"""report.py -- run the M01 FLOW-BENCH harness and emit report + CSVs.

Usage (from the repo root, with the project venv):

    python module_01_spec/eval/report.py

Writes, all under ``module_01_spec/eval/results/``:

    m01_eval_report.md        the report
    soundness_per_diagram.csv one row per diagram (148 rows)
    mutation_per_diagram.csv  one row per diagram (148 rows)
    structural_per_diagram.csv one row per diagram (148 rows)

Statistical conventions are inherited from Module 02's eval, not
re-derived: exact Clopper-Pearson binomial intervals at alpha = 0.05,
computed without scipy (``module_02_extract/eval/calibrate.py`` established
the no-scipy constraint and this is the same algorithm, re-implemented here
rather than cross-imported so the two modules stay independently runnable).

The two corpora are reported **separately and never pooled**: 47 uids occur
in both ``output`` and ``context``, so a pooled interval would double-count
related diagrams and violate the independence assumption a binomial
interval rests on. ``context`` functions as a held-out replication set.

Every rate is additionally stratified by branch / no-branch, because
branching is the dominant structural covariate for both metrics: branch-free
diagrams admit a single trace, which makes universally-quantified properties
much easier to satisfy, so an unstratified rate mostly reports the corpus's
branch mix rather than the engine's behaviour.
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

try:  # package import (pytest from the repo root), then script import
    from . import gold_bpmn, mutate_eval, soundness
    from .gold_bpmn import (
        CORPORA,
        MODULE01_DIR,
        RESULTS_DIR,
        aggregate_scores,
        corpus_files,
        gold_label,
        score_sets,
        uid_of,
    )
except ImportError:  # pragma: no cover - exercised by direct script run
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import gold_bpmn  # type: ignore[no-redef]
    import mutate_eval  # type: ignore[no-redef]
    import soundness  # type: ignore[no-redef]
    from gold_bpmn import (  # type: ignore[no-redef]
        CORPORA,
        MODULE01_DIR,
        RESULTS_DIR,
        aggregate_scores,
        corpus_files,
        gold_label,
        score_sets,
        uid_of,
    )

sys.path.insert(0, str(MODULE01_DIR / "src"))

from semantic_extractor import SemanticExtractionEngine  # noqa: E402

ALPHA = 0.05  # 95% confidence intervals, matching module_02_extract/eval


# ----------------------------------------------------------------------
# Exact binomial CDF + Clopper-Pearson interval (no scipy dependency)
# ----------------------------------------------------------------------


def _binom_sf_ge(n: int, p: float, x: int) -> float:
    """P(X >= x) for X ~ Binomial(n, p)."""
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(x, n + 1))


def _binom_cdf_le(n: int, p: float, x: int) -> float:
    """P(X <= x) for X ~ Binomial(n, p)."""
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, x + 1))


def clopper_pearson(
    successes: int, n: int, alpha: float = ALPHA
) -> Tuple[float, float]:
    """Exact two-sided (1-alpha) binomial interval, via bisection on the CDF."""
    if n == 0:
        return (0.0, 1.0)

    if successes == 0:
        lo = 0.0
    else:
        lo_lo, lo_hi = 0.0, 1.0
        target = alpha / 2
        for _ in range(100):
            mid = (lo_lo + lo_hi) / 2
            if _binom_sf_ge(n, mid, successes) > target:
                lo_hi = mid
            else:
                lo_lo = mid
        lo = (lo_lo + lo_hi) / 2

    if successes == n:
        hi = 1.0
    else:
        hi_lo, hi_hi = 0.0, 1.0
        target = alpha / 2
        for _ in range(100):
            mid = (hi_lo + hi_hi) / 2
            if _binom_cdf_le(n, mid, successes) > target:
                hi_lo = mid
            else:
                hi_hi = mid
        hi = (hi_lo + hi_hi) / 2

    return (lo, hi)


def rate_cell(successes: int, n: int) -> str:
    """``k/n = 0.9800 [0.9296, 0.9976]`` -- a rate never printed bare."""
    if n == 0:
        return "n/a (n=0)"
    lo, hi = clopper_pearson(successes, n)
    return "%d/%d = %.4f [%.4f, %.4f]" % (successes, n, successes / n, lo, hi)


# ----------------------------------------------------------------------
# Structural fidelity: extractor vs the independent gold labeler
# ----------------------------------------------------------------------


def structural_row(path: Path, corpus: str) -> Dict[str, Any]:
    """Node/edge P/R/F1 for one diagram, extractor vs gold_bpmn."""
    xml_text = Path(path).read_text(encoding="utf-8")
    gold = gold_label(xml_text)
    extraction = SemanticExtractionEngine(xml_text).run_pipeline()
    graph = extraction["semantic_graph"]

    got_nodes = {(s["node_id"], s["node_type"]) for s in graph["states"]}
    got_edges = {
        (e.get("flow_id"), e["source_id"], e["target_id"]) for e in graph["edges"]
    }

    node_scores = score_sets(gold["nodes"], got_nodes)
    edge_scores = score_sets(gold["edges"], got_edges)
    return {
        "corpus": corpus,
        "uid": uid_of(path),
        "has_branch": bool(gold["has_branch"]),
        "gold_nodes": len(gold["nodes"]),
        "gold_edges": len(gold["edges"]),
        "node": node_scores,
        "edge": edge_scores,
        "node_exact": node_scores["fp"] == 0 and node_scores["fn"] == 0,
        "edge_exact": edge_scores["fp"] == 0 and edge_scores["fn"] == 0,
    }


def run_structural() -> Dict[str, List[Dict[str, Any]]]:
    return {c: [structural_row(p, c) for p in corpus_files(c)] for c in CORPORA}


def corpus_overlap() -> Dict[str, Any]:
    """How much of ``context`` is genuinely new relative to ``output``.

    The memo describes ``context`` as a held-out replication set. That is
    right about why the corpora must not be pooled, but the overlap is
    large enough that "held-out" would overstate the corroboration on
    offer, so the harness computes the split and the report states it.
    """
    output_uids = {uid_of(p) for p in corpus_files("output")}
    context_uids = {uid_of(p) for p in corpus_files("context")}
    return {
        "output_n": len(output_uids),
        "context_n": len(context_uids),
        "shared": len(output_uids & context_uids),
        "output_only": sorted(output_uids - context_uids),
        "context_only": sorted(context_uids - output_uids),
    }


def construct_census() -> Tuple[List[Tuple[str, int]], List[str]]:
    """Which BPMN flow-node types the corpus actually exercises.

    Bounds how far a perfect structural score generalises: a type absent
    from every diagram is a type the metric says nothing about. Computed,
    not recalled, so the report cannot drift from the corpus.
    """
    counts: Dict[str, int] = {}
    for corpus in CORPORA:
        for path in corpus_files(corpus):
            for _node_id, node_type in gold_label(
                path.read_text(encoding="utf-8")
            )["nodes"]:
                counts[node_type] = counts.get(node_type, 0) + 1
    present = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    absent = sorted(gold_bpmn.SPEC_FLOW_NODES - set(counts))
    return present, absent


# ----------------------------------------------------------------------
# Open question: subProcess flattening (memo Section 6)
# ----------------------------------------------------------------------


def _flattened_gold_nodes(xml_text: str) -> set:
    """Gold node set under the ALTERNATIVE convention: a ``subProcess``
    wrapper is not itself a node, though its children still are."""
    root = ET.fromstring(xml_text)
    nodes = set()
    for elem in root.iter():
        if not elem.tag.startswith("{%s}" % gold_bpmn.BPMN_NS):
            continue
        tag = elem.tag.split("}")[-1]
        if tag in gold_bpmn.SPEC_FLOW_NODES and elem.get("id") and tag != "subProcess":
            nodes.add((elem.get("id"), tag))
    return nodes


def subprocess_sensitivity() -> Dict[str, Any]:
    """Measure -- not assert -- what the subProcess convention costs.

    The memo left "flatten a subProcess into its children, or count the
    wrapper as a node?" open. It is tempting to note that the corpus is
    small and call the question inert; it is not. 58 of 148 diagrams carry a
    ``subProcess``, so the harness answers by computing node F1 under BOTH
    conventions and reporting the difference.

    The convention actually adopted (wrapper counts) is chosen on BPMN 2.0
    grounds, not on which number it produces: in the standard's class
    hierarchy ``SubProcess`` is a subclass of ``Activity``, which is a
    subclass of ``FlowNode``, so a subProcess *is* a flow node. Dropping it
    would be a departure from the standard the labeler claims to transcribe.
    """
    tag = "{%s}subProcess" % gold_bpmn.BPMN_NS
    affected = 0
    total = 0
    wrappers = 0
    current_rows: List[Dict[str, float]] = []
    flattened_rows: List[Dict[str, float]] = []

    for corpus in CORPORA:
        for path in corpus_files(corpus):
            total += 1
            xml_text = path.read_text(encoding="utf-8")
            root = ET.fromstring(xml_text)
            found = root.findall(".//%s" % tag)
            if found:
                affected += 1
                wrappers += len(found)

            got_nodes = {
                (s["node_id"], s["node_type"])
                for s in SemanticExtractionEngine(xml_text)
                .run_pipeline()["semantic_graph"]["states"]
            }
            current_rows.append(score_sets(gold_label(xml_text)["nodes"], got_nodes))
            flattened_rows.append(score_sets(_flattened_gold_nodes(xml_text), got_nodes))

    return {
        "diagrams_with_subprocess": affected,
        "diagrams_total": total,
        "subprocess_wrappers": wrappers,
        "current": aggregate_scores(current_rows),
        "flattened": aggregate_scores(flattened_rows),
    }


# ----------------------------------------------------------------------
# CSV emission -- per-diagram persistence, so any aggregate is auditable
# ----------------------------------------------------------------------


def write_soundness_csv(
    per_corpus: Dict[str, List[soundness.DiagramSoundness]], out: Path
) -> None:
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "corpus",
                "uid",
                "sound",
                "has_branch",
                "n_nodes",
                "n_edges",
                "n_traces",
                "n_properties",
                "properties_by_tier",
                "rejecting_tier",
                "rejecting_property",
                "n_unparseable",
                "duplicate_proposition_names",
                "known_duplicate_proposition_class",
                "extraction_error",
            ]
        )
        for corpus in CORPORA:
            for r in per_corpus[corpus]:
                writer.writerow(
                    [
                        r.corpus,
                        r.uid,
                        int(r.sound),
                        int(r.has_branch),
                        r.n_nodes,
                        r.n_edges,
                        r.n_traces,
                        r.n_properties,
                        json.dumps(r.properties_by_tier, sort_keys=True),
                        r.rejecting_tier or "",
                        r.rejecting_property or "",
                        r.n_unparseable,
                        json.dumps(r.duplicate_proposition_names, sort_keys=True),
                        int(r.known_duplicate_proposition_class),
                        r.extraction_error or "",
                    ]
                )


def write_mutation_csv(
    per_corpus: Dict[str, List[mutate_eval.DiagramMutationResult]], out: Path
) -> None:
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "corpus",
                "uid",
                "sound",
                "has_branch",
                "mutants_requested",
                "mutants_generated",
                "killed_by_property",
                "killed_by_disconnection",
                "survived",
                "raw_kill_ratio",
                "discriminative_kill_ratio",
                "property_kill_tiers",
            ]
        )
        for corpus in CORPORA:
            for r in per_corpus[corpus]:
                writer.writerow(
                    [
                        r.corpus,
                        r.uid,
                        int(r.sound),
                        int(r.has_branch),
                        r.mutants_requested,
                        r.mutants_generated,
                        r.killed_by_property,
                        r.killed_by_disconnection,
                        r.survived,
                        "%.4f" % r.raw_kill_ratio,
                        "%.4f" % r.discriminative_kill_ratio,
                        json.dumps(r.property_kill_tiers, sort_keys=True),
                    ]
                )


def write_structural_csv(
    per_corpus: Dict[str, List[Dict[str, Any]]], out: Path
) -> None:
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "corpus",
                "uid",
                "has_branch",
                "gold_nodes",
                "gold_edges",
                "node_tp",
                "node_fp",
                "node_fn",
                "node_f1",
                "edge_tp",
                "edge_fp",
                "edge_fn",
                "edge_f1",
            ]
        )
        for corpus in CORPORA:
            for r in per_corpus[corpus]:
                writer.writerow(
                    [
                        r["corpus"],
                        r["uid"],
                        int(r["has_branch"]),
                        r["gold_nodes"],
                        r["gold_edges"],
                        r["node"]["tp"],
                        r["node"]["fp"],
                        r["node"]["fn"],
                        "%.4f" % r["node"]["f1"],
                        r["edge"]["tp"],
                        r["edge"]["fp"],
                        r["edge"]["fn"],
                        "%.4f" % r["edge"]["f1"],
                    ]
                )


# ----------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(MODULE01_DIR.parent),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:  # pragma: no cover - git absent
        return "unknown"


def build_report(
    sound_per_corpus: Dict[str, List[soundness.DiagramSoundness]],
    mut_per_corpus: Dict[str, List[mutate_eval.DiagramMutationResult]],
    struct_per_corpus: Dict[str, List[Dict[str, Any]]],
) -> str:
    lines: List[str] = []
    add = lines.append

    commit = _git("rev-parse", "--short", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    add("# Module 01 FLOW-BENCH evaluation report")
    add("")
    add(
        "Generated by `module_01_spec/eval/report.py` on %s, at `%s @ %s`, "
        "seed %d, %d mutants/diagram." % (stamp, branch, commit, mutate_eval.SEED,
                                          mutate_eval.MUTANTS_PER_DIAGRAM)
    )
    add("")
    add(
        "All intervals are exact Clopper-Pearson binomial intervals at "
        "alpha = %.2f. Every rate is stratified by branch / no-branch, the "
        "dominant structural covariate: branch-free diagrams admit a single "
        "trace, which makes universally-quantified properties far easier to "
        "satisfy, so an unstratified rate largely reports the corpus's branch "
        "mix rather than the engine's behaviour." % ALPHA
    )
    add("")
    overlap = corpus_overlap()
    add(
        "**The two corpora are reported separately and never pooled.** %d "
        "uids occur in both `output` and `context`, so pooling would "
        "double-count related diagrams and violate the independence "
        "assumption a binomial interval rests on."
        % overlap["shared"]
    )
    add("")
    add(
        "One caveat on how far `context` corroborates `output`, stated "
        "because the overlap is large enough to matter: only **%d of %d** "
        "`context` uids (%s) is absent from `output`. `context` is therefore "
        "a *paired near-replicate* -- the same %d workflows rendered as "
        "context diagrams -- not an independently sampled held-out set. "
        "Agreement between the two columns is evidence that a result is "
        "stable across two renderings of the same workflows; it is **not** "
        "evidence of generalisation to unseen workflows."
        % (
            len(overlap["context_only"]),
            overlap["context_n"],
            ", ".join("`%s`" % u for u in overlap["context_only"]),
            overlap["shared"],
        )
    )
    add("")

    # -- Metric 0: structural fidelity ---------------------------------
    add("## 0. Structural fidelity (extractor vs. independent gold labeler)")
    add("")
    add(
        "Gold labels come from `eval/gold_bpmn.py`, which reads the BPMN XML "
        "directly and never imports `src/` (enforced by an import-scan test). "
        "Its node vocabulary is an allowlist transcribed from the BPMN 2.0 "
        "flow-node taxonomy, not a copy of the extractor's `EXECUTABLE_NODES` "
        "nor a complement of its `NON_NODE_TAGS` -- the memo's first labeler "
        "did the latter, which made agreement partly definitional."
    )
    add("")
    add("| corpus | diagrams | node F1 | edge F1 | diagrams node-exact | diagrams edge-exact |")
    add("|---|---|---|---|---|---|")
    for corpus in CORPORA:
        rows = struct_per_corpus[corpus]
        node_agg = aggregate_scores([r["node"] for r in rows])
        edge_agg = aggregate_scores([r["edge"] for r in rows])
        add(
            "| %s | %d | %.4f | %.4f | %s | %s |"
            % (
                corpus,
                len(rows),
                node_agg["f1"],
                edge_agg["f1"],
                rate_cell(sum(1 for r in rows if r["node_exact"]), len(rows)),
                rate_cell(sum(1 for r in rows if r["edge_exact"]), len(rows)),
            )
        )
    add("")
    add(
        "**A perfect score is a claim about the metric as much as about the "
        "extractor, so it was checked for vacuity rather than reported as "
        "found.** `eval/test_gold_bpmn.py::TestMetricIsNotVacuous` injects "
        "known defects into the XML the extractor sees while holding the gold "
        "labels pinned to the pristine document: deleting one task drives "
        "recall below 1.0, retyping one task drives both precision and recall "
        "below 1.0. The metric can therefore score lower and does not on this "
        "corpus. Read it as: on FLOW-BENCH's constructs the extractor loses "
        "nothing and invents nothing -- **not** as evidence that it handles "
        "BPMN constructs this corpus does not exercise."
    )
    add("")
    present, absent = construct_census()
    add(
        "The construct census bounds that generalisation, and is computed "
        "from the corpus rather than recalled. Flow-node types **present**: "
        "%s. Types in the gold vocabulary **absent from all %d diagrams**, "
        "about which this metric says nothing: %s."
        % (
            ", ".join("`%s` (%d)" % (t, n) for t, n in present),
            sum(len(corpus_files(c)) for c in CORPORA),
            ", ".join("`%s`" % t for t in absent),
        )
    )
    add("")

    # -- Metric 1: soundness -------------------------------------------
    add("## 1. Suite soundness (primary metric)")
    add("")
    add(
        "A suite is **sound** on its own diagram iff every synthesised "
        "property holds on every trace of that diagram's unmutated semantic "
        "graph. A suite that rejects its own source diagram cannot be a "
        "faithful formalisation of it."
    )
    add("")
    add("| corpus | all | branch | no-branch |")
    add("|---|---|---|---|")
    for corpus in CORPORA:
        s = soundness.summarize(sound_per_corpus[corpus])
        add(
            "| %s | %s | %s | %s |"
            % (
                corpus,
                rate_cell(s["sound"], s["n"]),
                rate_cell(s["branch_sound"], s["branch_n"]),
                rate_cell(s["nobranch_sound"], s["nobranch_n"]),
            )
        )
    add("")

    unsound = [
        r
        for corpus in CORPORA
        for r in sound_per_corpus[corpus]
        if not r.sound
    ]
    add("### Unsound suites, individually")
    add("")
    if not unsound:
        add("None.")
    else:
        add("| corpus | uid | branch | rejecting tier | duplicate-proposition class |")
        add("|---|---|---|---|---|")
        for r in unsound:
            add(
                "| %s | %s | %s | %s | %s |"
                % (
                    r.corpus,
                    r.uid,
                    "yes" if r.has_branch else "no",
                    r.rejecting_tier or "-",
                    "yes" if r.known_duplicate_proposition_class else "no",
                )
            )
    add("")

    total_unparseable = sum(
        r.n_unparseable for corpus in CORPORA for r in sound_per_corpus[corpus]
    )
    add(
        "**Unparseable properties: %d.** Counted, never filtered. The memo's "
        "pilot scripts stripped the `/* loop_bound=10 */` P2 property because "
        "M01's own evaluator could not parse it; PR #89 fixed that at source "
        "by moving the bound to a typed `spec_metadata` field, so filtering "
        "would now hide a regression of that defect rather than work around "
        "it. A non-zero count here is a finding, not a filter trigger."
        % total_unparseable
    )
    add("")

    # -- Metric 2: discriminative kills --------------------------------
    add("## 2. Discriminative mutation kills (secondary metric)")
    add("")
    add(
        "`LTLfAuditor` kills a mutant whenever it has no complete trace, so a "
        "mutation that severs the graph scores a kill that an **empty** "
        "property suite would have scored too. Only the property mechanism "
        "measures suite strength. Reported on sound-suite diagrams only: a "
        "kill ratio computed against a suite that already rejects its own "
        "unmutated diagram is uninterpretable."
    )
    add("")
    add(
        "| corpus | bucket | diagrams | mutants | property kills | disconnection kills | survived |"
    )
    add("|---|---|---|---|---|---|---|")
    for corpus in CORPORA:
        stats = mutate_eval.summarize(mut_per_corpus[corpus])
        for label, key in (
            ("sound suite", "sound_suite"),
            ("unsound suite", "unsound_suite"),
        ):
            b = stats[key]
            add(
                "| %s | %s | %d | %d | %d | %d | %d |"
                % (
                    corpus,
                    label,
                    b["diagrams"],
                    b["mutants"],
                    b["killed_by_property"],
                    b["killed_by_disconnection"],
                    b["survived"],
                )
            )
    add("")

    add("### Discriminative kill ratio, sound-suite diagrams only")
    add("")
    add("| corpus | stratum | discriminative kill ratio |")
    add("|---|---|---|")
    for corpus in CORPORA:
        stats = mutate_eval.summarize(mut_per_corpus[corpus])
        for label, key in (
            ("all sound", "sound_suite"),
            ("sound + branch", "sound_branch"),
            ("sound + no-branch", "sound_nobranch"),
        ):
            b = stats[key]
            add(
                "| %s | %s | %s |"
                % (corpus, label, rate_cell(b["killed_by_property"], b["mutants"]))
            )
    add("")

    grand_sound_mutants = sum(
        mutate_eval.summarize(mut_per_corpus[c])["sound_suite"]["mutants"]
        for c in CORPORA
    )
    grand_prop_kills = sum(
        mutate_eval.summarize(mut_per_corpus[c])["sound_suite"]["killed_by_property"]
        for c in CORPORA
    )
    add(
        "Across both corpora, **%d of %d** mutants on sound-suite diagrams "
        "were killed by a property. The raw `mutants_killed_ratio` the Phase 3 "
        "gate consumes reads far higher because it counts disconnection kills; "
        "this row is the part that is evidence of property-suite strength."
        % (grand_prop_kills, grand_sound_mutants)
    )
    add("")
    unsound_prop_kills = [
        r
        for corpus in CORPORA
        for r in mut_per_corpus[corpus]
        if not r.sound and r.killed_by_property
    ]
    if unsound_prop_kills:
        add(
            "The unsound-suite rows are reported for completeness and must "
            "**not** be read as detections -- %s. Those kills come from the "
            "same P1 property that already rejects the diagram's *unmutated* "
            "graph (see §1), so the mutation is incidental: the suite would "
            "have rejected the original just as readily. A kill is only "
            "evidence when the suite accepts the unmutated diagram, which is "
            "exactly why the discriminative ratio is restricted to sound "
            "suites."
            % "; ".join(
                "`%s` contributes %d of them"
                % (r.uid, r.killed_by_property)
                for r in unsound_prop_kills
            )
        )
        add("")

    # -- Open questions -------------------------------------------------
    add("## 3. Open questions the memo left to the harness")
    add("")
    sp = subprocess_sensitivity()
    add(
        "**subProcess flattening.** Decided: a `subProcess` counts as one "
        "node *and* its children are counted too (the walk is recursive), "
        "matching the extractor's `.//` traversal."
    )
    add("")
    add(
        "This convention is **load-bearing, not cosmetic**, so it is measured "
        "rather than asserted: %d of %d diagrams carry a `subProcess` (%d "
        "wrappers in total). Node F1 under the adopted convention is **%.4f** "
        "(fp=%d, fn=%d); under the alternative -- wrapper dropped, children "
        "kept -- it would be **%.4f** (fp=%d, fn=%d)."
        % (
            sp["diagrams_with_subprocess"],
            sp["diagrams_total"],
            sp["subprocess_wrappers"],
            sp["current"]["f1"],
            sp["current"]["fp"],
            sp["current"]["fn"],
            sp["flattened"]["f1"],
            sp["flattened"]["fp"],
            sp["flattened"]["fn"],
        )
    )
    add("")
    add(
        "The adopted convention is the one that scores higher, so the "
        "grounds for it must be independent of that fact. They are: in the "
        "BPMN 2.0 class hierarchy `SubProcess` is a subclass of `Activity`, "
        "which is a subclass of `FlowNode`, so a subProcess *is* a flow node "
        "by the standard this labeler claims to transcribe; dropping it would "
        "be a departure from that standard chosen to suit an outcome. Stated "
        "the other way round: had the alternative been adopted, the %d extra "
        "false positives would be an artifact of the labeling convention, not "
        "an extractor defect -- which is exactly why the choice has to be "
        "argued from the spec and the counterfactual disclosed."
        % sp["flattened"]["fp"]
    )
    add("")
    dup_diagrams = [
        r
        for corpus in CORPORA
        for r in sound_per_corpus[corpus]
        if r.duplicate_proposition_names
    ]
    dup_unsound = [r for r in dup_diagrams if not r.sound]
    add(
        "**Duplicate atomic propositions.** Two activity nodes sharing a name "
        "collapse onto one atomic proposition, which can make a P1 ordering "
        "property self-contradictory. These diagrams are **labelled, not "
        "excluded**: excluding them would quietly raise the soundness rate by "
        "redefining the denominator, which the memo's own discipline forbids. "
        "%d diagrams carry duplicate activity names; %d of those are unsound."
        % (len(dup_diagrams), len(dup_unsound))
    )
    add("")

    # -- Scope ----------------------------------------------------------
    add("## 4. What these numbers do not establish")
    add("")
    add(
        "Soundness is computed with M01's *own* trace generator and *own* "
        "LTLf evaluator. It detects internal inconsistency between property "
        "synthesis and execution semantics; it does **not** establish that a "
        "suite faithfully formalises the diagram's intended meaning, which "
        "would need an external oracle. It is not vacuous -- the synthesiser "
        "instantiates templates over node types while the trace generator "
        "enumerates paths, and the check does fail on identifiable diagrams -- "
        "but it is a consistency check, not a correctness proof."
    )
    add("")
    add(
        "The structural-fidelity numbers are the one metric here graded "
        "against a genuinely external reference (the BPMN XML itself, via a "
        "labeler that cannot import the extractor)."
    )
    add("")
    return "\n".join(lines)


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    sound_per_corpus = soundness.run_all()
    mut_per_corpus = mutate_eval.run_all()
    struct_per_corpus = run_structural()

    write_soundness_csv(sound_per_corpus, RESULTS_DIR / "soundness_per_diagram.csv")
    write_mutation_csv(mut_per_corpus, RESULTS_DIR / "mutation_per_diagram.csv")
    write_structural_csv(struct_per_corpus, RESULTS_DIR / "structural_per_diagram.csv")

    report = build_report(sound_per_corpus, mut_per_corpus, struct_per_corpus)
    (RESULTS_DIR / "m01_eval_report.md").write_text(report, encoding="utf-8")

    total = sum(len(v) for v in sound_per_corpus.values())
    total_sound = sum(
        1 for rows in sound_per_corpus.values() for r in rows if r.sound
    )
    print("diagrams=%d sound=%d" % (total, total_sound))
    print("wrote %s" % (RESULTS_DIR / "m01_eval_report.md"))


if __name__ == "__main__":
    main()
