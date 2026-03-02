"""Backward-compat shim — moved to flowgate.core.auth."""
from .core.auth import *  # noqa: F401, F403
from .core.auth import headless_import_handlers, get_headless_import_handler  # explicit
