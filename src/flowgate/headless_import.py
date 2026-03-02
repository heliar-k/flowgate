"""Backward-compat shim — moved to flowgate.core.auth."""
from .core.auth import *  # noqa: F401, F403
from .core.auth import import_codex_headless_auth, OUTPUT_FILENAME  # explicit
