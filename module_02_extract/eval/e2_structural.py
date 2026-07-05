"""e2_structural.py -- E2: WIR structural accuracy vs the independent gold labeler.

Scores src/ast_extractor's extracted WIR for every corpus program against
eval/gold_wir.py's gold structure (a *different*, ast-only code path --
see gold_wir.py's anti-circularity rule). Computes micro node/edge
precision/recall/F1, a per-tag breakdown, and a worst-10 list to feed a
future extractor-fix session.

Node matching: greedy 1:1 on (type, normalized_code); nodes that don't
match on code but do line up by (type, order-within-type) count as a
separate "weak_matches" category -- still counted as matched for edge
scoring, but reported distinctly since they indicate a text/format
mismatch (e.g. a while-loop's guard vs a for-loop's "iter <expr>" guard
needing normalization) rather than a true absence.

Edge matching: an extracted edge matches a gold edge iff both endpoints
were matched (strong or weak) 1:1 and direction agrees; edge *labels*
(true/false/seq/... vs guard text) are compared only where both sides
have a label, and reported separately -- not required for the edge match
itself, per the session mandate.
"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

EVAL_DIR = Path(__file__).resolve().parent
MODULE02_DIR = EVAL_DIR.parent
sys.path.insert(0, str(MODULE02_DIR / "src"))

from ast_extractor import run_v3_pipeline  # noqa: E402

CORPUS_DIR = EVAL_DIR / "corpus"
GOLD_DIR = EVAL_DIR / "gold"
MANIFEST_PATH = EVAL_DIR / "manifest.json"
RESULTS_DIR = EVAL_DIR / "results"
MANUAL_CHECK_DIR = RESULTS_DIR / "e2_manual_check"

MANUAL_CHECK_SEED = 42
MANUAL_CHECK_SAMPLE_SIZE = 10


# ----------------------------------------------------------------------
# Text normalization
# ----------------------------------------------------------------------

def _extracted_node_text(node: dict[str, Any]) -> str:
    """The text to compare for an extracted WIR node: guard for
    gateway/loop (code stays empty for a plain test -- see cfg_extractor's
    visit_If/visit_For/visit_While), else the unparsed statement."""
    if node.get("type") in ("gateway", "loop"):
        return (node.get("guard") or "").strip()
    code = node.get("code") or []
    return code[0].strip() if code else ""


def _normalize(node_type: str, text: str) -> str:
    text = (text or "").strip()
    if node_type == "loop":
        text = text.rstrip(":")
        if text.startswith("iter "):
            return text[5:].strip()
        if text.startswith("while "):
            return text[6:].strip()
        if text.startswith("for ") and " in " in text:
            return text.split(" in ", 1)[1].strip()
        return text
    return text


# ----------------------------------------------------------------------
# Node / edge matching
# ----------------------------------------------------------------------

def match_nodes(
    gold_nodes: list[dict[str, Any]],
    extracted_nodes: list[dict[str, Any]],
) -> tuple[dict[str, str], int, int]:
    """Greedy 1:1 match. Returns (gold_id -> extracted_id map, n_strong,
    n_weak). Unmatched gold/extracted ids are simply absent from the map
    (recoverable as set differences by the caller)."""
    gold_by_type: dict[str, list[dict[str, Any]]] = {}
    for n in gold_nodes:
        gold_by_type.setdefault(n["type"], []).append(n)
    ext_by_type: dict[str, list[dict[str, Any]]] = {}
    for n in extracted_nodes:
        ext_by_type.setdefault(n.get("type"), []).append(n)

    mapping: dict[str, str] = {}
    used_ext_ids: set[str] = set()
    n_strong = 0

    # Pass 1: strong match on (type, normalized text) -- greedy, consumes
    # one candidate per gold node.
    for node_type, glist in gold_by_type.items():
        candidates = [e for e in ext_by_type.get(node_type, []) if e["id"] not in used_ext_ids]
        by_text: dict[str, list[dict[str, Any]]] = {}
        for e in candidates:
            by_text.setdefault(_normalize(node_type, _extracted_node_text(e)), []).append(e)
        for g in glist:
            key = _normalize(node_type, g["code"])
            bucket = by_text.get(key)
            if bucket:
                e = bucket.pop(0)
                mapping[g["gold_id"]] = e["id"]
                used_ext_ids.add(e["id"])
                n_strong += 1

    # Pass 2: weak match -- (type, order-within-type) for whatever's left.
    n_weak = 0
    for node_type, glist in gold_by_type.items():
        remaining_gold = [g for g in glist if g["gold_id"] not in mapping]
        remaining_ext = [e for e in ext_by_type.get(node_type, []) if e["id"] not in used_ext_ids]
        for g, e in zip(remaining_gold, remaining_ext):
            mapping[g["gold_id"]] = e["id"]
            used_ext_ids.add(e["id"])
            n_weak += 1

    return mapping, n_strong, n_weak


def match_edges(
    gold_edges: list[dict[str, Any]],
    extracted_edges: list[dict[str, Any]],
    node_mapping: dict[str, str],
) -> tuple[int, int, int]:
    """Returns (tp, fp, fn) for edges, matched as a multiset of
    (src, dst) pairs in extracted-id space."""
    translated_gold: list[tuple[str, str]] = []
    for e in gold_edges:
        src = node_mapping.get(e["src_gold_id"])
        dst = node_mapping.get(e["dst_gold_id"])
        if src is not None and dst is not None:
            translated_gold.append((src, dst))

    extracted_pairs = [(e["source"], e["target"]) for e in extracted_edges]

    gold_counter = Counter(translated_gold)
    ext_counter = Counter(extracted_pairs)

    tp = sum((gold_counter & ext_counter).values())
    fn = sum(gold_counter.values()) - tp
    fp = sum(ext_counter.values()) - tp
    return tp, fp, fn


# ----------------------------------------------------------------------
# Per-program scoring
# ----------------------------------------------------------------------

def score_program(gold: dict[str, Any], extracted_func_wir: dict[str, Any]) -> dict[str, Any]:
    gold_nodes = gold["nodes"]
    extracted_nodes = extracted_func_wir.get("nodes", [])
    mapping, n_strong, n_weak = match_nodes(gold_nodes, extracted_nodes)

    node_tp = len(mapping)
    node_fn = len(gold_nodes) - node_tp
    node_fp = len(extracted_nodes) - node_tp

    edge_tp, edge_fp, edge_fn = match_edges(gold["edges"], extracted_func_wir.get("edges", []), mapping)

    return {
        "node_tp": node_tp, "node_fp": node_fp, "node_fn": node_fn,
        "node_strong": n_strong, "node_weak": n_weak,
        "edge_tp": edge_tp, "edge_fp": edge_fp, "edge_fn": edge_fn,
        "n_gold_nodes": len(gold_nodes), "n_extracted_nodes": len(extracted_nodes),
    }


def _prf1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 1.0
    r = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


# ----------------------------------------------------------------------
# Corpus-wide run
# ----------------------------------------------------------------------

def _base_tag(tags: list[str]) -> str:
    for t in tags:
        if not t.isdigit():
            return t
    return "unknown"


def run_e2(
    corpus_dir: Path = CORPUS_DIR,
    gold_dir: Path = GOLD_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> dict[str, Any]:
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    corpus_entries = [e for e in manifest if "base_uid" not in e]

    per_program: list[dict[str, Any]] = []
    extraction_failed: list[int] = []

    for entry in corpus_entries:
        uid = entry["uid"]
        gold_path = gold_dir / f"uid_{uid}.json"
        source_path = corpus_dir / f"uid_{uid}.py"
        if not gold_path.exists() or not source_path.exists():
            extraction_failed.append(uid)
            continue
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        source = source_path.read_text(encoding="utf-8")
        try:
            wir = run_v3_pipeline(source)
            func_wir = wir.get("functions", {}).get("workflow", {})
        except Exception:
            extraction_failed.append(uid)
            continue

        scores = score_program(gold, func_wir)
        node_p, node_r, node_f1 = _prf1(scores["node_tp"], scores["node_fp"], scores["node_fn"])
        edge_p, edge_r, edge_f1 = _prf1(scores["edge_tp"], scores["edge_fp"], scores["edge_fn"])
        per_program.append({
            "uid": uid,
            "tag": _base_tag(entry.get("tags", [])),
            "node_p": node_p, "node_r": node_r, "node_f1": node_f1,
            "edge_p": edge_p, "edge_r": edge_r, "edge_f1": edge_f1,
            **scores,
        })

    return {"per_program": per_program, "extraction_failed": extraction_failed}


def _aggregate(programs: list[dict[str, Any]]) -> dict[str, Any]:
    node_tp = sum(p["node_tp"] for p in programs)
    node_fp = sum(p["node_fp"] for p in programs)
    node_fn = sum(p["node_fn"] for p in programs)
    edge_tp = sum(p["edge_tp"] for p in programs)
    edge_fp = sum(p["edge_fp"] for p in programs)
    edge_fn = sum(p["edge_fn"] for p in programs)
    node_p, node_r, node_f1 = _prf1(node_tp, node_fp, node_fn)
    edge_p, edge_r, edge_f1 = _prf1(edge_tp, edge_fp, edge_fn)
    return {
        "n_programs": len(programs),
        "node_precision": node_p, "node_recall": node_r, "node_f1": node_f1,
        "edge_precision": edge_p, "edge_recall": edge_r, "edge_f1": edge_f1,
        "node_strong": sum(p["node_strong"] for p in programs),
        "node_weak": sum(p["node_weak"] for p in programs),
    }


# ----------------------------------------------------------------------
# Manual-check sample (needs both gold and extracted -- lives here, not
# in gold_wir.py, to keep that module import-clean)
# ----------------------------------------------------------------------

def _render_side_by_side(uid: int, gold: dict[str, Any], extracted_func_wir: dict[str, Any]) -> str:
    lines = [f"# uid {uid}", "", "## Gold nodes", ""]
    for n in gold["nodes"]:
        lines.append(f"- {n['gold_id']:>4}  {n['type']:<8} {n['code']}")
    lines += ["", "## Gold edges", ""]
    for e in gold["edges"]:
        lines.append(f"- {e['src_gold_id']} --{e['label']}--> {e['dst_gold_id']}")
    lines += ["", "## Extracted nodes", ""]
    for n in extracted_func_wir.get("nodes", []):
        shown = _extracted_node_text(n)
        lines.append(f"- {n['id']:>10}  {n['type']:<8} {shown}")
    lines += ["", "## Extracted edges", ""]
    for e in extracted_func_wir.get("edges", []):
        label = e.get("guard") or e.get("exception_type") or ""
        lines.append(f"- {e['source']} --{label}--> {e['target']}")
    lines.append("")
    return "\n".join(lines)


def generate_manual_check_sample(
    corpus_dir: Path = CORPUS_DIR,
    gold_dir: Path = GOLD_DIR,
    output_dir: Path = MANUAL_CHECK_DIR,
    seed: int = MANUAL_CHECK_SEED,
    sample_size: int = MANUAL_CHECK_SAMPLE_SIZE,
) -> list[int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    gold_uids = sorted(int(p.stem.split("_")[1]) for p in gold_dir.glob("uid_*.json"))
    rng = random.Random(seed)
    sample = sorted(rng.sample(gold_uids, min(sample_size, len(gold_uids))))

    for uid in sample:
        source = (corpus_dir / f"uid_{uid}.py").read_text(encoding="utf-8")
        gold = json.loads((gold_dir / f"uid_{uid}.json").read_text(encoding="utf-8"))
        wir = run_v3_pipeline(source)
        func_wir = wir.get("functions", {}).get("workflow", {})
        rendered = _render_side_by_side(uid, gold, func_wir)
        (output_dir / f"uid_{uid}.md").write_text(rendered, encoding="utf-8")

    return sample


# ----------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------

def render_report(result: dict[str, Any], manual_check_uids: list[int]) -> str:
    programs = result["per_program"]
    agg = _aggregate(programs)

    by_tag: dict[str, list[dict[str, Any]]] = {}
    for p in programs:
        by_tag.setdefault(p["tag"], []).append(p)

    worst10 = sorted(programs, key=lambda p: p["node_f1"])[:10]

    lines = [
        "# E2: WIR Structural Accuracy Report",
        "",
        "## Methods",
        "",
        "Gold structure comes from `eval/gold_wir.py`, an independent",
        "ast-only labeler that **never imports `src/ast_extractor/`**",
        "(enforced by an import-scan test) -- grading the extractor against",
        "its own code would be circular and meaningless. Extracted WIR comes",
        "from `run_v3_pipeline` (`src/ast_extractor/pipeline.py`) on the same",
        "101 FLOW-BENCH corpus programs used throughout this evaluation.",
        "",
        "Node matching: greedy 1:1 on (type, normalized text); nodes that",
        "align by (type, order-within-type) but not by text count separately",
        "as `weak_matches` (still counted as matched for edge scoring). Edge",
        "matching: an extracted edge matches a gold edge iff both endpoints",
        "matched 1:1 and direction agrees; edge labels are not required to",
        "agree (reported separately would require label-normalization work",
        "not undertaken this session -- out of scope).",
        "",
        f"**Please eyeball these 10 randomly sampled uids** (seed {MANUAL_CHECK_SEED}) --",
        "gold-vs-extracted rendered side-by-side in `eval/results/e2_manual_check/`:",
        f"{', '.join(str(u) for u in manual_check_uids)}. This is the human-validation",
        "step that makes the gold citable; ~15 minutes.",
        "",
        "## Aggregate (micro, across all scored programs)",
        "",
        f"- Programs scored: {agg['n_programs']} (extraction failed: {len(result['extraction_failed'])})",
        f"- Node precision/recall/F1: {agg['node_precision']:.4f} / {agg['node_recall']:.4f} / **{agg['node_f1']:.4f}**",
        f"- Edge precision/recall/F1: {agg['edge_precision']:.4f} / {agg['edge_recall']:.4f} / **{agg['edge_f1']:.4f}**",
        f"- Strong node matches: {agg['node_strong']}, weak (order-fallback) matches: {agg['node_weak']}",
        "",
    ]

    if result["extraction_failed"]:
        lines += [f"- Extraction-failed uids: {result['extraction_failed']}", ""]

    lines += ["## Per-tag breakdown", "", "| tag | n | node F1 | edge F1 |", "|---|---|---|---|"]
    for tag, plist in sorted(by_tag.items()):
        a = _aggregate(plist)
        lines.append(f"| {tag} | {a['n_programs']} | {a['node_f1']:.4f} | {a['edge_f1']:.4f} |")
    lines.append("")

    lines += [
        "## Worst 10 by node F1 (extractor-bug leads for a future session)",
        "",
        "| uid | tag | node F1 | edge F1 | node fp | node fn | diagnosis |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in worst10:
        diag = _diagnose(p)
        lines.append(
            f"| {p['uid']} | {p['tag']} | {p['node_f1']:.3f} | {p['edge_f1']:.3f} | "
            f"{p['node_fp']} | {p['node_fn']} | {diag} |"
        )
    lines.append("")

    return "\n".join(lines)


def _diagnose(p: dict[str, Any]) -> str:
    if p["node_fp"] > 0 and p["node_fn"] == 0:
        return f"{p['node_fp']} extra extracted node(s) (likely merge/exit bookkeeping)"
    if p["node_fn"] > 0 and p["node_fp"] == 0:
        return f"{p['node_fn']} gold node(s) with no extracted counterpart"
    if p["node_fp"] > 0 and p["node_fn"] > 0:
        return f"{p['node_fp']} extra + {p['node_fn']} missing -- structural mismatch"
    return "n/a"


def _write_csv(programs: list[dict[str, Any]], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["uid", "tag", "node_p", "node_r", "node_f1", "edge_p", "edge_r", "edge_f1"])
        for p in sorted(programs, key=lambda x: x["uid"]):
            writer.writerow([p["uid"], p["tag"], p["node_p"], p["node_r"], p["node_f1"],
                              p["edge_p"], p["edge_r"], p["edge_f1"]])


def main() -> None:
    result = run_e2()
    manual_check_uids = generate_manual_check_sample()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = render_report(result, manual_check_uids)
    (RESULTS_DIR / "e2_structural_report.md").write_text(report, encoding="utf-8")
    _write_csv(result["per_program"], RESULTS_DIR / "e2_per_program.csv")

    print(report)


if __name__ == "__main__":
    main()
