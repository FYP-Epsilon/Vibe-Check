"""admit_variants.py -- Session C, C3: behavioral admission.

For each normalized variant (eval/variants/manifest.json, screen=="pass"),
executes it against the BASE implementation on N=100 shared seeded
inputs and compares observable behavior (stub-call sequence + return
value) -- code-vs-code, WIR-free, anti-circular. Reuses
eval/e3_correlation.py's instrumentation/recording machinery directly
(`_string_pool`, `_instrument`, `run_recorded`); only the input
generator is new here (round-robin-first over the BASE-union-VARIANT
guard-literal pool, mirroring Session A's A2 rationale), reimplemented
independently rather than importing RandomizedDifferentialTester or D1 --
same anti-coupling rule E3 already established for this experiment
family: admission is establishing ground truth, so it must not share
machinery with the verification pipeline being measured downstream in
C5b/C5c.

diff_rate == 0  -> admitted (label "correct" for M03; equivalence is
                   N=100-bounded -- same caveat language as E3: a variant
                   that differs only on inputs outside this sample looks
                   equivalent here but may not be with a larger sample).
diff_rate > 0   -> rejected-behavioral (label "natural_bug" -- KEPT, not
                   discarded; this is C5c's real-LLM-bug detection
                   corpus).
"""

from __future__ import annotations

import ast
import json
import random
import sys
from pathlib import Path
from typing import Any, Optional

EVAL_DIR = Path(__file__).resolve().parent
MODULE02_DIR = EVAL_DIR.parent
sys.path.insert(0, str(MODULE02_DIR / "src"))
sys.path.insert(0, str(EVAL_DIR))

from calibrate import _load_manifest as _load_corpus_manifest  # noqa: E402
from e3_correlation import _string_pool, _instrument, run_recorded, _generate_inputs  # noqa: E402

VARIANTS_DIR = EVAL_DIR / "variants"
VARIANTS_MANIFEST_PATH = VARIANTS_DIR / "manifest.json"

N_INPUTS = 100
SEED_BASE = 900_000  # distinct namespace from E3's SEED_BASE=100_000
ENTRY_FUNCTION = "workflow"  # fixed for every corpus program and variant


# ----------------------------------------------------------------------
# Round-robin input generation over the base UNION variant literal pool
# (A2-mirrored; independently implemented, not imported from D1/A2).
# ----------------------------------------------------------------------

def generate_admission_inputs(base_source: str, function_name: str, pool: list[str], seed: int, n: int = N_INPUTS) -> list[dict[str, Any]]:
    ns: dict[str, Any] = {"__builtins__": __builtins__}
    exec(compile(base_source, "<string>", "exec"), ns)
    func_obj = ns[function_name]

    rng = random.Random(seed)
    queue = list(pool)
    inputs_list = []
    for _ in range(n):
        inputs_list.append(_generate_inputs_round_robin(func_obj, pool, queue, rng))
    return inputs_list


def _generate_inputs_round_robin(func_obj: Any, pool: list[str], queue: list[str], rng: random.Random) -> dict[str, Any]:
    """Same shape as e3_correlation._generate_inputs, except str params
    drain the shared round-robin *queue* first (each pool literal
    guaranteed drawn at least once across the input budget) before
    falling back to uniform random sampling -- the A2 fix for exactly
    the failure mode Session A diagnosed: a model-renamed guard literal
    (e.g. base's "high" vs a variant's "urgent") going unexercised for
    an entire N-input run, making the two sides agree vacuously."""
    import inspect
    from typing import get_type_hints
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
            if queue:
                inputs[name] = queue.pop(0)
            else:
                choices = pool + ["", f"junk_{rng.randint(0, 10**6)}"]
                inputs[name] = rng.choice(choices)
        elif ann is dict or origin is dict:
            inputs[name] = {f"k{i}": rng.randint(1, 5) for i in range(rng.randint(1, 3))}
        elif ann is list or origin is list:
            inputs[name] = [f"v{i}" for i in range(rng.randint(1, 3))]
        else:
            inputs[name] = rng.randint(-100, 100)
    return inputs


# ----------------------------------------------------------------------
# Admission check (code-vs-code, reusing E3's recorder)
# ----------------------------------------------------------------------

def admission_check(base_source: str, variant_source: str, function_name: str, inputs_list: list[dict[str, Any]]) -> tuple[float, Optional[dict[str, Any]]]:
    base_ns, base_log = _instrument(base_source, function_name)
    var_ns, var_log = _instrument(variant_source, function_name)

    diffs = 0
    first_divergence: Optional[dict[str, Any]] = None
    for inputs in inputs_list:
        base_obs = run_recorded(base_ns, base_log, function_name, inputs)
        var_obs = run_recorded(var_ns, var_log, function_name, inputs)
        if base_obs != var_obs:
            diffs += 1
            if first_divergence is None:
                first_divergence = {
                    "inputs": inputs,
                    "base_calls": list(base_obs[0]), "base_return": base_obs[1],
                    "variant_calls": list(var_obs[0]), "variant_return": var_obs[1],
                }
    rate = diffs / len(inputs_list) if inputs_list else 0.0
    return rate, first_divergence


# ----------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------

def run_admission() -> list[dict[str, Any]]:
    variants_manifest = json.loads(VARIANTS_MANIFEST_PATH.read_text(encoding="utf-8"))
    corpus_manifest = {e["uid"]: e for e in _load_corpus_manifest() if "base_uid" not in e}

    results: list[dict[str, Any]] = []
    for rec in variants_manifest:
        if rec.get("screen") != "pass":
            results.append({**rec, "admission": None})
            continue

        uid = rec["uid"]
        corpus_entry = corpus_manifest[uid]
        base_source = (EVAL_DIR / corpus_entry["source_file"]).read_text(encoding="utf-8")
        variant_source = (EVAL_DIR / rec["source_file"]).read_text(encoding="utf-8")

        base_pool = _string_pool(ast.parse(base_source))
        variant_pool = _string_pool(ast.parse(variant_source))
        pool = sorted(set(base_pool) | set(variant_pool))

        try:
            inputs_list = generate_admission_inputs(base_source, ENTRY_FUNCTION, pool, seed=SEED_BASE + uid)
            diff_rate, first_divergence = admission_check(base_source, variant_source, ENTRY_FUNCTION, inputs_list)
        except Exception as e:  # noqa: BLE001 -- a crash on EVERY input is itself informative, not a script bug
            results.append({**rec, "admission": {
                "verdict": "error", "n_inputs": 0, "diff_rate": None, "detail": str(e),
            }})
            continue

        verdict = "admitted" if diff_rate == 0.0 else "rejected_behavioral"
        results.append({**rec, "admission": {
            "verdict": verdict,
            "n_inputs": len(inputs_list),
            "diff_rate": diff_rate,
            "first_divergent_input": first_divergence,
        }})

    return results


def main() -> None:
    results = run_admission()
    VARIANTS_MANIFEST_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")

    admitted = sum(1 for r in results if r.get("admission", {}) and r["admission"].get("verdict") == "admitted")
    rejected = sum(1 for r in results if r.get("admission", {}) and r["admission"].get("verdict") == "rejected_behavioral")
    errored = sum(1 for r in results if r.get("admission", {}) and r["admission"].get("verdict") == "error")
    screened_out = sum(1 for r in results if r.get("admission") is None)
    print(f"admitted={admitted} rejected_behavioral={rejected} error={errored} screened_out={screened_out}")


if __name__ == "__main__":
    main()
