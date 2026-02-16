from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def check_health_url(url: str, *, timeout: float = 1.0) -> bool:
    try:
        with urlopen(url, timeout=timeout) as response:  # nosec B310
            return 200 <= response.status < 500
    except HTTPError as exc:
        return 200 <= exc.code < 500
    except (TimeoutError, URLError, OSError):
        return False
