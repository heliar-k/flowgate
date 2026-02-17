from __future__ import annotations

import json
import time
from urllib.request import urlopen


def _get_json(url: str, timeout: float) -> dict:
    with urlopen(url, timeout=timeout) as response:  # nosec B310
        body = response.read().decode("utf-8")
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("OAuth endpoint must return a JSON object")
    return data


def fetch_auth_url(auth_url_endpoint: str, *, timeout: float = 5.0) -> str:
    payload = _get_json(auth_url_endpoint, timeout)

    for key in ("auth_url", "url", "login_url"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value

    raise ValueError("OAuth auth-url endpoint did not return auth_url/url/login_url")


def poll_auth_status(
    status_endpoint: str,
    *,
    timeout_seconds: float = 120,
    poll_interval_seconds: float = 2,
) -> str:
    success_states = {"success", "completed", "authorized", "ok"}
    failed_states = {"failed", "error", "denied", "expired", "cancelled"}

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
        if status in success_states:
            return status
        if status in failed_states:
            raise RuntimeError(f"OAuth login failed with status: {status}")
        time.sleep(poll_interval_seconds)

    detail = f"OAuth login timed out; last status={last_status}"
    if last_error:
        detail = f"{detail}; last error={last_error}"
    raise TimeoutError(detail)
