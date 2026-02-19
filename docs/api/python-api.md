# Python API Reference

Auto-generated API documentation for FlowGate modules.

## Overview

FlowGate provides a Python API for programmatic interaction with its components. While the primary interface is the CLI, the underlying modules can be imported and used directly for custom integrations or automation.

## Generated Documentation

Complete API documentation is auto-generated using [pdoc](https://pdoc.dev/) and can be found in the `_generated/` directory.

To generate the latest API docs:

```bash
./scripts/generate_docs.sh
```

Or manually:

```bash
uv run pdoc --output-dir docs/api/_generated src/flowgate
```

## Key Modules

### Configuration Management

**`flowgate.config`** - Configuration loading and validation
- `load_config(config_path: str) -> dict` - Load and validate configuration
- `merge_dicts(base: dict, overlay: dict) -> dict` - Deep merge dictionaries
- `ConfigError` - Exception for configuration errors

**`flowgate.config_utils.path_resolver`** - Path resolution utilities
- `PathResolver` - Unified path resolution class
- `resolve_all_paths(config: dict) -> dict` - Resolve relative paths to absolute

**`flowgate.validators`** - Configuration validators
- `validate_config_structure(config: dict) -> None` - Validate config schema
- `validate_service_config(service: dict) -> None` - Validate service definition

### Profile Management

**`flowgate.profile`** - Policy profile management
- `switch_profile(config: dict, profile_name: str) -> None` - Switch active profile
- `list_profiles(config: dict) -> list[str]` - List available profiles
- `get_active_profile(state_file: str) -> str | None` - Get current profile

### Process Management

**`flowgate.process`** - Service lifecycle management
- `ProcessSupervisor` - Main process management class
  - `start(service_name: str) -> None` - Start a service
  - `stop(service_name: str) -> None` - Stop a service
  - `restart(service_name: str) -> None` - Restart a service
  - `is_running(service_name: str) -> bool` - Check if service is running
  - `get_status(service_name: str) -> dict` - Get service status
- `ProcessError` - Exception for process operations

### Authentication

**`flowgate.oauth`** - OAuth authentication flows
- `fetch_auth_url(auth_url_endpoint: str) -> str` - Fetch authorization URL
- `poll_auth_status(status_endpoint: str, timeout_seconds: float) -> str` - Poll auth status

**`flowgate.auth_methods`** - Authentication method handlers
- `save_auth_artifact(provider: str, credentials: dict, auth_dir: Path) -> None` - Save credentials
- `load_auth_artifact(provider: str, auth_dir: Path) -> dict | None` - Load credentials
- `headless_import_handlers()` - Registry of headless import handlers

### Bootstrap

**`flowgate.bootstrap`** - Runtime bootstrap utilities
- `download_cliproxy_binary(version: str, platform: str, arch: str, dest: Path) -> None` - Download binary
- `generate_litellm_runner(dest: Path, python_path: str) -> None` - Generate runner script
- `detect_platform() -> tuple[str, str]` - Detect OS and architecture

### Integration

**`flowgate.integration`** - Client integration utilities
- `generate_config_snippet(client: str, config: dict) -> str` - Generate config snippet
- `apply_config_to_client(client: str, config: dict, backup: bool) -> None` - Apply config

**`flowgate.client_apply`** - Client configuration application
- `apply_codex_config(settings: dict) -> None` - Apply settings to Codex CLI
- `apply_claude_code_config(settings: dict) -> None` - Apply settings to Claude Code

### CLI Commands

**`flowgate.cli.commands`** - CLI command implementations
- `profile_commands` - Profile management commands
- `auth_commands` - Authentication commands
- `service_commands` - Service management commands
- `health_commands` - Health check commands
- `bootstrap_commands` - Bootstrap commands
- `integration_commands` - Integration commands

## Usage Examples

### Loading Configuration

```python
from flowgate.config import load_config

config = load_config("config/flowgate.yaml")
runtime_dir = config["paths"]["runtime_dir"]
```

### Managing Profiles

```python
from flowgate.profile import switch_profile, list_profiles

profiles = list_profiles(config)
print(f"Available profiles: {profiles}")

switch_profile(config, "balanced")
```

### Managing Services

```python
from flowgate.process import ProcessSupervisor

supervisor = ProcessSupervisor(runtime_dir=".router/runtime")

# Start a service
supervisor.start("litellm")

# Check status
if supervisor.is_running("litellm"):
    status = supervisor.get_status("litellm")
    print(f"LiteLLM PID: {status['pid']}")

# Stop service
supervisor.stop("litellm")
```

### OAuth Authentication

```python
from flowgate.oauth import fetch_auth_url, poll_auth_status

# Fetch auth URL
auth_url = fetch_auth_url("https://api.codex.com/auth_url")
print(f"Visit: {auth_url}")

# Poll for completion
credentials = poll_auth_status(
    "https://api.codex.com/status?token=xxx",
    timeout_seconds=120
)
```

## Type Hints

FlowGate uses Python 3.11+ type hints for all public functions. Enable type checking with mypy:

```bash
uv run mypy src/flowgate/
```

## Exception Hierarchy

```
Exception
├── RuntimeError
│   ├── ProcessError (process.py)
│   └── ConfigError (config.py)
├── ValueError
│   └── (Used for validation errors)
└── OSError
    └── (Used for file I/O errors)
```

## Development

### Regenerating Documentation

After making code changes, regenerate the API docs:

```bash
./scripts/generate_docs.sh
```

### Adding Docstrings

Follow Google-style docstrings for all public functions:

```python
def example_function(arg: str, count: int = 1) -> list[str]:
    """Short description of function.

    Longer description with more details about what the function does,
    its behavior, and any important notes.

    Args:
        arg: Description of arg parameter
        count: Description of count parameter (default: 1)

    Returns:
        Description of return value

    Raises:
        ValueError: When arg is empty
        ConfigError: When configuration is invalid

    Example:
        >>> example_function("test", count=2)
        ['test', 'test']
    """
    pass
```

## Related Documentation

- [Architecture Diagrams](../architecture/diagrams.md) - System architecture visualizations
- [Data Flows](../architecture/data-flows.md) - Detailed data flow documentation
- [C4 Architecture](../architecture/README.md) - C4 model diagrams
- [CLAUDE.md](../../CLAUDE.md) - Developer guide and coding conventions

---

**Last Updated**: 2026-02-19
