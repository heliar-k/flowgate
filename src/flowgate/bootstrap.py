"""Backward-compat shim — moved to flowgate.core.bootstrap."""
from .core.bootstrap import *  # noqa: F401, F403
from .core.bootstrap import (
    DEFAULT_CLIPROXY_REPO,
    DEFAULT_CLIPROXY_VERSION,
    detect_platform,
    pick_release_asset,
    http_get_json,
    download_cliproxyapi_plus,
    validate_cliproxy_binary,
)
