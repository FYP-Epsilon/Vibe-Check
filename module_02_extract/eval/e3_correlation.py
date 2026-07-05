"""e3_correlation.py -- E3: certificate score vs code-vs-code correctness.

Anti-circularity rule (load-bearing -- do not violate): the ground-truth
"how broken is this mutant" signal (semantic_diff_rate) comes ONLY from
executing base and mutant *code* directly on identical inputs and diffing
their observable behavior (stub call sequence + return value). The WIR
must never appear on this side of the experiment -- it is the thing whose
score we are validating. Reusing eval/calibrate.py's differential runner
for the *certificate* side is fine and expected; it must never feed back
into semantic_diff_rate.

Input generation is reimplemented locally (type-hint-driven random
values, string params sampled from a guard-literal pool extracted from
the source) rather than importing RandomizedDifferentialTester, per the
session mandate -- this experiment must not couple to that class.
"""

from __future__ import annotations

import ast
import csv
import inspect
import json
import math
import random
import sys
from pathlib import Path
from typing import Any, Optional, get_type_hints

EVAL_DIR = Path(__file__).resolve().parent
MODULE02_DIR = EVAL_DIR.parent
sys.path.insert(0, str(MODULE02_DIR / "src"))
sys.path.insert(0, str(EVAL_DIR))

from calibrate import run_differential_verification, _base_func_wir  # noqa: E402

MANIFEST_PATH = EVAL_DIR / "manifest.json"
RESULTS_DIR = EVAL_DIR / "results"
PAIRS_CSV = RESULTS_DIR / "e3_pairs.csv"

N_INPUTS = 25
SEED_BASE = 100_000  # per-base-uid input seed = SEED_BASE + base_uid
ALPHA = 0.05


# ----------------------------------------------------------------------
# Local, independent input generation (code-vs-code side only)
# ----------------------------------------------------------------------

def _string_pool(tree: ast.Module) -> list[str]:
    pool: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for side in (node.left, *node.comparators):
                if isinstance(side, ast.Constant) and isinstance(side.value, str):
                    pool.add(side.value)
    return sorted(pool)


def _generate_inputs(func_obj: Any, string_pool: list[str], rng: random.Random) -> dict[str, Any]:
    try:
        type_hints = get_type_hints(func_obj)
    except Exception:
        type_hints = {}
    sig = inspect.signature(func_obj)
    inputs: dict[str, Any] = {}
    for name, param in sig.parameters.items():
        ann = type_hints.get(name)
        origin = getattr(ann, "__origin__", None)
        if ann is int:
            inputs[name] = rng.randint(-100, 100)
        elif ann is float:
            inputs[name] = round(rng.uniform(-100.0, 100.0), 2)
        elif ann is bool:
            inputs[name] = rng.choice([True, False])
        elif ann is str:
            choices = string_pool + ["", f"junk_{rng.randint(0, 10**6)}"]
            inputs[name] = rng.choice(choices)
        elif ann is dict or origin is dict:
            inputs[name] = {f"k{i}": rng.randint(1, 5) for i in range(rng.randint(1, 3))}
        elif ann is list or origin is list:
            inputs[name] = [f"v{i}" for i in range(rng.randint(1, 3))]
        else:
            inputs[name] = rng.randint(-100, 100)
    return inputs


def generate_shared_inputs(base_source: str, function_name: str, base_uid: int, n: int = N_INPUTS) -> list[dict[str, Any]]:
    """N inputs derived from the base program's own signature/guard
    literals, seeded deterministically per base_uid so a mutant sharing
    the same signature is compared on exactly the same inputs."""
    tree = ast.parse(base_source)
    pool = _string_pool(tree)
    ns: dict[str, Any] = {"__builtins__": __builtins__}
    exec(compile(base_source, "<string>", "exec"), ns)
    func_obj = ns[function_name]
    rng = random.Random(SEED_BASE + base_uid)
    return [_generate_inputs(func_obj, pool, rng) for _ in range(n)]


# ----------------------------------------------------------------------
# Stub-call recorder (code-vs-code side only, no WIR involved)
# ----------------------------------------------------------------------

def _instrument(source: str, entry_function: str) -> tuple[dict[str, Any], list[str]]:
    """Compile *source*, wrap every top-level function except the entry
    point to log its name before delegating -- stubs are deterministic
    echoes by construction (eval/mutate.py never mutates them), so this
    is a sound, cheap way to observe which stubs a run actually called."""
    ns: dict[str, Any] = {"__builtins__": __builtins__}
    exec(compile(source, "<string>", "exec"), ns)
    log: list[str] = []

    def _make_wrapper(name: str, original: Any):
        def _wrapped(*args, **kwargs):
            log.append(name)
            return original(*args, **kwargs)
        return _wrapped

    for name, obj in list(ns.items()):
        if name == entry_function or name.startswith("__") or not callable(obj):
            continue
        ns[name] = _make_wrapper(name, obj)

    return ns, log


def run_recorded(ns: dict[str, Any], log: list[str], entry_function: str, inputs: dict[str, Any]) -> tuple[tuple[str, ...], Any]:
    """One recorded run: returns (call_sequence, return_value_repr)."""
    log.clear()
    try:
        result = ns[entry_function](**inputs)
        result_repr = repr(result)
    except BaseException as e:
        result_repr = f"__exception__:{type(e).__name__}"
    return tuple(log), result_repr


def semantic_diff_rate(base_source: str, mutant_source: str, function_name: str, inputs_list: list[dict[str, Any]]) -> float:
    """Fraction of shared inputs where base and mutant observably differ
    (call sequence or return value). No WIR anywhere in this function."""
    base_ns, base_log = _instrument(base_source, function_name)
    mut_ns, mut_log = _instrument(mutant_source, function_name)

    diffs = 0
    for inputs in inputs_list:
        base_obs = run_recorded(base_ns, base_log, function_name, inputs)
        mut_obs = run_recorded(mut_ns, mut_log, function_name, inputs)
        if base_obs != mut_obs:
            diffs += 1
    return diffs / len(inputs_list) if inputs_list else 0.0


# ----------------------------------------------------------------------
# Pure-stdlib statistics
# ----------------------------------------------------------------------

def pearson_r(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return 0.0
    return cov / math.sqrt(vx * vy)


def _rank(values: list[float]) -> list[float]:
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1  # 1-indexed, averaged over ties
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def spearman_rho(xs: list[float], ys: list[float]) -> float:
    return pearson_r(_rank(xs), _rank(ys))


def fisher_z_ci(r: float, n: int, alpha: float = ALPHA) -> tuple[float, float]:
    """95% CI for Pearson r via the Fisher z-transform (pure math:
    atanh, 1.96/sqrt(n-3) -- no scipy)."""
    if n < 4 or abs(r) >= 1.0:
        return (r, r)
    z = math.atanh(r)
    se = 1.0 / math.sqrt(n - 3)
    z_crit = 1.96
    return (math.tanh(z - z_crit * se), math.tanh(z + z_crit * se))


# ----------------------------------------------------------------------
# Corpus-wide run
# ----------------------------------------------------------------------

def _load_manifest() -> list[dict[str, Any]]:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_existing_pairs(path: Path = PAIRS_CSV) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    with open(path, "r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[row["mutant_id"]] = row
    return rows


def _mutant_id(entry: dict[str, Any]) -> str:
    return f"{entry['base_uid']}__{entry['operator']}__{entry.get('site') or ''}"


def run_e3(manifest_path: Path = MANIFEST_PATH, pairs_csv: Path = PAIRS_CSV) -> dict[str, Any]:
    manifest = _load_manifest()
    manifest_by_uid = {e["uid"]: e for e in manifest if "base_uid" not in e}
    mutant_entries = [e for e in manifest if e.get("applicable") and "base_uid" in e]

    existing = _load_existing_pairs(pairs_csv)  # resumability
    rows: list[dict[str, Any]] = list(existing.values())
    done_ids = set(existing.keys())

    execution_failed: list[str] = []
    wir_cache: dict[int, tuple[str, dict[str, Any]]] = {}
    inputs_cache: dict[int, list[dict[str, Any]]] = {}

    for entry in mutant_entries:
        mid = _mutant_id(entry)
        if mid in done_ids:
            continue
        base_uid = entry["base_uid"]
        base = _base_func_wir(base_uid, manifest_by_uid, wir_cache)
        if base is None:
            execution_failed.append(mid)
            continue
        base_source, base_func_wir = base

        mutant_path = EVAL_DIR / entry["source_file"]
        if not mutant_path.exists():
            execution_failed.append(mid)
            continue
        mutant_source = mutant_path.read_text(encoding="utf-8")

        try:
            if base_uid not in inputs_cache:
                inputs_cache[base_uid] = generate_shared_inputs(base_source, "workflow", base_uid)
            inputs_list = inputs_cache[base_uid]
            diff_rate = semantic_diff_rate(base_source, mutant_source, "workflow", inputs_list)
        except Exception:
            execution_failed.append(mid)
            continue

        try:
            cert = run_differential_verification(mutant_source, base_func_wir)
            combined = cert.get("combined_confidence", 0.0)
        except Exception:
            execution_failed.append(mid)
            continue

        row = {
            "mutant_id": mid,
            "operator": entry["operator"],
            "base_uid": base_uid,
            "semantic_diff_rate": diff_rate,
            "combined_confidence": combined,
        }
        rows.append(row)
        done_ids.add(mid)

        # Persist incrementally so the run is resumable.
        _write_csv(rows, pairs_csv)

    return {"rows": rows, "execution_failed": execution_failed}


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["mutant_id", "operator", "base_uid", "semantic_diff_rate", "combined_confidence"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ----------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------

def render_report(result: dict[str, Any]) -> str:
    rows = result["rows"]
    xs = [1.0 - float(r["combined_confidence"]) for r in rows]
    ys = [float(r["semantic_diff_rate"]) for r in rows]
    n = len(rows)

    r_full = pearson_r(xs, ys) if n >= 2 else 0.0
    rho_full = spearman_rho(xs, ys) if n >= 2 else 0.0
    ci_full = fisher_z_ci(r_full, n)

    nonzero = [(x, y) for x, y in zip(xs, ys) if y > 0]
    n_nonzero = len(nonzero)
    if n_nonzero >= 2:
        xs_nz, ys_nz = zip(*nonzero)
        r_nz = pearson_r(list(xs_nz), list(ys_nz))
        rho_nz = spearman_rho(list(xs_nz), list(ys_nz))
        ci_nz = fisher_z_ci(r_nz, n_nonzero)
    else:
        r_nz = rho_nz = 0.0
        ci_nz = (0.0, 0.0)

    n_equivalent = n - n_nonzero
    by_operator_equiv: dict[str, list[int]] = {}
    for row in rows:
        op = row["operator"]
        by_operator_equiv.setdefault(op, [0, 0])
        by_operator_equiv[op][1] += 1
        if float(row["semantic_diff_rate"]) == 0.0:
            by_operator_equiv[op][0] += 1

    lines = [
        "# E3: Certificate Score vs Code-vs-Code Correctness",
        "",
        "## Methods",
        "",
        f"Ground truth (`semantic_diff_rate`): base and mutant `workflow` are",
        f"each executed directly on the SAME {N_INPUTS} seeded random inputs",
        "(type-hint-driven generation reimplemented locally in this module,",
        "not imported from `RandomizedDifferentialTester`; string params",
        "sampled from a guard-literal pool extracted from the source, as",
        "elsewhere in this eval suite). Each run's observable behavior is",
        "the sequence of stub calls (every non-entry top-level function is",
        "wrapped to log its name before delegating -- stubs are",
        "deterministic echoes by construction, eval/mutate.py never mutates",
        "them) plus the return value. `semantic_diff_rate` is the fraction",
        "of the N inputs where these differ. **The WIR never appears on",
        "this side of the experiment** -- it is the thing being evaluated.",
        "",
        "Certificate score: `combined_confidence` from",
        "`eval/calibrate.py`'s `run_differential_verification` (mutant",
        "verified against its base program's WIR) -- the same detector",
        "measured in the E1 calibration run.",
        "",
        f"Caveat: N={N_INPUTS} bounds the equivalent-mutant count from",
        "above -- a mutant that differs only on inputs not sampled in",
        f"these {N_INPUTS} looks equivalent here but may not be with a",
        "larger sample. Read the equivalent count as \"at least this many",
        "are indistinguishable at this sample size,\" not an exact count.",
        "",
        "## Correlation: 1 - combined_confidence vs semantic_diff_rate",
        "",
        f"- n = {n} mutants scored (execution failed: {len(result['execution_failed'])})",
        f"- Pearson r = {r_full:.4f}, 95% CI {_fmt_ci(ci_full)}",
        f"- Spearman rho = {rho_full:.4f}",
        "",
        f"### Restricted to semantic_diff_rate > 0 (n={n_nonzero})",
        "",
        f"- Pearson r = {r_nz:.4f}, 95% CI {_fmt_ci(ci_nz)}",
        f"- Spearman rho = {rho_nz:.4f}",
        "",
        f"## Equivalent mutants (semantic_diff_rate == 0 at N={N_INPUTS}): {n_equivalent} / {n}",
        "",
        "| operator | equivalent | total |",
        "|---|---|---|",
    ]
    for op, (eq, tot) in sorted(by_operator_equiv.items()):
        lines.append(f"| {op} | {eq} | {tot} |")
    lines.append("")

    early_return_equiv = by_operator_equiv.get("early-return", (0, 0))
    if early_return_equiv[1] and early_return_equiv[0] == early_return_equiv[1]:
        lines += [
            "## Finding: early-return is a mutate.py implementation bug, not just a hard-to-detect operator",
            "",
            "`early-return` shows 100% equivalent mutants -- verified by inspecting",
            "generated mutant files directly, not just inferred from the rate: "
            "`eval/mutate.py`'s `op_early_return` inserts the new `return None` at "
            "`len(body) - 1`, i.e. immediately *before* the function's existing "
            "trailing statement. Every `eval/flowbench_adapter.py`-generated "
            "workflow already ends with a bare `return None` as that trailing "
            "statement, so the mutation fires at the exact same point the "
            "original would have -- it never actually cuts off any real logic "
            "(the for-loop/if-chain/stub calls all execute in full either way), "
            "it just duplicates the terminal no-op return as dead code. This "
            "reframes the earlier differential-mode calibration's ~0.43 "
            "detection rate for `early-return`: those weren't successfully "
            "detected genuine bugs surviving on hard-to-reach inputs -- they "
            "were **false positives on semantically-equivalent programs** (the "
            "certificate reporting `combined_confidence < tau` for code that "
            "is not actually buggy). Not fixed this session (`eval/mutate.py` "
            "is out of scope -- src/ and prior sessions' infra are frozen "
            "here), but this should be corrected before `early-return`'s "
            "detection numbers are cited anywhere as evidence of genuine bug "
            "detection.",
            "",
        ]

    if result["execution_failed"]:
        lines += [f"Execution-failed mutant ids: {result['execution_failed']}", ""]

    return "\n".join(lines)


def _fmt_ci(ci: tuple[float, float]) -> str:
    return f"[{ci[0]:.4f}, {ci[1]:.4f}]"


def main() -> None:
    result = run_e3()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = render_report(result)
    (RESULTS_DIR / "e3_correlation_report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
