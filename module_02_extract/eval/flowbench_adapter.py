"""flowbench_adapter.py -- FLOW-BENCH conditional/OOTB YAML -> executable corpus.

Turns each IBM FLOW-BENCH test case (a bare statement-list, no def/imports,
with undefined task-API calls and object-attribute guards) into a
self-contained Module 02 workflow: a ``def workflow(...):`` wrapping the
sequence, task-API calls replaced with local stub defs, and ``obj.attr``
guard reads rewritten to ``obj["attr"]`` so V2's existing Subscript/registry
handling (no ``visit_Attribute`` support) can reason about them.

Guard-controlling attributes are promoted to typed workflow parameters
(threaded through to the stub that produces the underlying object) so V1's
random generator and V2's solver can actually vary them instead of the
guard always evaluating against a fixed constant.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Optional

import yaml

EVAL_DIR = Path(__file__).resolve().parent
MODULE02_DIR = EVAL_DIR.parent
INPUT_YAML = MODULE02_DIR / "inputs" / "conditional_ootb.yaml"
CORPUS_DIR = EVAL_DIR / "corpus"
MANIFEST_PATH = EVAL_DIR / "manifest.json"


# ----------------------------------------------------------------------
# Type inference helpers
# ----------------------------------------------------------------------

def _infer_type(literal: Optional[ast.AST]) -> type:
    """Best-effort Python type from a comparison literal."""
    if isinstance(literal, ast.Constant):
        v = literal.value
        if isinstance(v, bool):
            return bool
        if isinstance(v, int):
            return int
        if isinstance(v, float):
            return float
        if isinstance(v, str):
            return str
    return str


def _default_value(t: type, i: int) -> Any:
    """A distinct default value of type *t* for slot *i* (0 or 1)."""
    if t is bool:
        return bool(i % 2)
    if t is int:
        return i
    if t is float:
        return float(i)
    return f"v{i}"


def _type_name(t: type) -> str:
    return {str: "str", int: "int", float: "float", bool: "bool"}.get(t, "str")


# ----------------------------------------------------------------------
# Attribute rewrite: obj.attr (Load) -> obj["attr"]
# ----------------------------------------------------------------------

class AttributeRewriter(ast.NodeTransformer):
    """Rewrite every attribute *read* into a subscript read.

    V2's SymbolicEvaluator has no visit_Attribute; it does support
    Subscript against the flattened registry, so this rewrite is what lets
    guards like ``incident.impact == "high"`` carry symbolic meaning.
    """

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.ctx, ast.Load):
            new_node = ast.Subscript(
                value=node.value,
                slice=ast.Constant(value=node.attr),
                ctx=ast.Load(),
            )
            return ast.copy_location(new_node, node)
        return node


# ----------------------------------------------------------------------
# Sequence analysis
# ----------------------------------------------------------------------

class SequenceAnalyzer:
    """Analyze one FLOW-BENCH sequence to find:

    * which variables are produced by which stub call (and the Call node
      itself, so we can add keyword arguments to that exact call site)
    * which variables are for-loop targets, and over which iterable
    * which (variable, attribute) pairs are read, and what literal type
      they are compared against (for parameter type inference)
    """

    def __init__(self, tree: ast.Module) -> None:
        self.tree = tree
        # var name -> (call_name, call_node)
        self.var_call: dict[str, tuple[str, ast.Call]] = {}
        # for-loop target var -> iterable var name
        self.loop_target_of: dict[str, str] = {}
        # iterable var name -> for-loop target var
        self.iterable_target: dict[str, str] = {}
        # base var -> {attr: literal type}
        self.attrs_on_var: dict[str, dict[str, type]] = {}

        self._walk_assignments_and_loops(tree.body)
        self._collect_attribute_types(tree)

    def _walk_assignments_and_loops(self, stmts: list[ast.stmt]) -> None:
        for stmt in stmts:
            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Name)
            ):
                self.var_call[stmt.targets[0].id] = (stmt.value.func.id, stmt.value)
            if isinstance(stmt, ast.For):
                if isinstance(stmt.target, ast.Name) and isinstance(stmt.iter, ast.Name):
                    self.loop_target_of[stmt.target.id] = stmt.iter.id
                    self.iterable_target[stmt.iter.id] = stmt.target.id
                self._walk_assignments_and_loops(stmt.body)
                self._walk_assignments_and_loops(stmt.orelse)
            elif isinstance(stmt, ast.If):
                self._walk_assignments_and_loops(stmt.body)
                self._walk_assignments_and_loops(stmt.orelse)

    def _collect_attribute_types(self, tree: ast.Module) -> None:
        def record(base: str, attr: str, t: type) -> None:
            slot = self.attrs_on_var.setdefault(base, {})
            # Keep the first non-default (str) inference; a later same-attr
            # hit with a more specific type can still upgrade it.
            if attr not in slot or slot[attr] is str:
                slot[attr] = t

        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                sides = [node.left, *node.comparators]
                consts = [s for s in sides if isinstance(s, ast.Constant)]
                attrs = [
                    s for s in sides
                    if isinstance(s, ast.Attribute) and isinstance(s.value, ast.Name)
                ]
                for a in attrs:
                    lit = consts[0] if consts else None
                    record(a.value.id, a.attr, _infer_type(lit))
            elif (
                isinstance(node, ast.UnaryOp)
                and isinstance(node.operand, ast.Attribute)
                and isinstance(node.operand.value, ast.Name)
            ):
                record(node.operand.value.id, node.operand.attr, bool)
            elif (
                isinstance(node, ast.If)
                and isinstance(node.test, ast.Attribute)
                and isinstance(node.test.value, ast.Name)
            ):
                record(node.test.value.id, node.test.attr, bool)

        # Safety net: any remaining bare attribute read not covered above
        # (e.g. used in an assignment RHS rather than a guard) still needs a
        # subscript key available on its base object, default type str.
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Load)
                and isinstance(node.value, ast.Name)
            ):
                self.attrs_on_var.setdefault(node.value.id, {}).setdefault(node.attr, str)


# ----------------------------------------------------------------------
# Adapter: one FLOW-BENCH sequence -> one workflow module source
# ----------------------------------------------------------------------

class AdaptedProgram:
    def __init__(self, source: str, params: dict[str, str]) -> None:
        self.source = source
        self.params = params  # param_name -> type_name, for the manifest


def adapt_sequence(sequence: str) -> AdaptedProgram:
    tree = ast.parse(sequence)
    analyzer = SequenceAnalyzer(tree)

    workflow_params: dict[str, type] = {}
    # stub call_name -> ("dict", {attr: param_name}) or ("list", {attr: (param0, param1)})
    stub_shapes: dict[str, tuple[str, dict[str, Any]]] = {}

    def ensure_dict_stub(call_name: str) -> dict[str, str]:
        shape = stub_shapes.get(call_name)
        if shape is None:
            shape = ("dict", {})
            stub_shapes[call_name] = shape
        return shape[1]

    def ensure_list_stub(call_name: str) -> dict[str, tuple[str, str]]:
        shape = stub_shapes.get(call_name)
        if shape is None:
            shape = ("list", {})
            stub_shapes[call_name] = shape
        return shape[1]

    # -- promote guard-controlling attributes to parameters --------------
    for base, attrs in analyzer.attrs_on_var.items():
        if base in analyzer.loop_target_of:
            # base is itself a for-loop target; promote via its iterable.
            iterable = analyzer.loop_target_of[base]
            call_info = analyzer.var_call.get(iterable)
            if call_info is None:
                continue
            call_name, _ = call_info
            attr_map = ensure_list_stub(call_name)
            for attr, t in attrs.items():
                p0, p1 = f"{iterable}_{attr}_0", f"{iterable}_{attr}_1"
                workflow_params[p0] = t
                workflow_params[p1] = t
                attr_map[attr] = (p0, p1)
        elif base in analyzer.var_call:
            call_name, _ = analyzer.var_call[base]
            attr_map = ensure_dict_stub(call_name)
            for attr, t in attrs.items():
                p = f"{base}_{attr}"
                workflow_params[p] = t
                attr_map[attr] = p
        # else: base is neither a stub result nor a loop target (should not
        # occur in this corpus) -- leave unpromoted; the rewritten subscript
        # read will KeyError at runtime, which V1/V2 degrade gracefully.

    # -- ensure every for-loop iterable stub returns a non-empty list ----
    # (even when the loop body never reads an attribute off the target, a
    # loop over an empty list never executes its body, so V1/V2 can't see
    # inside it at all).
    for iterable, call_info in analyzer.var_call.items():
        if iterable not in analyzer.iterable_target:
            continue
        call_name, _ = call_info
        ensure_list_stub(call_name)  # no-op if already present

    # -- every remaining distinct call name gets a no-op stub -------------
    # (create/update/delete-style calls whose result is never read via an
    # attribute or iterated still need *some* def, or the call site raises
    # NameError on every single run. Collected from every Call in the tree,
    # not just analyzer.var_call, since the same variable name reused across
    # if/else branches with different underlying calls would otherwise drop
    # one of the two call names.)
    all_call_names = {
        n.func.id for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    for call_name in all_call_names:
        if call_name == "user_task" or call_name in stub_shapes:
            continue
        stub_shapes[call_name] = ("dict", {})

    # -- add keyword arguments at each stub call site ---------------------
    for var, (call_name, call_node) in analyzer.var_call.items():
        shape = stub_shapes.get(call_name)
        if shape is None:
            continue
        kind, attr_map = shape
        if kind == "dict" and var in analyzer.attrs_on_var and var not in analyzer.loop_target_of:
            for attr in analyzer.attrs_on_var[var]:
                p = attr_map.get(attr)
                if isinstance(p, str):
                    call_node.keywords.append(ast.keyword(arg=p, value=ast.Name(id=p, ctx=ast.Load())))
        elif kind == "list" and var in analyzer.iterable_target:
            target = analyzer.iterable_target[var]
            for attr, (p0, p1) in attr_map.items():
                call_node.keywords.append(ast.keyword(arg=p0, value=ast.Name(id=p0, ctx=ast.Load())))
                call_node.keywords.append(ast.keyword(arg=p1, value=ast.Name(id=p1, ctx=ast.Load())))

    # -- rewrite obj.attr -> obj["attr"] everywhere -----------------------
    tree = AttributeRewriter().visit(tree)
    ast.fix_missing_locations(tree)

    # -- build stub defs ---------------------------------------------------
    stub_defs: list[str] = []
    for call_name, (kind, attr_map) in stub_shapes.items():
        if kind == "dict":
            params_sig = ", ".join(f"{p}: {_type_name(workflow_params[p])} = None" for p in attr_map.values())
            body_items = ", ".join(f'"{attr}": {p}' for attr, p in attr_map.items())
            stub_defs.append(f"def {call_name}({params_sig}):\n    return {{{body_items}}}")
        else:  # list
            if attr_map:
                params_sig = ", ".join(
                    f"{p}: {_type_name(workflow_params[p])} = None"
                    for p0, p1 in attr_map.values() for p in (p0, p1)
                )
                item0 = ", ".join(f'"{attr}": {p0}' for attr, (p0, p1) in attr_map.items())
                item1 = ", ".join(f'"{attr}": {p1}' for attr, (p0, p1) in attr_map.items())
                stub_defs.append(
                    f"def {call_name}({params_sig}):\n    return [{{{item0}}}, {{{item1}}}]"
                )
            else:
                stub_defs.append(f"def {call_name}():\n    return [{{'value': 0}}, {{'value': 1}}]")

    # user_task(label) -- generic stub shared across all call sites.
    used_user_task = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "user_task"
        for n in ast.walk(tree)
    )
    if used_user_task:
        stub_defs.append("def user_task(label=None):\n    return {'label': label}")

    # -- assemble the workflow function -----------------------------------
    param_items = sorted(workflow_params.items())
    sig = ", ".join(f"{name}: {_type_name(t)}" for name, t in param_items)
    body_src = ast.unparse(tree)
    indented_body = "\n".join(f"    {line}" for line in body_src.splitlines()) or "    pass"

    parts = list(stub_defs)
    parts.append(f"def workflow({sig}):\n{indented_body}\n    return None")
    module_src = "\n\n\n".join(parts) + "\n"

    params_manifest = {name: _type_name(t) for name, t in param_items}
    return AdaptedProgram(source=module_src, params=params_manifest)


# ----------------------------------------------------------------------
# Corpus generation
# ----------------------------------------------------------------------

def generate_corpus(
    input_yaml: Path = INPUT_YAML,
    corpus_dir: Path = CORPUS_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> list[dict[str, Any]]:
    with open(input_yaml, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    corpus_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []

    for test in data["tests"]:
        uid = test["_metadata"]["uid"]
        tags = test["_metadata"].get("tags", [])
        sequence = test["expected_output"]["sequence"][0]

        try:
            adapted = adapt_sequence(sequence)
        except (SyntaxError, ValueError, KeyError):
            continue

        filename = f"uid_{uid}.py"
        (corpus_dir / filename).write_text(adapted.source, encoding="utf-8")
        manifest.append({
            "uid": uid,
            "tags": tags,
            "params": adapted.params,
            "source_file": f"corpus/{filename}",
        })

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest


if __name__ == "__main__":
    entries = generate_corpus()
    print(f"Generated {len(entries)} corpus programs -> {CORPUS_DIR}")
