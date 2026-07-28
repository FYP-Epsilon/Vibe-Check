from dataclasses import dataclass
from typing import Optional, Set, Tuple

try:
    from .ltlf_eval import LTLfParser, ASTNode
except ImportError:
    from ltlf_eval import LTLfParser, ASTNode

@dataclass(frozen=True)
class LTLfFormula:
    op: str           # "atom", "not", "and", "or", "X", "F", "G", "U", "W", "TRUE", "FALSE"
    atom: Optional[str] = None  # Only for op="atom"
    left: 'Optional[LTLfFormula]' = None
    right: 'Optional[LTLfFormula]' = None

def TRUE() -> LTLfFormula:
    return LTLfFormula(op="TRUE")

def FALSE() -> LTLfFormula:
    return LTLfFormula(op="FALSE")

def is_true(f: LTLfFormula) -> bool:
    return f.op == "TRUE"

def is_false(f: LTLfFormula) -> bool:
    return f.op == "FALSE"

def _convert(node: ASTNode) -> LTLfFormula:
    if node.type == "TRUE": return TRUE()
    if node.type == "FALSE": return FALSE()
    if node.type == "ATOM": return LTLfFormula(op="atom", atom=node.value.strip())
    if node.type == "NOT": return LTLfFormula(op="not", left=_convert(node.children[0]))
    if node.type == "AND": return LTLfFormula(op="and", left=_convert(node.children[0]), right=_convert(node.children[1]))
    if node.type == "OR": return LTLfFormula(op="or", left=_convert(node.children[0]), right=_convert(node.children[1]))
    
    if node.type == "IMPLIES":
        left = _convert(node.children[0])
        right = _convert(node.children[1])
        return LTLfFormula(op="or", left=LTLfFormula(op="not", left=left), right=right)
        
    if node.type == "EQUIV":
        left = _convert(node.children[0])
        right = _convert(node.children[1])
        t1 = LTLfFormula(op="and", left=left, right=right)
        t2 = LTLfFormula(op="and", left=LTLfFormula(op="not", left=left), right=LTLfFormula(op="not", left=right))
        return LTLfFormula(op="or", left=t1, right=t2)
        
    if node.type == "X": return LTLfFormula(op="X", left=_convert(node.children[0]))
    if node.type == "F": return LTLfFormula(op="F", left=_convert(node.children[0]))
    if node.type == "G": return LTLfFormula(op="G", left=_convert(node.children[0]))
    if node.type == "UNTIL":
        return LTLfFormula(op=node.value, left=_convert(node.children[0]), right=_convert(node.children[1]))
        
    raise ValueError(f"Unknown node type {node.type}")

def parse(formula_string: str) -> LTLfFormula:
    parser = LTLfParser(formula_string)
    return _convert(parser.parse())

def simplify(f: LTLfFormula) -> LTLfFormula:
    if f.op in ("TRUE", "FALSE", "atom"):
        return f
        
    left = simplify(f.left) if f.left else None
    right = simplify(f.right) if f.right else None
    
    if f.op == "not":
        if is_true(left): return FALSE()
        if is_false(left): return TRUE()
        if left.op == "not": return left.left
        return LTLfFormula(op="not", left=left)
        
    if f.op == "and":
        if is_false(left) or is_false(right): return FALSE()
        if is_true(left): return right
        if is_true(right): return left
        if left == right: return left
        return LTLfFormula(op="and", left=left, right=right)
        
    if f.op == "or":
        if is_true(left) or is_true(right): return TRUE()
        if is_false(left): return right
        if is_false(right): return left
        if left == right: return left
        return LTLfFormula(op="or", left=left, right=right)
        
    if f.op == "X":
        return LTLfFormula(op="X", left=left)
        
    if f.op == "F":
        if is_true(left): return TRUE()
        if is_false(left): return FALSE()
        return LTLfFormula(op="F", left=left)
        
    if f.op == "G":
        if is_true(left): return TRUE()
        if is_false(left): return FALSE()
        return LTLfFormula(op="G", left=left)
        
    if f.op in ("U", "W"):
        if is_true(right): return TRUE()
        if is_false(right):
            if f.op == "U": return FALSE()
            if f.op == "W": return simplify(LTLfFormula(op="G", left=left))
            
        if is_false(left): return right
        if is_true(left) and f.op == "U": return simplify(LTLfFormula(op="F", left=right))
        if is_true(left) and f.op == "W": return TRUE()
        
        return LTLfFormula(op=f.op, left=left, right=right)
        
    return f

def progress(f: LTLfFormula, P: Set[str]) -> LTLfFormula:
    if f.op == "TRUE": return TRUE()
    if f.op == "FALSE": return FALSE()
    
    if f.op == "atom":
        return TRUE() if f.atom in P else FALSE()
        
    if f.op == "not":
        return LTLfFormula(op="not", left=progress(f.left, P))
        
    if f.op == "and":
        return LTLfFormula(op="and", left=progress(f.left, P), right=progress(f.right, P))
        
    if f.op == "or":
        return LTLfFormula(op="or", left=progress(f.left, P), right=progress(f.right, P))
        
    if f.op == "X":
        return f.left
        
    if f.op == "F":
        return LTLfFormula(op="or", left=progress(f.left, P), right=f)
        
    if f.op == "G":
        return LTLfFormula(op="and", left=progress(f.left, P), right=f)
        
    if f.op in ("U", "W"):
        prog_psi = progress(f.right, P)
        prog_phi = progress(f.left, P)
        
        t1 = LTLfFormula(op="and", left=prog_phi, right=f)
        return LTLfFormula(op="or", left=prog_psi, right=t1)
        
    raise ValueError(f"Unknown op {f.op}")

def is_satisfied_at_end(f: LTLfFormula) -> bool:
    if f.op == "TRUE": return True
    if f.op == "FALSE": return False
    if f.op == "atom": return False
    if f.op == "not": return not is_satisfied_at_end(f.left)
    if f.op == "and": return is_satisfied_at_end(f.left) and is_satisfied_at_end(f.right)
    if f.op == "or": return is_satisfied_at_end(f.left) or is_satisfied_at_end(f.right)
    if f.op == "X": return False
    if f.op == "F": return False
    if f.op == "G": return True
    if f.op == "U": return False
    if f.op == "W": return True
    return False

def extract_obligations(f: LTLfFormula) -> Tuple[Set[str], Set[str], Set[str]]:
    must_true = set()
    must_false = set()
    
    def _extract(n: LTLfFormula, sign: bool):
        if n.op in ("TRUE", "FALSE"): return
        if n.op == "and" and sign:
            _extract(n.left, True)
            _extract(n.right, True)
        elif n.op == "or" and not sign:
            _extract(n.left, False)
            _extract(n.right, False)
        elif n.op == "not":
            _extract(n.left, not sign)
        elif n.op == "atom":
            if sign: must_true.add(n.atom)
            else: must_false.add(n.atom)
            
    _extract(f, True)
    
    def _current(n: LTLfFormula) -> Set[str]:
        if n.op == "X": return set()
        if n.op == "atom": return {n.atom}
        res = set()
        if n.left: res |= _current(n.left)
        if n.right: res |= _current(n.right)
        return res
        
    curr = _current(f)
    free = curr - must_true - must_false
    return must_true, must_false, free
