"""test_normalize_variants.py -- Session C, C2 screening-gate unit tests.
No network calls anywhere in this module."""

from __future__ import annotations

from eval.normalize_variants import normalize_one

CORPUS_SOURCE = (
    "def stub_a(x: str = None):\n    return {'v': x}\n\n\n"
    "def workflow(status: str) -> int:\n"
    "    a = stub_a(status)\n"
    "    return 0\n"
)


class TestNormalizeOne:
    def test_parse_error_rejected(self):
        result = normalize_one(1, "m", "def workflow(status: str)\n    pass", CORPUS_SOURCE)
        assert result["screen"] == "parse_error"

    def test_signature_mismatch_rejected(self):
        code = "def workflow(status: str, extra: int):\n    return 0\n"
        result = normalize_one(1, "m", code, CORPUS_SOURCE)
        assert result["screen"] == "signature_mismatch"

    def test_unknown_call_rejected(self):
        code = "def workflow(status: str) -> int:\n    invented_helper()\n    return 0\n"
        result = normalize_one(1, "m", code, CORPUS_SOURCE)
        assert result["screen"] == "unknown_call"
        assert result["detail"] == "invented_helper"

    def test_functionally_required_import_rejected(self):
        code = "import re\ndef workflow(status: str) -> int:\n    return len(re.findall('a', status))\n"
        result = normalize_one(1, "m", code, CORPUS_SOURCE)
        assert result["screen"] == "imports"

    def test_unused_import_stripped_not_rejected(self, tmp_path, monkeypatch):
        import eval.normalize_variants as nv
        monkeypatch.setattr(nv, "NORMALIZED_DIR", tmp_path)
        code = "import re\ndef workflow(status: str) -> int:\n    return 0\n"
        result = normalize_one(1, "m", code, CORPUS_SOURCE)
        assert result["screen"] == "pass"
        assert any("stripped_unused_imports" in a for a in result["normalization_applied"])

    def test_async_rejected(self):
        code = "async def workflow(status: str) -> int:\n    return 0\n"
        result = normalize_one(1, "m", code, CORPUS_SOURCE)
        assert result["screen"] in ("async_or_yield", "signature_mismatch", "no_single_workflow_def")
        # AsyncFunctionDef isn't a FunctionDef, so it won't even be found as
        # `workflow` by the plain-FunctionDef scan -- accept either
        # detection path as correct (both reject it).

    def test_attribute_access_rewritten_and_passes(self, tmp_path, monkeypatch):
        import eval.normalize_variants as nv
        monkeypatch.setattr(nv, "NORMALIZED_DIR", tmp_path)
        code = "def workflow(status: str) -> int:\n    a = stub_a(status)\n    return a['v']\n"
        result = normalize_one(1, "m", code, CORPUS_SOURCE)
        assert result["screen"] == "pass"
        written = (tmp_path / "1__m.py").read_text(encoding="utf-8")
        assert "def stub_a" in written  # real stub body prepended
        assert "return {'v': x}" in written

    def test_clean_variant_passes_and_writes_self_contained_file(self, tmp_path, monkeypatch):
        import eval.normalize_variants as nv
        monkeypatch.setattr(nv, "NORMALIZED_DIR", tmp_path)
        code = "def workflow(status: str) -> int:\n    stub_a(status)\n    return 0\n"
        result = normalize_one(1, "m", code, CORPUS_SOURCE)
        assert result["screen"] == "pass"
        assert result["source_file"] == "variants/normalized/1__m.py"
        assert (tmp_path / "1__m.py").exists()

    def test_model_redefined_stub_is_stripped_not_kept(self, tmp_path, monkeypatch):
        import eval.normalize_variants as nv
        monkeypatch.setattr(nv, "NORMALIZED_DIR", tmp_path)
        code = (
            "def stub_a(x=None):\n    return 'wrong'\n\n"
            "def workflow(status: str) -> int:\n    stub_a(status)\n    return 0\n"
        )
        result = normalize_one(1, "m", code, CORPUS_SOURCE)
        assert result["screen"] == "pass"
        assert "stripped_stub_redefinitions" in result["normalization_applied"]
        written = (tmp_path / "1__m.py").read_text(encoding="utf-8")
        assert "wrong" not in written  # the model's fake stub body must not survive
