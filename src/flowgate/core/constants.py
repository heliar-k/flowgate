from __future__ import annotations

from types import MappingProxyType
from typing import Final

CLIPROXYAPI_PLUS_SERVICE: Final = "cliproxyapi_plus"

DEFAULT_SERVICE_HOST: Final = "127.0.0.1"
DEFAULT_READINESS_PATH: Final = "/v1/models"

DEFAULT_SERVICE_PORTS: MappingProxyType[str, int] = MappingProxyType(
    {
        CLIPROXYAPI_PLUS_SERVICE: 8317,
    }
)
