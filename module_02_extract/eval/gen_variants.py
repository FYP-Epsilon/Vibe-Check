"""gen_variants.py -- Session C: multi-implementation corpus.

Generates multiple real LLM implementations of each FLOW-BENCH
requirement (one `workflow` per (uid, model)), normalizes/screens them,
and behaviorally admits them against the base program -- building the
corpus Module 03's equivalence-clustering work will consume.

Modes:
    python -m eval.gen_variants              C1: generate raw completions
    python -m eval.gen_variants --normalize   C2: normalize + screen
    python -m eval.gen_variants --admit       C3: behavioral admission
    python -m eval.gen_variants --preflight   C0: env/model-pool smoke check

Never call the NIM API from tests -- mock nim_client.chat_completion.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

EVAL_DIR = Path(__file__).resolve().parent
MODULE02_DIR = EVAL_DIR.parent
sys.path.insert(0, str(MODULE02_DIR / "src"))
sys.path.insert(0, str(EVAL_DIR))

from calibrate import _load_manifest as _load_corpus_manifest  # noqa: E402
from flowbench_adapter import AttributeRewriter  # noqa: E402
import nim_client  # noqa: E402

INPUT_YAML = MODULE02_DIR / "inputs" / "conditional_ootb.yaml"
VARIANTS_DIR = EVAL_DIR / "variants"
RAW_DIR = VARIANTS_DIR / "raw"
NORMALIZED_DIR = VARIANTS_DIR / "normalized"
VARIANTS_MANIFEST_PATH = VARIANTS_DIR / "manifest.json"

TEMPERATURE = 0.7
MAX_TOKENS = 1500
MAX_TOTAL_CALLS = 400

# C0: confirmed live on https://integrate.api.nvidia.com/v1/chat/completions
# as of this session (checked via direct probe -- the NIM catalog lists many
# models that 404 or hang on this generic invoke endpoint). No Qwen-*coder*
# variant was live; qwen3-next is the in-catalog substitute for that slot,
# per the session mandate's explicit substitution allowance.
MODELS: list[dict[str, str]] = [
    {"id": "meta/llama-3.1-8b-instruct", "slug": "llama-3.1-8b", "family": "llama"},
    {"id": "mistralai/mixtral-8x7b-instruct-v0.1", "slug": "mixtral-8x7b", "family": "mistral"},
    {"id": "qwen/qwen3-next-80b-a3b-instruct", "slug": "qwen3-next-80b", "family": "qwen"},
]

SYSTEM_PROMPT = (
    "You implement one Python function. Use ONLY the provided helper "
    "functions and builtins -- no imports. Return only code."
)


# ----------------------------------------------------------------------
# C0 -- preflight
# ----------------------------------------------------------------------

def preflight() -> None:
    nim_client.get_api_key()  # raises with a clear message if unset
    print("API key: present (not printed).")
    for m in MODELS:
        try:
            resp = nim_client.chat_completion(m["id"], "You are terse.", "Reply with exactly one word: pong", max_tokens=10)
            content = resp["choices"][0]["message"]["content"]
            print(f"OK   {m['id']:45s} -> {content!r}")
        except Exception as e:  # noqa: BLE001 -- preflight reports, doesn't crash
            print(f"FAIL {m['id']:45s} -> {e}")


# ----------------------------------------------------------------------
# Prompt construction
# ----------------------------------------------------------------------

def _load_utterances() -> dict[int, str]:
    with open(INPUT_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {t["_metadata"]["uid"]: t["input"]["utterance"] for t in data["tests"]}


def _stub_defs_and_signature(corpus_source: str) -> tuple[list[str], str]:
    """(stub SIGNATURE lines only, workflow's exact signature line) from a
    base corpus program. Deliberately signatures-only, not full bodies:
    the real stub bodies are prepended mechanically after generation (see
    module docstring), so the LLM never needs to see them to write correct
    calling code -- and showing the adapter's actual echo-shape return
    (e.g. "returns a 2-item list keyed off these exact two params") would
    leak an implementation detail that could bias style toward matching
    that shape, rather than genuinely varying with the model's own
    approach to the utterance. Environment (callable names + params +
    required workflow signature) stays fixed; only the LLM-written
    workflow BODY varies."""
    tree = ast.parse(corpus_source)
    stub_sigs: list[str] = []
    workflow_args = None
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name == "workflow":
            workflow_args = ast.unparse(node.args)
        else:
            stub_sigs.append(f"def {node.name}({ast.unparse(node.args)}): ...")
    if workflow_args is None:
        raise ValueError("corpus source has no `workflow` function")
    return stub_sigs, f"def workflow({workflow_args}):"


def build_prompt(uid: int, utterance: str, corpus_source: str) -> tuple[str, str]:
    """(system, user) messages for one (uid) generation request."""
    stub_defs, signature = _stub_defs_and_signature(corpus_source)
    stub_block = "\n\n".join(stub_defs)
    user = (
        f"Task: {utterance}\n\n"
        "The following helper functions are already defined -- do not "
        "redefine them, just call them:\n\n"
        f"{stub_block}\n\n"
        "Implement the task's logic in exactly this function (same name, "
        "same parameters -- do not change the signature):\n\n"
        f"{signature}\n    ...\n\n"
        "Return only the body/implementation of `workflow`, as a complete "
        "`def workflow(...):` block. Do not include the helper functions "
        "in your answer, and do not import anything."
    )
    return SYSTEM_PROMPT, user


def prompt_sha256(system: str, user: str) -> str:
    return hashlib.sha256((system + "\n---\n" + user).encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------
# Code-block extraction from a raw LLM response
# ----------------------------------------------------------------------

def extract_code_block(text: str) -> str:
    """Pull a fenced ```python ...``` or ``` ...``` block out of *text*;
    fall back to the raw text if no fence is present (some models comply
    with "return only code" literally and skip the fence)."""
    lines = text.splitlines()
    fence_indices = [i for i, line in enumerate(lines) if line.strip().startswith("```")]
    if len(fence_indices) >= 2:
        start, end = fence_indices[0], fence_indices[1]
        return "\n".join(lines[start + 1:end]).strip()
    return text.strip()


# ----------------------------------------------------------------------
# C1 -- generation
# ----------------------------------------------------------------------

def _raw_path(uid: int, model_slug: str) -> Path:
    return RAW_DIR / f"{uid}__{model_slug}.json"


def generate_all(
    manifest_by_uid: Optional[dict[int, dict[str, Any]]] = None,
    model_slugs: Optional[set[str]] = None,
    max_calls_this_invocation: Optional[int] = None,
    retry_failed: bool = False,
) -> dict[str, int]:
    """C1: one sample per (uid, model). Resumable -- skips any (uid, model)
    whose raw response is already cached on disk (unless retry_failed=True,
    in which case a previously-cached ERROR record is retried).

    *model_slugs* restricts to a subset of MODELS (e.g. to finish healthy
    models while a flaky one is temporarily degraded, without burning time
    retrying it every pass). *max_calls_this_invocation* caps how many
    live API calls this single call makes before returning -- lets a
    caller run this repeatedly in small, foreground-safe chunks instead of
    trusting one long-running background process."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    utterances = _load_utterances()
    manifest_by_uid = manifest_by_uid or {
        e["uid"]: e for e in _load_corpus_manifest() if "base_uid" not in e
    }
    models = [m for m in MODELS if model_slugs is None or m["slug"] in model_slugs]

    calls_made = 0
    skipped_cached = 0
    failed = 0

    for uid in sorted(manifest_by_uid):
        entry = manifest_by_uid[uid]
        corpus_path = EVAL_DIR / entry["source_file"]
        corpus_source = corpus_path.read_text(encoding="utf-8")
        system, user = build_prompt(uid, utterances[uid], corpus_source)
        phash = prompt_sha256(system, user)

        for model in models:
            raw_path = _raw_path(uid, model["slug"])
            if raw_path.exists():
                if retry_failed and "error" in json.loads(raw_path.read_text(encoding="utf-8")):
                    pass  # fall through and retry this one
                else:
                    skipped_cached += 1
                    continue
            if calls_made >= MAX_TOTAL_CALLS:
                print(f"Hit MAX_TOTAL_CALLS={MAX_TOTAL_CALLS}; stopping.")
                return {"calls_made": calls_made, "skipped_cached": skipped_cached, "failed": failed}
            if max_calls_this_invocation is not None and calls_made >= max_calls_this_invocation:
                return {"calls_made": calls_made, "skipped_cached": skipped_cached, "failed": failed, "stopped_early": True}

            try:
                resp = nim_client.chat_completion(model["id"], system, user, temperature=TEMPERATURE, max_tokens=MAX_TOKENS)
                calls_made += 1
            except Exception as e:  # noqa: BLE001 -- record and continue; not a generation-poisoning error
                calls_made += 1
                failed += 1
                raw_path.write_text(json.dumps({
                    "uid": uid, "model": model["id"], "model_slug": model["slug"],
                    "prompt_sha256": phash, "temperature": TEMPERATURE, "error": str(e),
                }, indent=2), encoding="utf-8")
                print(f"FAIL uid={uid} model={model['slug']}: {e}")
                continue

            content = resp["choices"][0]["message"]["content"]
            extracted = extract_code_block(content)
            raw_path.write_text(json.dumps({
                "uid": uid, "model": model["id"], "model_slug": model["slug"],
                "prompt_sha256": phash, "temperature": TEMPERATURE,
                "raw_response": resp, "extracted_code": extracted,
            }, indent=2), encoding="utf-8")
            print(f"OK   uid={uid} model={model['slug']} ({len(extracted)} chars)")

    return {"calls_made": calls_made, "skipped_cached": skipped_cached, "failed": failed}


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main() -> None:
    if "--preflight" in sys.argv:
        preflight()
        return
    if "--normalize" in sys.argv:
        import normalize_variants
        normalize_variants.main()
        return
    if "--admit" in sys.argv:
        import admit_variants
        admit_variants.main()
        return
    stats = generate_all()
    print(stats)


if __name__ == "__main__":
    main()
