"""nim_client.py -- minimal stdlib-only client for the NVIDIA NIM
OpenAI-compatible chat-completions API.

Used by eval/gen_variants.py (Session C: multi-implementation corpus).
No external HTTP dependency (urllib only, per session ground rules).

Key discipline: the key is read via os.getenv at call time and never
logged, printed, or returned in any exception message. `.env` (if
present, searched from the repo root down to this file's directory) is
loaded once into os.environ with setdefault, so a real OS-level env var
always wins over the file.
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

EVAL_DIR = Path(__file__).resolve().parent
MODULE02_DIR = EVAL_DIR.parent
REPO_ROOT = MODULE02_DIR.parent

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
MAX_RETRIES = 2  # total attempts = MAX_RETRIES + 1, per session budget rules
SOFT_TIMEOUT = 25  # seconds passed to urlopen's own timeout=
HARD_TIMEOUT = 35  # seconds: enforced from OUTSIDE the request thread

_env_loaded = False


def _load_env_file() -> None:
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    for d in (REPO_ROOT, MODULE02_DIR, EVAL_DIR):
        p = d / ".env"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if k and v:
                os.environ.setdefault(k, v)


def get_api_key() -> str:
    _load_env_file()
    key = os.getenv("NVIDIA_API_KEY") or os.getenv("NIM_API_KEY")
    if not key:
        raise RuntimeError(
            "NVIDIA_API_KEY (or NIM_API_KEY) is not set. Put it in .env at the "
            "repo root (NVIDIA_API_KEY=...) or export it as a real env var."
        )
    return key


class NimHTTPError(RuntimeError):
    """A well-formed HTTP error response (4xx/5xx) from the NIM API --
    distinct from a network-level failure/timeout, so callers can treat
    "model not live on this endpoint" (404) as a fast, non-retryable skip
    rather than burning the retry budget on a call that will never
    succeed."""

    def __init__(self, status_code: int, reason: str, body: str) -> None:
        super().__init__(f"HTTP {status_code} {reason} -- {body}")
        self.status_code = status_code


def _urlopen_hard_timeout(req: urllib.request.Request, soft_timeout: int, hard_timeout: int) -> bytes:
    """Run urlopen in a throwaway daemon thread and enforce *hard_timeout*
    from the calling thread, independent of urlopen's own `timeout=`.

    Observed empirically on this platform: a stalled TLS renegotiation
    (schannel) can leave urlopen blocked for HOURS past its own `timeout=`
    argument -- a single call once hung for ~3 hours with timeout=60. The
    worker thread cannot be killed (Python has no safe thread-kill), so on
    a hard-timeout it is simply abandoned as a daemon thread (never blocks
    process exit, and future calls spawn their own fresh thread rather
    than reusing a pool slot that might itself be stuck).
    """
    result_q: "queue.Queue[tuple[str, Any]]" = queue.Queue(maxsize=1)

    def _worker() -> None:
        try:
            with urllib.request.urlopen(req, timeout=soft_timeout) as resp:
                result_q.put(("ok", resp.read()))
        except Exception as e:  # noqa: BLE001 -- re-raised in the caller's thread
            result_q.put(("err", e))

    threading.Thread(target=_worker, daemon=True).start()
    try:
        kind, payload = result_q.get(timeout=hard_timeout)
    except queue.Empty:
        raise TimeoutError(f"hard timeout after {hard_timeout}s (worker thread abandoned)") from None
    if kind == "err":
        raise payload
    return payload


def _request(method: str, path: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    key = get_api_key()
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"{NIM_BASE_URL}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method=method,
    )
    last_err: Optional[str] = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            body = _urlopen_hard_timeout(req, SOFT_TIMEOUT, HARD_TIMEOUT)
            return json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")[:500]
            if 400 <= e.code < 500:
                # Client errors (e.g. 404: model not live on this endpoint)
                # won't be fixed by retrying -- fail fast, don't burn budget.
                raise NimHTTPError(e.code, e.reason, body_text) from None
            last_err = f"HTTP {e.code} {e.reason} -- {body_text}"
        except urllib.error.URLError as e:
            last_err = f"URLError: {e.reason}"
        except TimeoutError as e:
            last_err = str(e)
        if attempt < MAX_RETRIES:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"NIM {method} {path} failed after {MAX_RETRIES + 1} attempt(s): {last_err}")


def list_models() -> list[dict[str, Any]]:
    return _request("GET", "/models").get("data", [])


def chat_completion(
    model: str,
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int = 1200,
) -> dict[str, Any]:
    """One chat-completions call. Returns the raw parsed JSON response
    (caller extracts `choices[0].message.content`) so the full response
    can be cached to disk before any processing."""
    return _request(
        "POST",
        "/chat/completions",
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
    )
