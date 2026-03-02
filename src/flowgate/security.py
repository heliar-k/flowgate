"""Backward-compat shim — moved to flowgate.core.security."""
from .core.security import *  # noqa: F401, F403
from .core.security import check_secret_file_permissions  # explicit
