from __future__ import annotations

from types import MappingProxyType
from typing import Final

LITELLM_SERVICE: Final = "litellm"
CLIPROXYAPI_PLUS_SERVICE: Final = "cliproxyapi_plus"

DEFAULT_SERVICE_HOST: Final = "127.0.0.1"
DEFAULT_READINESS_PATH: Final = "/v1/models"

DEFAULT_SERVICE_PORTS: MappingProxyType[str, int] = MappingProxyType(
    {
        LITELLM_SERVICE: 4000,
        CLIPROXYAPI_PLUS_SERVICE: 8317,
    }
)

DEFAULT_SERVICE_READINESS_PATHS: MappingProxyType[str, str] = MappingProxyType(
    {
        LITELLM_SERVICE: "/health",
        CLIPROXYAPI_PLUS_SERVICE: "/",
    }
)
