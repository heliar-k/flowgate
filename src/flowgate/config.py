"""Backward-compat shim — moved to flowgate.core.config."""
from .core.config import *  # noqa: F401, F403
from .core.config import ConfigError, load_router_config, PathResolver  # explicit
