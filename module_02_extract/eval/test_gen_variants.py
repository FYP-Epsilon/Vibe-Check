"""test_gen_variants.py -- Session C unit tests for the generation
pipeline. nim_client.chat_completion is ALWAYS mocked -- no test in this
module may reach the network."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from eval.gen_variants import (
    build_prompt, prompt_sha256, extract_code_block,
    _stub_defs_and_signature, generate_all,
)


CORPUS_SOURCE = (
    "def stub_a(x: str = None):\n    return {'v': x}\n\n\n"
    "def workflow(status: str) -> int:\n"
    "    a = stub_a(status)\n"
    "    return 0\n"
)


class TestStubDefsAndSignature:
    def test_extracts_signature_only_not_body(self):
        stub_sigs, sig = _stub_defs_and_signature(CORPUS_SOURCE)
        assert stub_sigs == ["def stub_a(x: str=None): ..."]
        assert "return" not in stub_sigs[0]
        assert sig == "def workflow(status: str):"

    def test_raises_without_workflow(self):
        with pytest.raises(ValueError):
            _stub_defs_and_signature("def stub_a(): return 1\n")


class TestBuildPrompt:
    def test_prompt_contains_utterance_and_signature_only(self):
        system, user = build_prompt(1, "Do the thing.", CORPUS_SOURCE)
        assert "Do the thing." in user
        assert "def stub_a(x: str=None): ..." in user
        assert "return {'v': x}" not in user  # body must not leak
        assert "def workflow(status: str):" in user
        assert "no imports" in system.lower() or "no imports" in system

    def test_prompt_hash_stable(self):
        s1, u1 = build_prompt(1, "Do the thing.", CORPUS_SOURCE)
        s2, u2 = build_prompt(1, "Do the thing.", CORPUS_SOURCE)
        assert prompt_sha256(s1, u1) == prompt_sha256(s2, u2)

    def test_prompt_hash_changes_with_utterance(self):
        s1, u1 = build_prompt(1, "Do the thing.", CORPUS_SOURCE)
        s2, u2 = build_prompt(1, "Do a different thing.", CORPUS_SOURCE)
        assert prompt_sha256(s1, u1) != prompt_sha256(s2, u2)


class TestExtractCodeBlock:
    def test_extracts_fenced_python_block(self):
        text = "Here you go:\n```python\ndef workflow(x):\n    return x\n```\nDone."
        assert extract_code_block(text) == "def workflow(x):\n    return x"

    def test_extracts_bare_fence(self):
        text = "```\ndef workflow(x):\n    return x\n```"
        assert extract_code_block(text) == "def workflow(x):\n    return x"

    def test_falls_back_to_raw_text_when_no_fence(self):
        text = "def workflow(x):\n    return x"
        assert extract_code_block(text) == text


class TestGenerateAllResumability:
    def test_skips_cached_and_never_calls_api_when_fully_cached(self, tmp_path, monkeypatch):
        import eval.gen_variants as gv
        monkeypatch.setattr(gv, "RAW_DIR", tmp_path)
        monkeypatch.setattr(gv, "MODELS", [{"id": "fake/model", "slug": "fake", "family": "x"}])

        # Pre-seed a cached raw file for uid=1.
        (tmp_path / "1__fake.json").write_text(json.dumps({
            "uid": 1, "model": "fake/model", "model_slug": "fake",
            "prompt_sha256": "x", "temperature": 0.7, "extracted_code": "def workflow(status: str):\n    return 0\n",
        }), encoding="utf-8")

        manifest = {1: {"uid": 1, "source_file": "corpus/uid_1.py"}}
        monkeypatch.setattr(gv, "_load_utterances", lambda: {1: "Do the thing."})

        real_read = gv.EVAL_DIR
        with patch.object(gv, "nim_client") as mock_client, \
             patch("pathlib.Path.read_text", return_value=CORPUS_SOURCE):
            stats = generate_all(manifest_by_uid=manifest)
            mock_client.chat_completion.assert_not_called()
        assert stats["skipped_cached"] == 1
        assert stats["calls_made"] == 0

    def test_calls_api_for_uncached_and_writes_result(self, tmp_path, monkeypatch):
        import eval.gen_variants as gv
        monkeypatch.setattr(gv, "RAW_DIR", tmp_path)
        monkeypatch.setattr(gv, "MODELS", [{"id": "fake/model", "slug": "fake", "family": "x"}])
        monkeypatch.setattr(gv, "_load_utterances", lambda: {1: "Do the thing."})

        manifest = {1: {"uid": 1, "source_file": "corpus/uid_1.py"}}
        fake_resp = {"choices": [{"message": {"content": "```python\ndef workflow(status: str):\n    return 0\n```"}}]}

        with patch.object(gv, "nim_client") as mock_client, \
             patch("pathlib.Path.read_text", return_value=CORPUS_SOURCE):
            mock_client.chat_completion.return_value = fake_resp
            stats = generate_all(manifest_by_uid=manifest)
            mock_client.chat_completion.assert_called_once()

        assert stats["calls_made"] == 1
        assert stats["failed"] == 0
        raw_file = tmp_path / "1__fake.json"
        assert raw_file.exists()
        saved = json.loads(raw_file.read_text(encoding="utf-8"))
        assert "def workflow" in saved["extracted_code"]

    def test_max_calls_this_invocation_stops_early(self, tmp_path, monkeypatch):
        import eval.gen_variants as gv
        monkeypatch.setattr(gv, "RAW_DIR", tmp_path)
        monkeypatch.setattr(gv, "MODELS", [{"id": "fake/model", "slug": "fake", "family": "x"}])
        monkeypatch.setattr(gv, "_load_utterances", lambda: {1: "a", 2: "b", 3: "c"})

        manifest = {i: {"uid": i, "source_file": f"corpus/uid_{i}.py"} for i in (1, 2, 3)}
        fake_resp = {"choices": [{"message": {"content": "def workflow(status: str):\n    return 0\n"}}]}

        with patch.object(gv, "nim_client") as mock_client, \
             patch("pathlib.Path.read_text", return_value=CORPUS_SOURCE):
            mock_client.chat_completion.return_value = fake_resp
            stats = generate_all(manifest_by_uid=manifest, max_calls_this_invocation=1)

        assert stats["calls_made"] == 1
        assert stats.get("stopped_early") is True

    def test_failed_call_is_recorded_and_loop_continues(self, tmp_path, monkeypatch):
        import eval.gen_variants as gv
        monkeypatch.setattr(gv, "RAW_DIR", tmp_path)
        monkeypatch.setattr(gv, "MODELS", [{"id": "fake/model", "slug": "fake", "family": "x"}])
        monkeypatch.setattr(gv, "_load_utterances", lambda: {1: "a"})

        manifest = {1: {"uid": 1, "source_file": "corpus/uid_1.py"}}

        with patch.object(gv, "nim_client") as mock_client, \
             patch("pathlib.Path.read_text", return_value=CORPUS_SOURCE):
            mock_client.chat_completion.side_effect = RuntimeError("boom")
            stats = generate_all(manifest_by_uid=manifest)

        assert stats["failed"] == 1
        saved = json.loads((tmp_path / "1__fake.json").read_text(encoding="utf-8"))
        assert saved["error"] == "boom"
