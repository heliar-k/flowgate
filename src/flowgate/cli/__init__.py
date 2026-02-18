"""
CLI package for FlowGate.

This package contains the command-line interface implementation,
including argument parsing, command handlers, and CLI utilities.
"""

# Temporary: Re-export run_cli from the old cli.py module during transition
# This allows flowgate.__init__.py to import it while we refactor
import sys
from pathlib import Path

# We need to import the cli.py module which has relative imports
# The trick is to import it as if it's part of the flowgate package
parent_module = sys.modules.get('flowgate')
if parent_module:
    # Import cli.py as flowgate._cli_legacy to avoid name collision
    import importlib.util
    _cli_module_path = Path(__file__).parent.parent / "cli.py"
    _spec = importlib.util.spec_from_file_location("flowgate._cli_legacy", _cli_module_path)
    _cli_module = importlib.util.module_from_spec(_spec)
    sys.modules['flowgate._cli_legacy'] = _cli_module
    _spec.loader.exec_module(_cli_module)

    # Export main CLI function
    run_cli = _cli_module.run_cli

    # Export internal functions that tests need to mock or import
    from .parser import build_parser
    _build_parser = build_parser  # Backward compatibility alias
    _is_service_port_available = _cli_module._is_service_port_available
    _is_executable_file = _cli_module._is_executable_file
    _runtime_dependency_available = _cli_module._runtime_dependency_available

    # Export public functions that tests mock
    ProcessSupervisor = _cli_module.ProcessSupervisor
    check_http_health = _cli_module.check_http_health
    check_secret_file_permissions = _cli_module.check_secret_file_permissions
    fetch_auth_url = _cli_module.fetch_auth_url
    get_headless_import_handler = _cli_module.get_headless_import_handler
    poll_auth_status = _cli_module.poll_auth_status
else:
    # Fallback if flowgate package not loaded yet
    def run_cli(*args, **kwargs):
        raise RuntimeError("CLI not properly initialized")

    def _build_parser(*args, **kwargs):
        raise RuntimeError("CLI not properly initialized")

    def _is_service_port_available(*args, **kwargs):
        raise RuntimeError("CLI not properly initialized")

    def _is_executable_file(*args, **kwargs):
        raise RuntimeError("CLI not properly initialized")

    def _runtime_dependency_available(*args, **kwargs):
        raise RuntimeError("CLI not properly initialized")

    ProcessSupervisor = None
    check_http_health = None
    check_secret_file_permissions = None
    fetch_auth_url = None
    get_headless_import_handler = None
    poll_auth_status = None

__all__ = ["run_cli"]
