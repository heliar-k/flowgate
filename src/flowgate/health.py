from __future__ import annotations

from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


class HttpHealthResult(TypedDict):
    ok: bool
    status_code: int | None
    error: str | None


def check_http_health(url: str, *, timeout: float = 1.0) -> HttpHealthResult:
    try:
        with urlopen(url, timeout=timeout) as response:  # nosec B310
            return {
                "ok": 200 <= response.status < 300,
                "status_code": response.status,
                "error": None,
            }
    except HTTPError as exc:
        return {"ok": False, "status_code": exc.code, "error": None}
    except (TimeoutError, URLError, OSError) as exc:
        return {"ok": False, "status_code": None, "error": type(exc).__name__}


def check_health_url(url: str, *, timeout: float = 1.0) -> bool:
    # Backward-compatible helper kept for existing call sites/tests.
    return check_http_health(url, timeout=timeout)["ok"]
