"""Backward-compat shim — functions moved to flowgate.core modules."""
from __future__ import annotations

from .core.bootstrap import is_executable_file as _is_executable_file  # noqa: F401
from .core.process import is_port_available as _is_service_port_available  # noqa: F401
