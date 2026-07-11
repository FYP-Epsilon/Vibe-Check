import unittest
from module_01_spec.src.ltlf_eval import evaluate_ltlf, LTLfParser, ASTNode

class TestLTLfEvaluator(unittest.TestCase):
    def test_tokenization_and_parsing(self):
        # Test atom parsing and LTL operators
        formula = "!done(T1) W start(T1)"
        parser = LTLfParser(formula)
        ast = parser.parse()
        self.assertEqual(ast.type, 'UNTIL')
        self.assertEqual(ast.value, 'W')
        self.assertEqual(ast.children[0].type, 'NOT')
        self.assertEqual(ast.children[0].children[0].type, 'ATOM')
        self.assertEqual(ast.children[0].children[0].value, 'done(T1)')
        self.assertEqual(ast.children[1].type, 'ATOM')
        self.assertEqual(ast.children[1].value, 'start(T1)')

    def test_sentinel_guard(self):
        # Sentinel template: !done(X) W start(X)
        formula = "!done(T1) W start(T1)"
        
        # Valid trace: starts, then done
        trace_valid = [
            {"start_event"},
            {"start(T1)"},
            {"done(T1)"},
            {"end_event"}
        ]
        self.assertTrue(evaluate_ltlf(formula, trace_valid))
        
        # Invalid trace: done before start
        trace_invalid = [
            {"start_event"},
            {"done(T1)"},
            {"start(T1)"},
            {"end_event"}
        ]
        self.assertFalse(evaluate_ltlf(formula, trace_invalid))
        
        # Vacuous trace: never starts, never done
        trace_vacuous = [
            {"start_event"},
            {"end_event"}
        ]
        self.assertTrue(evaluate_ltlf(formula, trace_vacuous))

    def test_sequence_flow(self):
        # Sequence template: !start(B) W done(A)
        formula = "!start(T2) W done(T1)"
        
        # Valid trace: T1 starts -> done -> T2 starts
        trace_valid = [
            {"start(T1)"},
            {"done(T1)"},
            {"start(T2)"},
            {"done(T2)"}
        ]
        self.assertTrue(evaluate_ltlf(formula, trace_valid))
        
        # Invalid trace: T2 starts before T1 done
        trace_invalid = [
            {"start(T2)"},
            {"start(T1)"},
            {"done(T1)"}
        ]
        self.assertFalse(evaluate_ltlf(formula, trace_invalid))
        
        # Vacuous trace: T2 never runs
        trace_vacuous = [
            {"start(T1)"},
            {"done(T1)"}
        ]
        self.assertTrue(evaluate_ltlf(formula, trace_vacuous))

    def test_implication_and_logical_ops(self):
        formula = "G(start(T1) -> !start(T2))"
        
        # Valid trace: T1 and T2 never run together
        trace_valid = [
            {"start(T1)"},
            {"start(T2)"}
        ]
        self.assertTrue(evaluate_ltlf(formula, trace_valid))
        
        # Invalid trace: both run in same step
        trace_invalid = [
            {"start(T1)", "start(T2)"}
        ]
        self.assertFalse(evaluate_ltlf(formula, trace_invalid))

    def test_comparisons(self):
        formula = "G(iteration_count <= 10 -> F(end))"
        
        # Valid: count <= 10, end eventually occurs
        trace_valid = [
            {"iteration_count <= 10"},
            {"end"}
        ]
        self.assertTrue(evaluate_ltlf(formula, trace_valid))
        
        # Invalid: count <= 10, end never occurs
        trace_invalid = [
            {"iteration_count <= 10"},
            {"something_else"}
        ]
        self.assertFalse(evaluate_ltlf(formula, trace_invalid))

if __name__ == "__main__":
    unittest.main()
