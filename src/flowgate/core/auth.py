"""Authentication: OAuth polling, headless import, provider registry."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable
from pathlib import Path
from urllib.request import urlopen

from flowgate.core.observability import measure_time

_SUCCESS_STATES = frozenset({"success", "completed", "authorized", "ok"})
_FAILED_STATES = frozenset({"failed", "error", "denied", "expired", "cancelled"})

OUTPUT_FILENAME = "codex-headless-import.json"
KIRO_SCAN_LOCATIONS = (
    Path("~/.kiro/kiro-auth-token.json"),
    Path("~/.aws/sso/cache/kiro-auth-token.json"),
)

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


def _write_auth_payload(
    payload: dict[str, str], dest_dir: str | Path, filename: str
) -> Path:
    dst_dir = Path(dest_dir).expanduser().resolve()
    dst_dir.mkdir(parents=True, exist_ok=True)
    out = dst_dir / filename
    out.write_text(json.dumps(payload), encoding="utf-8")
    out.chmod(0o600)
    return out


def _resolve_explicit_source(source: str | Path) -> Path | None:
    source_text = str(source).strip()
    if not source_text:
        return None

    src = Path(source_text).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source auth file not found: {src}")
    return src


def _sanitize_file_part(value: str) -> str:
    cleaned = "".join(
        ch.lower() if ch.isalnum() else "-" for ch in value.strip().lower()
    )
    normalized = "-".join(part for part in cleaned.split("-") if part)
    return normalized


def _extract_email_from_jwt(access_token: str) -> str:
    parts = access_token.split(".")
    if len(parts) < 2:
        return ""

    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(f"{payload}{padding}".encode("ascii"))
        data = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return ""

    if not isinstance(data, dict):
        return ""

    email = data.get("email")
    if isinstance(email, str):
        return email.strip()
    return ""


def _kiro_identifier(data: dict[str, object], email: str) -> str:
    if email:
        return _sanitize_file_part(email)

    profile_arn = str(data.get("profileArn", "")).strip()
    if profile_arn:
        profile_id = profile_arn.rsplit("/", 1)[-1]
        sanitized = _sanitize_file_part(profile_id)
        if sanitized:
            return sanitized

    client_id = str(data.get("clientId", "")).strip()
    if client_id:
        sanitized = _sanitize_file_part(client_id)
        if sanitized:
            return sanitized

    return f"imported-{int(time.time())}"


def _resolve_kiro_source(source: str | Path) -> Path:
    explicit = _resolve_explicit_source(source)
    if explicit is not None:
        return explicit

    checked_paths: list[str] = []
    for location in KIRO_SCAN_LOCATIONS:
        candidate = location.expanduser().resolve()
        checked_paths.append(str(candidate))
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Kiro IDE token file not found; checked="
        + ",".join(checked_paths if checked_paths else ["none"])
    )


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
    src = _resolve_explicit_source(source)
    if src is None:
        src = Path("~/.codex/auth.json").expanduser().resolve()
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

    return _write_auth_payload(payload, dest_dir, OUTPUT_FILENAME)


@measure_time("oauth_import_headless")
def import_kiro_headless_auth(source: str | Path, dest_dir: str | Path) -> Path:
    src = _resolve_kiro_source(source)
    data = _load_json(src)

    access_token = str(data.get("accessToken", "")).strip()
    refresh_token = str(data.get("refreshToken", "")).strip()
    expires_at = str(data.get("expiresAt", "")).strip()
    if not access_token:
        raise ValueError("Headless auth file missing accessToken")
    if not refresh_token:
        raise ValueError("Headless auth file missing refreshToken")
    if not expires_at:
        raise ValueError("Headless auth file missing expiresAt")

    email = str(data.get("email", "")).strip() or _extract_email_from_jwt(access_token)
    provider = str(data.get("provider", "")).strip() or "imported"
    provider_slug = _sanitize_file_part(provider) or "imported"
    identifier = _kiro_identifier(data, email)
    filename = f"kiro-{provider_slug}-{identifier}.json"

    payload = {
        "type": "kiro",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "profile_arn": str(data.get("profileArn", "")).strip(),
        "expires_at": expires_at,
        "auth_method": str(data.get("authMethod", "")).strip().lower(),
        "provider": provider,
        "client_id": str(data.get("clientId", "")).strip(),
        "client_secret": str(data.get("clientSecret", "")).strip(),
        "client_id_hash": str(data.get("clientIdHash", "")).strip(),
        "email": email,
        "region": str(data.get("region", "")).strip(),
        "start_url": str(data.get("startUrl", "")).strip(),
    }
    return _write_auth_payload(payload, dest_dir, filename)


# ── Provider registry ─────────────────────────────────────────


def headless_import_handlers() -> dict[str, HeadlessImportHandler]:
    return {
        "codex": import_codex_headless_auth,
        "kiro": import_kiro_headless_auth,
    }


def get_headless_import_handler(provider: str) -> HeadlessImportHandler | None:
    return headless_import_handlers().get(provider)
