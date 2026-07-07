"""normalize_variants.py -- Session C, C2: normalization + static screening.

Mechanical pass over eval/variants/raw/*.json (C1's cached generations):
strip stub redefinitions and unused imports (a variant that still
references a name only an import would define is rejected -- it
functionally needs the import), rewrite obj.attr -> obj["attr"]
(AttributeRewriter, reused from flowbench_adapter.py), then screen each
survivor through a fixed sequence of gates. Clean survivors become
eval/variants/normalized/<uid>__<model-slug>.py, self-contained like the
base corpus (base program's real stub defs prepended verbatim -- the
model never had to know their bodies, only their signatures).

No judgment calls: every reject reason is mechanical and recorded.
"""

from __future__ import annotations

import ast
import builtins
import json
import sys
from pathlib import Path
from typing import Any, Optional

EVAL_DIR = Path(__file__).resolve().parent
MODULE02_DIR = EVAL_DIR.parent
sys.path.insert(0, str(MODULE02_DIR / "src"))
sys.path.insert(0, str(EVAL_DIR))

from calibrate import _load_manifest as _load_corpus_manifest  # noqa: E402
from flowbench_adapter import AttributeRewriter  # noqa: E402

VARIANTS_DIR = EVAL_DIR / "variants"
RAW_DIR = VARIANTS_DIR / "raw"
NORMALIZED_DIR = VARIANTS_DIR / "normalized"
VARIANTS_MANIFEST_PATH = VARIANTS_DIR / "manifest.json"

_BUILTIN_NAMES = set(dir(builtins))


# ----------------------------------------------------------------------
# AST helpers
# ----------------------------------------------------------------------

def _corpus_stub_names(corpus_source: str) -> set[str]:
    tree = ast.parse(corpus_source)
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef) and n.name != "workflow"}


def _workflow_signature(corpus_source: str) -> str:
    tree = ast.parse(corpus_source)
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == "workflow":
            return ast.unparse(n.args)
    raise ValueError("no workflow in corpus source")


def _corpus_stub_defs_source(corpus_source: str) -> list[str]:
    tree = ast.parse(corpus_source)
    return [
        ast.get_source_segment(corpus_source, n)
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name != "workflow" and ast.get_source_segment(corpus_source, n)
    ]


class _ImportStripper(ast.NodeTransformer):
    """Remove Import/ImportFrom nodes wherever they occur (module level or
    nested inside the workflow body) and record the names they bound."""

    def __init__(self) -> None:
        self.imported_names: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imported_names.add(alias.asname or alias.name.split(".")[0])
        return None

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self.imported_names.add(alias.asname or alias.name)
        return None


def _still_references(tree: ast.Module, names: set[str]) -> set[str]:
    return {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in names
    }


def _has_async_or_yield(tree: ast.Module) -> bool:
    return any(
        isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom))
        for node in ast.walk(tree)
    )


def _first_unknown_call(tree: ast.Module, known: set[str]) -> Optional[str]:
    """First bare-Name call target that isn't a known stub, `user_task`,
    or a builtin. (Attribute-method calls, e.g. a hallucinated
    `result.send()`, are deliberately NOT screened here -- they're a
    behavioral defect, not a structural one, and belong in C3's
    behavioral admission / C5c's natural-bug corpus, not a static
    reject.)"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            if name not in known and name != "user_task" and name not in _BUILTIN_NAMES:
                return name
    return None


# ----------------------------------------------------------------------
# Per-variant normalization + screening
# ----------------------------------------------------------------------

def normalize_one(uid: int, model_slug: str, extracted_code: str, corpus_source: str) -> dict[str, Any]:
    applied: list[str] = []

    try:
        tree = ast.parse(extracted_code)
    except SyntaxError as e:
        return {"screen": "parse_error", "normalization_applied": applied, "detail": str(e)}

    stripper = _ImportStripper()
    tree = stripper.visit(tree)
    ast.fix_missing_locations(tree)
    if stripper.imported_names:
        still_used = _still_references(tree, stripper.imported_names)
        if still_used:
            applied.append(f"stripped_imports:{','.join(sorted(stripper.imported_names))}")
            return {
                "screen": "imports", "normalization_applied": applied,
                "detail": f"still references {sorted(still_used)} after stripping",
            }
        applied.append(f"stripped_unused_imports:{','.join(sorted(stripper.imported_names))}")

    stub_names = _corpus_stub_names(corpus_source)
    before = len(tree.body)
    tree.body = [n for n in tree.body if not (isinstance(n, ast.FunctionDef) and n.name in stub_names)]
    if len(tree.body) != before:
        applied.append("stripped_stub_redefinitions")

    tree = AttributeRewriter().visit(tree)
    ast.fix_missing_locations(tree)
    applied.append("attribute_rewrite")

    workflow_defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "workflow"]
    if len(workflow_defs) != 1:
        return {"screen": "no_single_workflow_def", "normalization_applied": applied,
                "detail": f"found {len(workflow_defs)} top-level `workflow` defs"}

    expected_sig = _workflow_signature(corpus_source)
    actual_sig = ast.unparse(workflow_defs[0].args)
    if actual_sig != expected_sig:
        return {"screen": "signature_mismatch", "normalization_applied": applied,
                "detail": f"expected ({expected_sig}) got ({actual_sig})"}

    if _has_async_or_yield(tree):
        return {"screen": "async_or_yield", "normalization_applied": applied}

    offending = _first_unknown_call(tree, stub_names)
    if offending:
        return {"screen": "unknown_call", "normalization_applied": applied, "detail": offending}

    stub_defs_src = _corpus_stub_defs_source(corpus_source)
    workflow_src = ast.unparse(tree)
    module_src = "\n\n\n".join([*stub_defs_src, workflow_src]) + "\n"

    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uid}__{model_slug}.py"
    (NORMALIZED_DIR / filename).write_text(module_src, encoding="utf-8")

    return {
        "screen": "pass", "normalization_applied": applied,
        "source_file": f"variants/normalized/{filename}",
    }


# ----------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------

FUNNEL_STAGE = {
    "parse_error": "raw",
    "imports": "parsed",
    "no_single_workflow_def": "parsed",
    "signature_mismatch": "parsed",
    "async_or_yield": "signature-ok",
    "unknown_call": "signature-ok",
    "pass": "clean",
}


def run_normalization() -> list[dict[str, Any]]:
    corpus_manifest = {e["uid"]: e for e in _load_corpus_manifest() if "base_uid" not in e}
    records: list[dict[str, Any]] = []

    for raw_path in sorted(RAW_DIR.glob("*.json")):
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        uid = raw["uid"]
        model = raw["model"]
        model_slug = raw["model_slug"]

        if "extracted_code" not in raw:
            records.append({
                "uid": uid, "variant_id": f"{uid}__{model_slug}", "model": model,
                "screen": "generation_failed", "normalization_applied": [],
                "detail": raw.get("error"),
            })
            continue

        corpus_entry = corpus_manifest[uid]
        corpus_source = (EVAL_DIR / corpus_entry["source_file"]).read_text(encoding="utf-8")
        result = normalize_one(uid, model_slug, raw["extracted_code"], corpus_source)
        records.append({
            "uid": uid, "variant_id": f"{uid}__{model_slug}", "model": model,
            "prompt_sha256": raw.get("prompt_sha256"), "temperature": raw.get("temperature"),
            **result,
        })

    return records


def render_funnel(records: list[dict[str, Any]]) -> str:
    by_model: dict[str, dict[str, int]] = {}
    for r in records:
        model = r["model"]
        stats = by_model.setdefault(model, {"raw": 0, "parsed": 0, "signature-ok": 0, "clean": 0})
        stats["raw"] += 1
        stage = FUNNEL_STAGE.get(r["screen"], "raw")
        # Each stage implies passing every earlier one.
        order = ["raw", "parsed", "signature-ok", "clean"]
        for s in order[: order.index(stage) + 1]:
            if s != "raw":
                stats[s] += 1

    lines = ["| model | raw | parsed | signature-ok | clean |", "|---|---|---|---|---|"]
    for model, stats in sorted(by_model.items()):
        lines.append(f"| {model} | {stats['raw']} | {stats['parsed']} | {stats['signature-ok']} | {stats['clean']} |")
    return "\n".join(lines)


def main() -> None:
    records = run_normalization()
    VARIANTS_DIR.mkdir(parents=True, exist_ok=True)
    VARIANTS_MANIFEST_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(render_funnel(records))

    reject_reasons: dict[str, int] = {}
    for r in records:
        if r["screen"] != "pass":
            reject_reasons[r["screen"]] = reject_reasons.get(r["screen"], 0) + 1
    print()
    print("Reject reasons:", json.dumps(reject_reasons, indent=2))


if __name__ == "__main__":
    main()
