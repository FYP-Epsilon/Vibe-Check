import re
from typing import List, Set, Any, Tuple, Optional

# Tokenizer specification for LTLf formulas
TOKEN_SPEC = [
    ('IMPLIES', r'->'),
    ('EQUIV', r'<->'),
    ('AND', r'&&|&'),
    ('OR', r'\|\||\|'),
    ('NOT', r'!'),
    ('LTL_OP', r'\b[GfFXUW]\b'),
    ('START_ATOM', r'\bstart\([^)]+\)'),
    ('DONE_ATOM', r'\bdone\([^)]+\)'),
    # node(...) is the atomic-proposition form emitted by semantic_extractor
    # for every non-task node (see semantic_extractor.py's `node({clean_name})`).
    # Without this rule the tokenizer split it into IDENT_ATOM + LPAREN and the
    # parser raised on the nested paren, so every P0/P1 property over a node
    # proposition was unparseable. That was masked until the malformed P2
    # comment property was removed, because P2 failed first on every diagram.
    # Matches START_ATOM/DONE_ATOM in accepting any non-paren payload, so names
    # containing ':' or '.' tokenize as one atom rather than a MISMATCH.
    ('NODE_ATOM', r'\bnode\([^)]+\)'),
    ('COMP_ATOM', r'\b[a-zA-Z_][a-zA-Z0-9_]*\s*(?:<=|>=|<|>|==)\s*[a-zA-Z0-9_]+'),
    ('IDENT_ATOM', r'\b[a-zA-Z_][a-zA-Z0-9_]*'),
    ('LPAREN', r'\('),
    ('RPAREN', r'\)'),
    ('SKIP', r'[ \t\n\r]+'),
    ('MISMATCH', r'.'),
]

class ASTNode:
    """Represents a node in the LTLf AST."""
    def __init__(self, type_: str, value: Any = None, children: List['ASTNode'] = None):
        self.type = type_
        self.value = value
        self.children = children or []

    def __repr__(self) -> str:
        if not self.children:
            return f"Node({self.type}, {self.value!r})"
        return f"Node({self.type}, {self.value!r}, {self.children})"

class LTLfParser:
    """Parses LTLf formulas into an AST."""
    def __init__(self, formula: str):
        self.formula = formula
        self.tokens = self._tokenize(formula)
        self.pos = 0

    def _tokenize(self, s: str) -> List[Tuple[str, str]]:
        regex_parts = [f'(?P<{name}>{pattern})' for name, pattern in TOKEN_SPEC]
        master_regex = re.compile('|'.join(regex_parts))
        
        tokens = []
        for mo in master_regex.finditer(s):
            kind = mo.lastgroup
            value = mo.group(kind)
            if kind == 'SKIP':
                continue
            elif kind == 'MISMATCH':
                raise ValueError(f"Unexpected character {value!r} in formula {s!r}")
            tokens.append((kind, value))
        return tokens

    def peek(self) -> Optional[Tuple[str, str]]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self, expected_kind: str = None) -> Tuple[str, str]:
        tok = self.peek()
        if not tok:
            raise ValueError(f"Unexpected end of formula in {self.formula!r}")
        if expected_kind and tok[0] != expected_kind:
            raise ValueError(f"Expected token {expected_kind}, got {tok[0]} ({tok[1]}) in {self.formula!r}")
        self.pos += 1
        return tok

    def parse(self) -> ASTNode:
        node = self.parse_implies()
        if self.peek() is not None:
            raise ValueError(f"Unexpected token at end of formula: {self.peek()[1]} in {self.formula!r}")
        return node

    def parse_implies(self) -> ASTNode:
        node = self.parse_or()
        tok = self.peek()
        if tok and tok[0] in ('IMPLIES', 'EQUIV'):
            op_tok = self.consume()
            rhs = self.parse_implies()
            return ASTNode(op_tok[0], op_tok[1], [node, rhs])
        return node

    def parse_or(self) -> ASTNode:
        node = self.parse_and()
        while True:
            tok = self.peek()
            if tok and tok[0] == 'OR':
                self.consume()
                rhs = self.parse_and()
                node = ASTNode('OR', '||', [node, rhs])
            else:
                break
        return node

    def parse_and(self) -> ASTNode:
        node = self.parse_until()
        while True:
            tok = self.peek()
            if tok and tok[0] == 'AND':
                self.consume()
                rhs = self.parse_until()
                node = ASTNode('AND', '&&', [node, rhs])
            else:
                break
        return node

    def parse_until(self) -> ASTNode:
        node = self.parse_unary()
        tok = self.peek()
        if tok and tok[0] == 'LTL_OP' and tok[1] in ('U', 'W'):
            op_tok = self.consume()
            rhs = self.parse_unary()
            return ASTNode('UNTIL', op_tok[1], [node, rhs])
        return node

    def parse_unary(self) -> ASTNode:
        tok = self.peek()
        if not tok:
            raise ValueError(f"Unexpected end of formula in {self.formula!r}")
        if tok[0] == 'NOT':
            self.consume()
            child = self.parse_unary()
            return ASTNode('NOT', '!', [child])
        elif tok[0] == 'LTL_OP' and tok[1] in ('G', 'F', 'X'):
            op_tok = self.consume()
            child = self.parse_unary()
            return ASTNode(op_tok[1], op_tok[1], [child])
        elif tok[0] == 'LPAREN':
            self.consume()
            node = self.parse_implies()
            self.consume('RPAREN')
            return node
        elif tok[0] in ('START_ATOM', 'DONE_ATOM', 'NODE_ATOM', 'COMP_ATOM', 'IDENT_ATOM'):
            atom_tok = self.consume()
            return ASTNode('ATOM', atom_tok[1])
        else:
            raise ValueError(f"Unexpected token in unary expression: {tok[1]} in {self.formula!r}")

def evaluate_ast(node: ASTNode, trace: List[Set[str]], i: int) -> bool:
    """Evaluates the LTLf AST over a trace at step i."""
    N = len(trace)
    if i < 0 or i >= N:
        return False

    if node.type == 'ATOM':
        atom = node.value.strip()
        return atom in trace[i]

    elif node.type == 'NOT':
        return not evaluate_ast(node.children[0], trace, i)

    elif node.type == 'AND':
        return evaluate_ast(node.children[0], trace, i) and evaluate_ast(node.children[1], trace, i)

    elif node.type == 'OR':
        return evaluate_ast(node.children[0], trace, i) or evaluate_ast(node.children[1], trace, i)

    elif node.type == 'IMPLIES':
        return (not evaluate_ast(node.children[0], trace, i)) or evaluate_ast(node.children[1], trace, i)

    elif node.type == 'EQUIV':
        return evaluate_ast(node.children[0], trace, i) == evaluate_ast(node.children[1], trace, i)

    elif node.type == 'X':
        if i + 1 < N:
            return evaluate_ast(node.children[0], trace, i + 1)
        return False

    elif node.type == 'F':
        return any(evaluate_ast(node.children[0], trace, j) for j in range(i, N))

    elif node.type == 'G':
        return all(evaluate_ast(node.children[0], trace, j) for j in range(i, N))

    elif node.type == 'UNTIL':
        op = node.value  # 'U' or 'W'
        p = node.children[0]
        q = node.children[1]
        
        # Check strong until: there exists k in [i, N-1] s.t. q holds at k,
        # and for all j in [i, k-1], p holds.
        strong_until = False
        for k in range(i, N):
            if evaluate_ast(q, trace, k):
                if all(evaluate_ast(p, trace, j) for j in range(i, k)):
                    strong_until = True
                    break
        
        if strong_until:
            return True
        
        if op == 'W':
            # Check G p: for all j in [i, N-1], p holds.
            return all(evaluate_ast(p, trace, j) for j in range(i, N))
        
        return False

    raise ValueError(f"Unknown AST node type: {node.type}")

def evaluate_ltlf(formula: str, trace: List[Set[str]]) -> bool:
    """Parses and evaluates an LTLf formula over a finite trace."""
    if not trace:
        return False
    parser = LTLfParser(formula)
    ast = parser.parse()
    return evaluate_ast(ast, trace, 0)
