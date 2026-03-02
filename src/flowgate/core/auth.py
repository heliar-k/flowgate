"""Authentication: OAuth polling, headless import, provider registry."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from urllib.request import urlopen

from .observability import measure_time

_SUCCESS_STATES = frozenset({"success", "completed", "authorized", "ok"})
_FAILED_STATES = frozenset({"failed", "error", "denied", "expired", "cancelled"})

OUTPUT_FILENAME = "codex-headless-import.json"

HeadlessImportHandler = Callable[[str, str], Path]


def _get_json(url: str, timeout: float) -> dict:
    with urlopen(url, timeout=timeout) as response:  # nosec B310
        body = response.read().decode("utf-8")
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("OAuth endpoint must return a JSON object")
    return data


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError("Headless auth file must be a JSON object")
    return data


# ── OAuth helpers ────────────────────────────────────────────

@measure_time("oauth_fetch_auth_url")
def fetch_auth_url(auth_url_endpoint: str, *, timeout: float = 5.0) -> str:
    payload = _get_json(auth_url_endpoint, timeout)

    for key in ("auth_url", "url", "login_url"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value

    raise ValueError("OAuth auth-url endpoint did not return auth_url/url/login_url")


@measure_time("oauth_poll_status")
def poll_auth_status(
    status_endpoint: str,
    *,
    timeout_seconds: float = 120,
    poll_interval_seconds: float = 2,
) -> str:
    deadline = time.time() + timeout_seconds
    last_status = "unknown"
    last_error: str | None = None
    while time.time() < deadline:
        try:
            payload = _get_json(status_endpoint, timeout=5)
            last_error = None
        except (TimeoutError, OSError) as exc:
            last_error = str(exc)
            time.sleep(poll_interval_seconds)
            continue

        status_raw = payload.get("status", "unknown")
        status = str(status_raw).strip().lower()
        last_status = status
        if status in _SUCCESS_STATES:
            return status
        if status in _FAILED_STATES:
            raise RuntimeError(f"OAuth login failed with status: {status}")
        time.sleep(poll_interval_seconds)

    detail = f"OAuth login timed out; last status={last_status}"
    if last_error:
        detail = f"{detail}; last error={last_error}"
    raise TimeoutError(detail)


# ── Headless import ───────────────────────────────────────────

@measure_time("oauth_import_headless")
def import_codex_headless_auth(source: str | Path, dest_dir: str | Path) -> Path:
    src = Path(source).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source auth file not found: {src}")

    data = _load_json(src)
    tokens = data.get("tokens")
    if not isinstance(tokens, dict):
        raise ValueError("Headless auth file missing tokens object")

    access_token = str(tokens.get("access_token", "")).strip()
    refresh_token = str(tokens.get("refresh_token", "")).strip()
    id_token = str(tokens.get("id_token", "")).strip()
    account_id = str(tokens.get("account_id", "")).strip()

    if not access_token:
        raise ValueError("Headless auth file missing tokens.access_token")
    if not refresh_token:
        raise ValueError("Headless auth file missing tokens.refresh_token")

    payload = {
        "type": "codex",
        "token_type": "bearer",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "id_token": id_token,
        "account_id": account_id,
    }

    dst_dir = Path(dest_dir).expanduser().resolve()
    dst_dir.mkdir(parents=True, exist_ok=True)
    out = dst_dir / OUTPUT_FILENAME
    out.write_text(json.dumps(payload), encoding="utf-8")
    out.chmod(0o600)
    return out


# ── Provider registry ─────────────────────────────────────────

def headless_import_handlers() -> dict[str, HeadlessImportHandler]:
    return {
        "codex": import_codex_headless_auth,
    }


def get_headless_import_handler(provider: str) -> HeadlessImportHandler | None:
    return headless_import_handlers().get(provider)
