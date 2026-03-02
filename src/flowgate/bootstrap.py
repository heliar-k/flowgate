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
    _http_get_bytes,
    _extract_sha256_from_checksum_text,
    _find_expected_sha256,
    _extract_binary_from_bytes,
)
