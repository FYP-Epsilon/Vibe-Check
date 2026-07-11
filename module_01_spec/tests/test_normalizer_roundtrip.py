import pytest
from module_01_spec.src.formula_normalizer import FormulaNormalizer

def test_normalize_and_denormalize():
    formulas = [
        "G(start(Task_1) -> F(done(Task_1)))",
        "!done(A) W start(A)",
        "G(start(A) <-> start(B)) && G(done(A) <-> done(B))",
        "!(A) || !(B)"
    ]
    
    for f in formulas:
        norm = FormulaNormalizer.normalize(f)
        denorm = FormulaNormalizer.denormalize(norm)
        assert denorm == f

def test_normalization_details():
    assert FormulaNormalizer.normalize("A && B") == "A & B"
    assert FormulaNormalizer.normalize("A || B") == "A | B"
    assert FormulaNormalizer.normalize("start(My_Task_1)") == "start_My_Task_1"
    assert FormulaNormalizer.normalize("done(My_Task_1)") == "done_My_Task_1"
