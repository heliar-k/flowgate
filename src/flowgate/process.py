"""Backward-compat shim — moved to flowgate.core.process."""
from .core.process import *  # noqa: F401, F403
from .core.process import ProcessSupervisor, ProcessError  # explicit
