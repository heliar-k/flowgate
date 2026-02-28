"""Shared utility functions for FlowGate.

This module contains common utility functions used across multiple modules
to avoid code duplication.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path


def _is_executable_file(path: Path) -> bool:
    """Check if a file exists and is executable."""
    return path.exists() and path.is_file() and os.access(path, os.X_OK)


def _is_service_port_available(host: str, port: int) -> bool:
    """Check if a service port is available for binding."""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((host, port))
    except OSError:
        return False
    return True
