"""mutate.py -- targeted, order-aware mutations for the full-pipeline eval
harness (demo/eval_e2e/harness.py).

FLOW-BENCH has no native correctness labels for real LLM implementations
(see .claude/memory/flowbench_groundtruth_finding.md) -- only injected,
known-class mutations give a defensible ground truth, mirroring how
module_02_extract/eval's own mutation corpus grounds its E1 detection-rate
measurement. Two disjoint mutation classes, chosen because M03's checkable
properties are exclusively node()-free P1 ordering/occurrence constraints
(see property_ingest.py's docstring) -- they are the only classes an
ordering-only checker can be expected to see at all:

  - Order-changing (``drop_step``, ``swap_adjacent``): removes or reorders
    one of the driver's own top-level calls to a sibling task function.
    Candidate genuine-violation test cases -- "candidate" because whether a
    specific ordering constraint is actually broken depends on which BPMN
    task each call semantically matched to, not on the mutation alone; the
    harness verifies that per-mutant against gold's own matched atoms
    rather than assuming it (see harness.py's ``applicable_properties``).

  - Order-preserving (``perturb_constant``): rewrites a numeric/string
    literal that is not itself a driver call argument selecting which
    sibling function runs. Candidate false-alarm test cases -- verified
    order-preserving by comparing the mutant's own call-order WIR task
    sequence against gold's, not assumed from the mutation's intent.

Only targets simple, non-branching, non-looping top-level statements in the
driver body (``ast.Expr``/``ast.Assign`` containing exactly one call to a
distinct sibling function) -- real LLM-generated drivers in this corpus are
straight-line call sequences (verified: every one of the 6 gold specs this
harness uses has an all-straight-line or partially-straight-line driver),
so this scope covers the mutation targets that exist without having to
reason about loop/branch semantics under mutation.
"""

from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MutationCandidate:
    kind: str            # "drop_step" | "swap_adjacent" | "perturb_constant"
    label: str            # human-readable, e.g. "drop stmt 1 (call to X)"
    source: str            # the mutated module source
    affected_calls: tuple[str, ...]  # sibling call name(s) this mutation touches


def _driver_def(tree: ast.Module, driver_name: str) -> Optional[ast.FunctionDef]:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == driver_name:
            return node
    return None


def _sibling_names(tree: ast.Module) -> set[str]:
    return {
        c.name for c in tree.body
        if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _single_call_targets(driver_body: list[ast.stmt], sibling_names: set[str], driver_name: str) -> list[tuple[int, str]]:
    """Indices (within driver_body) of simple, non-branching statements that
    call exactly one distinct sibling function -- the only statements safe
    to drop or reorder without reasoning about branch/loop semantics."""
    targets: list[tuple[int, str]] = []
    for i, stmt in enumerate(driver_body):
        if isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
            continue
        if not isinstance(stmt, (ast.Expr, ast.Assign)):
            continue
        calls = {
            n.func.id for n in ast.walk(stmt)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id in sibling_names and n.func.id != driver_name
        }
        if len(calls) == 1:
            targets.append((i, next(iter(calls))))
    return targets


def generate_order_mutations(source: str, driver_name: str) -> list[MutationCandidate]:
    """``drop_step`` (remove one statement) and ``swap_adjacent`` (swap two
    of the simple single-call statements) candidates. Requires >=2 simple
    single-call targets for swap_adjacent; drop_step only needs >=2 total
    targets so the sequence isn't emptied to a single task."""
    tree = ast.parse(source)
    driver = _driver_def(tree, driver_name)
    if driver is None:
        return []
    sibling_names = _sibling_names(tree)
    targets = _single_call_targets(driver.body, sibling_names, driver_name)
    if len(targets) < 2:
        return []

    out: list[MutationCandidate] = []

    for idx, call_name in targets:
        mutant_tree = copy.deepcopy(tree)
        mutant_driver = _driver_def(mutant_tree, driver_name)
        del mutant_driver.body[idx]
        ast.fix_missing_locations(mutant_tree)
        out.append(MutationCandidate(
            kind="drop_step",
            label=f"drop stmt {idx} (call to {call_name})",
            source=ast.unparse(mutant_tree) + "\n",
            affected_calls=(call_name,),
        ))

    for k in range(len(targets) - 1):
        i, name_i = targets[k]
        j, name_j = targets[k + 1]
        if name_i == name_j:
            continue  # same task repeated (e.g. a loop-adjacent duplicate); not a real reorder
        mutant_tree = copy.deepcopy(tree)
        mutant_driver = _driver_def(mutant_tree, driver_name)
        mutant_driver.body[i], mutant_driver.body[j] = mutant_driver.body[j], mutant_driver.body[i]
        ast.fix_missing_locations(mutant_tree)
        out.append(MutationCandidate(
            kind="swap_adjacent",
            label=f"swap stmts {i}<->{j} ({name_i} <-> {name_j})",
            source=ast.unparse(mutant_tree) + "\n",
            affected_calls=(name_i, name_j),
        ))

    return out


def call_sequence(source: str, driver_name: str) -> tuple[str, ...]:
    """The ordered sequence of sibling-function call names encountered while
    walking the driver body in source order (descending into branches/loops
    in place, never reordering) -- a source-level proxy for "did this
    mutation change the call order" that harness.py uses to verify a
    perturb_constant mutant is genuinely order-preserving, rather than
    assuming it from the mutation's intent."""
    tree = ast.parse(source)
    driver = _driver_def(tree, driver_name)
    if driver is None:
        return ()
    sibling_names = _sibling_names(tree)
    calls: list[str] = []

    def walk_stmts(stmts: list[ast.stmt]) -> None:
        for stmt in stmts:
            for node in ast.walk(stmt):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in sibling_names and node.func.id != driver_name:
                        calls.append(node.func.id)

    walk_stmts(driver.body)
    return tuple(calls)


class _ConstantPerturber(ast.NodeTransformer):
    """Rewrites the first eligible literal it finds; ``found`` records
    whether one was rewritten (a no-op mutation is not a valid test case)."""

    def __init__(self, skip_stmt_ids: set[int]) -> None:
        self.skip_ids = skip_stmt_ids
        self.found = False

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if self.found:
            return node
        if id(node) in self.skip_ids:
            return node
        if isinstance(node.value, bool) or node.value is None:
            return node
        if isinstance(node.value, (int, float)):
            self.found = True
            return ast.copy_location(ast.Constant(value=node.value + 1), node)
        if isinstance(node.value, str) and node.value:
            self.found = True
            return ast.copy_location(ast.Constant(value=node.value + "_x"), node)
        return node


def generate_constant_perturbation(source: str, driver_name: str) -> Optional[MutationCandidate]:
    """One order-preserving literal perturbation, skipping any constant that
    is itself a keyword argument at a driver call site (those select which
    stub/branch runs, so touching them isn't guaranteed order-preserving).
    Returns None if no eligible constant exists."""
    tree = ast.parse(source)
    driver = _driver_def(tree, driver_name)
    skip_ids: set[int] = set()
    if driver is not None:
        for stmt in driver.body:
            for node in ast.walk(stmt):
                if isinstance(node, ast.Call):
                    for kw in node.keywords:
                        if isinstance(kw.value, ast.Constant):
                            skip_ids.add(id(kw.value))

    # skip_ids were collected from this same `tree` object (a fresh parse,
    # not shared elsewhere in this function) -- mutate it directly rather
    # than a deepcopy, whose node ids would no longer match skip_ids.
    perturber = _ConstantPerturber(skip_ids)
    mutant_tree = perturber.visit(tree)
    if not perturber.found:
        return None
    ast.fix_missing_locations(mutant_tree)
    return MutationCandidate(
        kind="perturb_constant",
        label="perturb one non-driver-selecting literal",
        source=ast.unparse(mutant_tree) + "\n",
        affected_calls=(),
    )
