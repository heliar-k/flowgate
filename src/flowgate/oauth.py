"""Backward-compat shim — moved to flowgate.core.auth."""
from .core.auth import *  # noqa: F401, F403
from .core.auth import fetch_auth_url, poll_auth_status  # explicit
