"""mutate.py -- single-operator mutation generator for the eval corpus.

Applies exactly one mutation operator at exactly one site to a base
program's ``workflow`` function (stub defs are left untouched -- a mutant
represents a bug in the *workflow's* orchestration logic, not in a
simulated external system). Each (base, operator) pair yields at most one
mutant, using the first applicable site found; operators with no
applicable site in a given base are recorded as inapplicable rather than
skipped silently.
"""

from __future__ import annotations

import ast
import copy
import json
import random
from pathlib import Path
from typing import Any, Callable, Optional

EVAL_DIR = Path(__file__).resolve().parent
CORPUS_DIR = EVAL_DIR / "corpus"
MUTANTS_DIR = EVAL_DIR / "mutants"
MANIFEST_PATH = EVAL_DIR / "manifest.json"

MutationResult = tuple[ast.Module, str]  # (mutated tree, site description)


def _find_workflow(tree: ast.Module) -> Optional[ast.FunctionDef]:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "workflow":
            return node
    return None


def _stmt_lists(fn: ast.FunctionDef) -> list[list[ast.stmt]]:
    """Every statement list (block) reachable inside *fn*: the function
    body itself, plus every If/For/While body and orelse."""
    blocks: list[list[ast.stmt]] = [fn.body]
    for node in ast.walk(fn):
        if isinstance(node, (ast.If, ast.For, ast.While)):
            if node.body:
                blocks.append(node.body)
            if node.orelse:
                blocks.append(node.orelse)
    return blocks


# ----------------------------------------------------------------------
# Operators. Each takes the *already-copy.deepcopy'd* module tree and the
# workflow FunctionDef found inside it, and either mutates in place and
# returns a site description, or returns None if inapplicable.
# ----------------------------------------------------------------------

def op_negate_guard(tree: ast.Module, fn: ast.FunctionDef) -> Optional[str]:
    for node in ast.walk(fn):
        if isinstance(node, ast.If):
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
            ast.fix_missing_locations(node.test)
            return f"if@line{getattr(node, 'lineno', '?')}"
    return None


_BOUNDARY_FLIP = {ast.Lt: ast.GtE, ast.LtE: ast.Gt, ast.Gt: ast.LtE, ast.GtE: ast.Lt}


def op_boundary_shift(tree: ast.Module, fn: ast.FunctionDef) -> Optional[str]:
    for node in ast.walk(fn):
        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                flip = _BOUNDARY_FLIP.get(type(op))
                if flip is not None:
                    node.ops[i] = flip()
                    return f"compare@line{getattr(node, 'lineno', '?')}"
    return None


def op_swap_branches(tree: ast.Module, fn: ast.FunctionDef) -> Optional[str]:
    for node in ast.walk(fn):
        if isinstance(node, ast.If) and node.orelse and not (
            len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)
        ):
            node.body, node.orelse = node.orelse, node.body
            return f"if@line{getattr(node, 'lineno', '?')}"
    return None


def op_off_by_one_loop(tree: ast.Module, fn: ast.FunctionDef) -> Optional[str]:
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
            if node.args and isinstance(node.args[-1], ast.Constant) and isinstance(node.args[-1].value, int):
                node.args[-1] = ast.Constant(value=node.args[-1].value + 1)
                return f"range@line{getattr(node, 'lineno', '?')}"
        if isinstance(node, ast.Slice) and isinstance(node.upper, ast.Constant) and isinstance(node.upper.value, int):
            node.upper = ast.Constant(value=node.upper.value + 1)
            return f"slice@line{getattr(node, 'lineno', '?')}"
    return None


def op_drop_step(tree: ast.Module, fn: ast.FunctionDef) -> Optional[str]:
    for block in _stmt_lists(fn):
        for i, stmt in enumerate(block):
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
                site = f"stmt@line{getattr(stmt, 'lineno', '?')}"
                del block[i]
                return site
    return None


def op_reorder_steps(tree: ast.Module, fn: ast.FunctionDef) -> Optional[str]:
    for block in _stmt_lists(fn):
        # Need two adjacent, independently-movable statements; skip the
        # trailing `return` we always append.
        movable = [s for s in block if not isinstance(s, ast.Return)]
        if len(movable) >= 2:
            i = block.index(movable[0])
            j = block.index(movable[1])
            block[i], block[j] = block[j], block[i]
            return f"stmts@lines{getattr(movable[0], 'lineno', '?')}-{getattr(movable[1], 'lineno', '?')}"
    return None


def op_wrong_variable(tree: ast.Module, fn: ast.FunctionDef) -> Optional[str]:
    assigned = [n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]
    distinct = list(dict.fromkeys(assigned))
    if len(distinct) < 2:
        return None
    victim, replacement = distinct[0], distinct[1]
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == victim:
            node.id = replacement
            return f"name@line{getattr(node, 'lineno', '?')} ({victim}->{replacement})"
    return None


def op_corrupt_container_op(tree: ast.Module, fn: ast.FunctionDef) -> Optional[str]:
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            site = f"subscript@line{getattr(node, 'lineno', '?')} (key={node.slice.value!r})"
            node.slice = ast.Constant(value=node.slice.value + "_corrupted")
            return site
    return None


def op_early_return(tree: ast.Module, fn: ast.FunctionDef) -> Optional[str]:
    """Insert a `return None` at a position that actually cuts logic.

    The original version always inserted at len(body)-1 -- immediately
    before the function's existing trailing statement. Every
    eval/flowbench_adapter.py-generated workflow already ends with a bare
    `return None` as that trailing statement, so the insert landed right
    before an identical statement and cut nothing: 101/101 early-return
    mutants were semantically equivalent to their base (see
    eval/results/e3_correlation_report.md's "early-return is a mutate.py
    bug" finding). Fixed by inserting at a site that necessarily precedes
    at least one real statement: index range [1, len(body)-2] always
    excludes the trailing position. Seeded by the function's own unparsed
    source (deterministic and reproducible regardless of PYTHONHASHSEED --
    random.Random on a str/bytes seed uses a fixed hash algorithm per the
    stdlib docs), not a fixed formula, so the cut position varies
    sensibly across the corpus rather than always landing on the same
    relative offset.
    """
    body = fn.body
    if len(body) < 3:
        return None
    rng = random.Random(ast.unparse(fn))
    idx = rng.randint(1, len(body) - 2)
    site_target = body[idx]
    site = f"before_stmt@line{getattr(site_target, 'lineno', '?')}"
    body.insert(idx, ast.Return(value=ast.Constant(value=None)))
    return site


def op_constant_perturb(tree: ast.Module, fn: ast.FunctionDef) -> Optional[str]:
    for node in ast.walk(fn):
        if isinstance(node, ast.Compare):
            for i, comparator in enumerate(node.comparators):
                if isinstance(comparator, ast.Constant):
                    v = comparator.value
                    if isinstance(v, bool):
                        continue
                    if isinstance(v, str):
                        new_val = v + "_MUTATED"
                    elif isinstance(v, (int, float)):
                        new_val = v + 1000
                    else:
                        continue
                    site = f"compare@line{getattr(node, 'lineno', '?')} ({v!r}->{new_val!r})"
                    node.comparators[i] = ast.Constant(value=new_val)
                    return site
    return None


OPERATORS: dict[str, Callable[[ast.Module, ast.FunctionDef], Optional[str]]] = {
    "negate-guard": op_negate_guard,
    "boundary-shift": op_boundary_shift,
    "swap-branches": op_swap_branches,
    "off-by-one-loop": op_off_by_one_loop,
    "drop-step": op_drop_step,
    "reorder-steps": op_reorder_steps,
    "wrong-variable": op_wrong_variable,
    "corrupt-container-op": op_corrupt_container_op,
    "early-return": op_early_return,
    "constant-perturb": op_constant_perturb,
}


def apply_operator(source: str, operator: str) -> Optional[tuple[str, str]]:
    """Apply *operator* to *source*. Returns (mutated_source, site) or
    None if the operator has no applicable site in this program."""
    tree = ast.parse(source)
    fn = _find_workflow(tree)
    if fn is None:
        return None
    mutated_tree = copy.deepcopy(tree)
    mutated_fn = _find_workflow(mutated_tree)
    site = OPERATORS[operator](mutated_tree, mutated_fn)
    if site is None:
        return None
    ast.fix_missing_locations(mutated_tree)
    mutated_source = ast.unparse(mutated_tree) + "\n"
    if mutated_source == source:
        return None
    return mutated_source, site


def generate_mutants(
    corpus_dir: Path = CORPUS_DIR,
    mutants_dir: Path = MUTANTS_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> list[dict[str, Any]]:
    mutants_dir.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    # Idempotent: drop any mutant entries from a previous run before
    # regenerating, so re-running this script doesn't duplicate them.
    manifest = [e for e in manifest if "base_uid" not in e]

    mutant_entries: list[dict[str, Any]] = []
    for base_file in sorted(corpus_dir.glob("uid_*.py"), key=lambda p: int(p.stem.split("_")[1])):
        uid = int(base_file.stem.split("_")[1])
        source = base_file.read_text(encoding="utf-8")
        for operator in OPERATORS:
            result = apply_operator(source, operator)
            if result is None:
                mutant_entries.append({
                    "base_uid": uid,
                    "operator": operator,
                    "site": None,
                    "applicable": False,
                    "label": "buggy",
                })
                continue
            mutated_source, site = result
            filename = f"{uid}__{operator}__{_slugify(site)}.py"
            (mutants_dir / filename).write_text(mutated_source, encoding="utf-8")
            mutant_entries.append({
                "base_uid": uid,
                "operator": operator,
                "site": site,
                "applicable": True,
                "label": "buggy",
                "source_file": f"mutants/{filename}",
            })

    manifest.extend(mutant_entries)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def regenerate_operator(
    operator: str,
    corpus_dir: Path = CORPUS_DIR,
    mutants_dir: Path = MUTANTS_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> list[dict[str, Any]]:
    """Regenerate mutants for a single *operator* only, leaving every
    other operator's mutant files and manifest entries untouched.

    Used to fix a single buggy operator (e.g. early-return) without
    invalidating the rest of the corpus's cross-report comparability --
    regenerating everything would force re-scoring every mutant, not
    just the fixed operator's.
    """
    mutants_dir.mkdir(parents=True, exist_ok=True)

    # Delete this operator's old mutant files.
    for old_file in mutants_dir.glob(f"*__{operator}__*.py"):
        old_file.unlink()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    # Drop this operator's old entries (applicable and inapplicable);
    # every other entry (corpus + all other operators) is untouched.
    manifest = [e for e in manifest if not (e.get("operator") == operator and "base_uid" in e)]

    new_entries: list[dict[str, Any]] = []
    for base_file in sorted(corpus_dir.glob("uid_*.py"), key=lambda p: int(p.stem.split("_")[1])):
        uid = int(base_file.stem.split("_")[1])
        source = base_file.read_text(encoding="utf-8")
        result = apply_operator(source, operator)
        if result is None:
            new_entries.append({
                "base_uid": uid, "operator": operator, "site": None,
                "applicable": False, "label": "buggy",
            })
            continue
        mutated_source, site = result
        filename = f"{uid}__{operator}__{_slugify(site)}.py"
        (mutants_dir / filename).write_text(mutated_source, encoding="utf-8")
        new_entries.append({
            "base_uid": uid, "operator": operator, "site": site,
            "applicable": True, "label": "buggy",
            "source_file": f"mutants/{filename}",
        })

    manifest.extend(new_entries)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return new_entries

    return mutant_entries


def _slugify(site: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in site)[:60]


if __name__ == "__main__":
    entries = generate_mutants()
    applicable = sum(1 for e in entries if e["applicable"])
    print(f"Generated {applicable} mutants ({len(entries) - applicable} inapplicable) -> {MUTANTS_DIR}")
