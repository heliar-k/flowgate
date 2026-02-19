# FlowGate Data Flows

This document describes the key data flows within FlowGate, detailing how data moves through the system, which modules are involved, and what transformations occur at each step.

## Table of Contents

1. [Configuration Loading Flow](#1-configuration-loading-flow)
2. [Profile Switching Flow](#2-profile-switching-flow)
3. [Service Startup Flow](#3-service-startup-flow)
4. [OAuth Authentication Flow](#4-oauth-authentication-flow)
5. [Credential Resolution Flow](#5-credential-resolution-flow)

---

## 1. Configuration Loading Flow

### Overview

Configuration loading is the foundation of FlowGate's operation. The system loads a YAML configuration file, validates its schema, normalizes legacy formats, resolves all paths, and prepares it for use by other components.

### Flow Steps

```
User provides config path
    ↓
cli.py: parse_args() → config_path
    ↓
config.py: load_config(config_path)
    ↓
config.py: _read_config_file() → raw YAML dict
    ↓
config.py: _normalize_config_keys() → normalized dict
    ↓
validators.py: validate_config_structure() → validated dict
    ↓
path_resolver.py: PathResolver.resolve_all_paths() → resolved dict
    ↓
Return final config to CLI
```

### Involved Modules

**`src/flowgate/cli.py`**:
- Function: `main()`, `parse_args()`
- Responsibility: Parse command-line arguments and extract config path
- Input: Command-line arguments
- Output: Config path string

**`src/flowgate/config.py`**:
- Function: `load_config(config_path: str) -> dict`
- Responsibility: Orchestrate config loading, normalization, validation
- Input: Config file path
- Output: Validated configuration dictionary

**`src/flowgate/config.py`**:
- Function: `_read_config_file(path: str) -> dict`
- Responsibility: Read and parse YAML file
- Input: Config file path
- Output: Raw YAML dictionary

**`src/flowgate/config.py`**:
- Function: `_normalize_config_keys(config: dict) -> dict`
- Responsibility: Convert legacy v1 keys to v2 format
- Input: Raw config dict
- Output: Normalized config dict with version 2 schema

**`src/flowgate/validators.py`**:
- Function: `validate_config_structure(config: dict) -> None`
- Responsibility: Validate required keys and structure
- Input: Normalized config dict
- Output: Raises `ConfigError` if invalid

**`src/flowgate/config_utils/path_resolver.py`**:
- Function: `PathResolver.resolve_all_paths(config: dict) -> dict`
- Responsibility: Resolve all relative paths to absolute paths
- Input: Validated config dict
- Output: Config dict with resolved paths

### Data Transformations

**Step 1: Raw YAML**
```yaml
# config/flowgate.yaml
config_version: 2
paths:
  runtime_dir: .router/runtime  # Relative path
services:
  litellm:
    command:
      cwd: .router/runtime      # Relative path
```

**Step 2: After Normalization** (legacy keys converted)
```python
{
    "config_version": 2,
    "paths": {"runtime_dir": ".router/runtime"},
    "services": {
        "litellm": {"command": {"cwd": ".router/runtime"}}
    }
}
```

**Step 3: After Path Resolution**
```python
{
    "config_version": 2,
    "paths": {"runtime_dir": "/Users/user/flowgate/.router/runtime"},
    "services": {
        "litellm": {"command": {"cwd": "/Users/user/flowgate/.router/runtime"}}
    }
}
```

### Error Handling

- **File not found**: Raise `ConfigError("Config file not found: {path}")`
- **Invalid YAML**: Raise `ConfigError("Failed to parse config: {error}")`
- **Missing required keys**: Raise `ConfigError("Missing required key: {key}")`
- **Invalid path**: Raise `ConfigError("Path does not exist: {path}")`

### Example Usage

```python
from flowgate.config import load_config

config = load_config("config/flowgate.yaml")
runtime_dir = config["paths"]["runtime_dir"]  # Absolute path
```

---

## 2. Profile Switching Flow

### Overview

Profile switching allows users to change LiteLLM's behavior by applying different policy overlays (reliability, balanced, cost). The flow merges base configuration with profile-specific settings, resolves credential references, writes the active configuration, and optionally restarts services.

### Flow Steps

```
User runs: flowgate profile set balanced
    ↓
cli.py: dispatch to profile_set command
    ↓
profile.py: switch_profile(config, profile_name)
    ↓
profile.py: validate profile exists in config["profiles"]
    ↓
profile.py: merge_dicts(litellm_base, profile_overlay)
    ↓
profile.py: _resolve_model_api_key_refs(merged_config)
    ↓
profile.py: _read_api_key_from_file(credential_path)
    ↓
profile.py: _atomic_write(active_config.yaml)
    ↓
profile.py: _atomic_write(state.json)
    ↓
profile.py: check if litellm is running
    ↓
process.py: is_running("litellm")
    ↓ (if running)
profile.py: restart LiteLLM service
    ↓
process.py: restart_service("litellm")
    ↓
Return success message
```

### Involved Modules

**`src/flowgate/cli/commands/profile_commands.py`**:
- Function: `profile_set()`
- Responsibility: Handle CLI command for profile switching
- Input: Config, profile name
- Output: Success/error message

**`src/flowgate/profile.py`**:
- Function: `switch_profile(config: dict, profile_name: str) -> None`
- Responsibility: Orchestrate profile switch
- Input: Config dict, profile name
- Output: Writes active config and state files

**`src/flowgate/config.py`**:
- Function: `merge_dicts(base: dict, overlay: dict) -> dict`
- Responsibility: Deep merge two dictionaries
- Input: Base dict, overlay dict
- Output: Merged dict

**`src/flowgate/profile.py`**:
- Function: `_resolve_model_api_key_refs(config: dict) -> dict`
- Responsibility: Replace `api_key_ref` with actual API keys
- Input: Config with references
- Output: Config with resolved credentials

**`src/flowgate/profile.py`**:
- Function: `_read_api_key_from_file(path: str) -> str`
- Responsibility: Read API key from credential file
- Input: Credential file path
- Output: API key string

**`src/flowgate/profile.py`**:
- Function: `_atomic_write(path: Path, content: str) -> None`
- Responsibility: Atomically write file (tmp + rename)
- Input: File path, content
- Output: File written

**`src/flowgate/process.py`**:
- Function: `ProcessSupervisor.is_running(service: str) -> bool`
- Responsibility: Check if service is running
- Input: Service name
- Output: Boolean

**`src/flowgate/process.py`**:
- Function: `ProcessSupervisor.restart_service(service: str) -> None`
- Responsibility: Restart service (stop + start)
- Input: Service name
- Output: Service restarted

### Data Transformations

**Step 1: Base Configuration** (`litellm_base`)
```yaml
model_list:
  - model_name: gpt-4
    litellm_params:
      api_key_ref: openai
router_settings:
  num_retries: 1
```

**Step 2: Profile Overlay** (`profiles.balanced`)
```yaml
router_settings:
  num_retries: 2
  timeout: 30
litellm_settings:
  success_callback: ["langfuse"]
```

**Step 3: Merged Configuration**
```yaml
model_list:
  - model_name: gpt-4
    litellm_params:
      api_key_ref: openai
router_settings:
  num_retries: 2        # Overridden by profile
  timeout: 30           # Added by profile
litellm_settings:
  success_callback: ["langfuse"]
```

**Step 4: Resolved Credentials**
```yaml
model_list:
  - model_name: gpt-4
    litellm_params:
      api_key: sk-abc123...  # Resolved from .router/secrets/openai.key
router_settings:
  num_retries: 2
  timeout: 30
litellm_settings:
  success_callback: ["langfuse"]
```

**Step 5: Written to Active Config**
- File: `.router/runtime/active_config.yaml`
- Format: YAML (pretty-printed)

**Step 6: State File**
```json
{
  "active_profile": "balanced",
  "timestamp": "2026-02-19T10:30:00Z"
}
```

### Error Handling

- **Profile not found**: Raise `ValueError(f"Profile '{name}' not found in config")`
- **Credential file missing**: Raise `ValueError(f"Credential file not found: {path}")`
- **Write failure**: Raise `OSError` if atomic write fails
- **Service restart failure**: Raise `ProcessError` if restart fails

### Example Usage

```bash
# Switch to reliability profile (high retries, fallbacks)
flowgate --config config/flowgate.yaml profile set reliability

# Switch to cost profile (fewer retries, cheaper models)
flowgate --config config/flowgate.yaml profile set cost
```

---

## 3. Service Startup Flow

### Overview

Service startup involves spawning managed processes (LiteLLM, CLIProxyAPIPlus), tracking their PIDs, validating ports, and logging events. The flow ensures services start cleanly and are properly supervised.

### Flow Steps

```
User runs: flowgate service start all
    ↓
cli.py: dispatch to service_start command
    ↓
process.py: validate_port_availability(host, port)
    ↓
process.py: ProcessSupervisor.start(service_name)
    ↓
process.py: check if already running (PID file + process check)
    ↓ (if not running)
process.py: prepare command arguments
    ↓
process.py: prepare environment variables
    ↓
process.py: subprocess.Popen(command, env=env)
    ↓
process.py: write PID to .router/runtime/pids/<service>.pid
    ↓
process.py: log_event("service_start", service_name)
    ↓
process.py: optional health check (HTTP GET to /health)
    ↓
Return success message
```

### Involved Modules

**`src/flowgate/cli/commands/service_commands.py`**:
- Function: `service_start()`
- Responsibility: Handle CLI command for service start
- Input: Config, service names
- Output: Success/error message

**`src/flowgate/process.py`**:
- Function: `ProcessSupervisor.start(service_name: str) -> None`
- Responsibility: Spawn and track service process
- Input: Service name
- Output: Process started, PID recorded

**`src/flowgate/process.py`**:
- Function: `ProcessSupervisor.is_running(service: str) -> bool`
- Responsibility: Check if service is already running
- Input: Service name
- Output: Boolean

**`src/flowgate/process.py`**:
- Function: `ProcessSupervisor._prepare_command(service: dict) -> list[str]`
- Responsibility: Build command arguments from config
- Input: Service config dict
- Output: Command argument list

**`src/flowgate/process.py`**:
- Function: `ProcessSupervisor._prepare_env(service: dict) -> dict`
- Responsibility: Prepare environment variables
- Input: Service config dict
- Output: Environment dict

**`src/flowgate/process.py`**:
- Function: `ProcessSupervisor._write_pid(service: str, pid: int) -> None`
- Responsibility: Write PID to file
- Input: Service name, PID
- Output: PID file created

**`src/flowgate/process.py`**:
- Function: `ProcessSupervisor.log_event(event: str, **kwargs) -> None`
- Responsibility: Append event to JSON log
- Input: Event type, metadata
- Output: Event logged to `.router/runtime/events.log`

### Data Structures

**Service Configuration**
```python
{
    "litellm": {
        "command": {
            "executable": ".router/bin/litellm_runner.sh",
            "args": ["--config", ".router/runtime/active_config.yaml"],
            "cwd": ".router/runtime"
        },
        "host": "127.0.0.1",
        "port": 4000,
        "env": {
            "DATABASE_URL": "file:.router/runtime/litellm_cache.db"
        }
    }
}
```

**PID File**
```
# .router/runtime/pids/litellm.pid
12345
```

**Event Log Entry**
```json
{
  "event": "service_start",
  "service": "litellm",
  "timestamp": "2026-02-19T10:30:00Z",
  "pid": 12345,
  "result": "success"
}
```

### Port Validation

Before starting a service, FlowGate validates that the configured port is available:

```python
import socket

def validate_port_availability(host: str, port: int) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
    except OSError:
        raise ProcessError(f"Port {port} is already in use")
```

### Error Handling

- **Port conflict**: Raise `ProcessError(f"Port {port} already in use")`
- **Binary not found**: Raise `ProcessError(f"Executable not found: {path}")`
- **Spawn failure**: Raise `ProcessError(f"Failed to start {service}: {error}")`
- **Permission denied**: Raise `ProcessError(f"Permission denied: {path}")`

### Example Usage

```bash
# Start all services
flowgate --config config/flowgate.yaml service start all

# Start specific service
flowgate --config config/flowgate.yaml service start litellm

# Check status
flowgate --config config/flowgate.yaml status
```

---

## 4. OAuth Authentication Flow

### Overview

OAuth authentication enables FlowGate to authenticate with OAuth-backed providers (Codex, GitHub Copilot) using a browser-based device authorization flow. The flow fetches an authorization URL, polls for completion, and stores credentials.

### Flow Steps

```
User runs: flowgate auth login codex --timeout 180
    ↓
cli.py: dispatch to auth_login command
    ↓
oauth.py: fetch_auth_url(auth_url_endpoint)
    ↓
oauth.py: HTTP GET https://api.codex.com/auth_url
    ↓
oauth.py: parse JSON response → {url, token}
    ↓
oauth.py: display URL to user
    ↓
User: opens URL in browser, completes auth
    ↓
oauth.py: poll_auth_status(status_endpoint, timeout=180)
    ↓
oauth.py: loop every 2 seconds
    ↓
oauth.py: HTTP GET https://api.codex.com/status?token=xxx
    ↓
oauth.py: parse JSON response → {status, credentials}
    ↓ (if status == "success")
oauth.py: extract credentials from response
    ↓
oauth.py: write .router/auth/codex.json
    ↓
oauth.py: log_event("oauth_login", provider="codex", result="success")
    ↓
Return success message
```

### Involved Modules

**`src/flowgate/cli/commands/auth_commands.py`**:
- Function: `auth_login()`
- Responsibility: Handle CLI command for OAuth login
- Input: Config, provider name, timeout
- Output: Success/error message

**`src/flowgate/oauth.py`**:
- Function: `fetch_auth_url(auth_url_endpoint: str) -> str`
- Responsibility: Fetch authorization URL from provider
- Input: Auth URL endpoint
- Output: Authorization URL string

**`src/flowgate/oauth.py`**:
- Function: `poll_auth_status(status_endpoint: str, timeout_seconds: float) -> str`
- Responsibility: Poll status endpoint until success/failure/timeout
- Input: Status endpoint, timeout
- Output: Credentials JSON string

**`src/flowgate/oauth.py`**:
- Function: `_get_json(url: str, timeout: float) -> dict`
- Responsibility: Make HTTP GET request and parse JSON
- Input: URL, timeout
- Output: JSON dict

**`src/flowgate/auth_methods.py`**:
- Function: `save_auth_artifact(provider: str, credentials: dict, auth_dir: Path) -> None`
- Responsibility: Save credentials to auth artifact file
- Input: Provider name, credentials, auth directory
- Output: File written to `.router/auth/<provider>.json`

### Data Structures

**Auth URL Response**
```json
{
  "url": "https://codex.com/device?code=ABC123",
  "auth_url": "https://codex.com/device?code=ABC123",
  "token": "poll_token_xyz"
}
```

**Status Polling Response (Pending)**
```json
{
  "status": "pending",
  "message": "Waiting for user authorization"
}
```

**Status Polling Response (Success)**
```json
{
  "status": "success",
  "credentials": {
    "access_token": "abc123...",
    "refresh_token": "def456...",
    "expires_at": 1708430400
  }
}
```

**Auth Artifact File** (`.router/auth/codex.json`)
```json
{
  "access_token": "abc123...",
  "refresh_token": "def456...",
  "expires_at": 1708430400,
  "provider": "codex"
}
```

### Polling Logic

```python
def poll_auth_status(status_endpoint: str, timeout_seconds: float = 120) -> str:
    success_states = {"success", "completed", "authorized", "ok"}
    failed_states = {"failed", "error", "denied", "expired"}

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        payload = _get_json(status_endpoint, timeout=5)
        status = payload.get("status", "unknown").lower()

        if status in success_states:
            return json.dumps(payload.get("credentials", {}))
        elif status in failed_states:
            raise ValueError(f"Auth failed: {status}")

        time.sleep(2)  # Poll every 2 seconds

    raise TimeoutError("OAuth polling timed out")
```

### Error Handling

- **Network error**: Raise `OSError` if HTTP request fails
- **Invalid response**: Raise `ValueError` if JSON is malformed
- **Timeout**: Raise `TimeoutError` if polling exceeds timeout
- **User denied**: Raise `ValueError("Auth failed: denied")`
- **Write failure**: Raise `OSError` if credential file write fails

### Alternative: Headless Import

For environments without browser access or when credentials already exist:

```bash
flowgate auth import-headless codex --source ~/.codex/auth.json
```

**Flow**:
```
User runs: flowgate auth import-headless codex --source ~/.codex/auth.json
    ↓
cli.py: dispatch to auth_import_headless command
    ↓
auth_methods.py: load handler for provider
    ↓
auth_methods.py: read source file
    ↓
auth_methods.py: validate credentials structure
    ↓
auth_methods.py: write to .router/auth/codex.json
    ↓
auth_methods.py: log_event("auth_import", provider="codex")
    ↓
Return success message
```

### Example Usage

```bash
# OAuth login with browser
flowgate --config config/flowgate.yaml auth login codex --timeout 180

# Headless import
flowgate --config config/flowgate.yaml auth import-headless codex --source ~/.codex/auth.json

# Check auth status
flowgate --config config/flowgate.yaml auth status
```

---

## 5. Credential Resolution Flow

### Overview

Credential resolution is the process of replacing placeholder references (`api_key_ref`) in configuration with actual API keys from credential files. This ensures sensitive credentials are never stored in configuration files.

### Flow Steps

```
Configuration contains: api_key_ref: openai
    ↓
profile.py: _resolve_model_api_key_refs(config)
    ↓
profile.py: _upstream_credentials(config) → {"openai": ".router/secrets/openai.key"}
    ↓
profile.py: iterate over model_list
    ↓
profile.py: find api_key_ref in litellm_params
    ↓
profile.py: lookup credential file path
    ↓
profile.py: _read_api_key_from_file(path)
    ↓
profile.py: read file, strip whitespace
    ↓
profile.py: replace api_key_ref with api_key
    ↓
Return config with resolved credentials
```

### Involved Modules

**`src/flowgate/profile.py`**:
- Function: `_resolve_model_api_key_refs(config: dict) -> dict`
- Responsibility: Replace all `api_key_ref` with actual keys
- Input: Config with references
- Output: Config with resolved credentials

**`src/flowgate/profile.py`**:
- Function: `_upstream_credentials(config: dict) -> dict[str, str]`
- Responsibility: Extract credential file mappings
- Input: Config dict
- Output: Dict of {credential_name: file_path}

**`src/flowgate/profile.py`**:
- Function: `_read_api_key_from_file(path: str) -> str`
- Responsibility: Read and validate API key from file
- Input: Credential file path
- Output: API key string

### Data Transformations

**Step 1: Configuration with References**
```yaml
credentials:
  upstream:
    openai:
      file: .router/secrets/openai.key
    anthropic:
      file: .router/secrets/anthropic.key

model_list:
  - model_name: gpt-4
    litellm_params:
      api_key_ref: openai
  - model_name: claude-3-opus
    litellm_params:
      api_key_ref: anthropic
```

**Step 2: Credential Mapping Extracted**
```python
{
    "openai": "/absolute/path/to/.router/secrets/openai.key",
    "anthropic": "/absolute/path/to/.router/secrets/anthropic.key"
}
```

**Step 3: Credential Files Read**
```python
# .router/secrets/openai.key
sk-abc123...

# .router/secrets/anthropic.key
sk-ant-def456...
```

**Step 4: References Resolved**
```yaml
model_list:
  - model_name: gpt-4
    litellm_params:
      api_key: sk-abc123...     # Resolved
  - model_name: claude-3-opus
    litellm_params:
      api_key: sk-ant-def456... # Resolved
```

### Security Considerations

1. **File Permissions**: Credential files should have mode `0600` (owner read/write only)
2. **No Logging**: Credentials are never logged or printed
3. **Gitignore**: `.router/secrets/` is gitignored
4. **Atomic Writes**: Credentials written atomically to prevent partial writes
5. **No Environment Variables**: Credentials stored in files, not env vars (except for edge cases)

### Environment Variable Fallback

For credentials that can't be stored in files:

```yaml
model_list:
  - model_name: custom-model
    litellm_params:
      api_key: ${CUSTOM_API_KEY}  # Read from environment
```

**Resolution**:
```python
import os

if value.startswith("${") and value.endswith("}"):
    env_var = value[2:-1]
    return os.environ.get(env_var, "")
```

### Error Handling

- **Credential file not found**: Raise `ValueError(f"Credential file not found: {path}")`
- **Credential file empty**: Raise `ValueError(f"Credential file is empty: {path}")`
- **Invalid reference**: Raise `ValueError(f"Unknown credential reference: {ref}")`
- **Permission denied**: Raise `PermissionError(f"Cannot read credential file: {path}")`

### Example Credential Files

**`.router/secrets/openai.key`**:
```
sk-abc123def456ghi789jkl012mno345pqr678stu901
```

**`.router/secrets/anthropic.key`**:
```
sk-ant-api03-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
```

**Best Practices**:
- One API key per file
- No extra whitespace (stripped automatically)
- No comments or metadata in key files
- Mode `0600` permissions

### Example Usage

```bash
# Create credential file
echo "sk-abc123..." > .router/secrets/openai.key
chmod 600 .router/secrets/openai.key

# Verify resolution
flowgate --config config/flowgate.yaml profile set balanced
# Credentials are resolved during profile switch
```

---

## Related Documentation

- [Architecture Diagrams](diagrams.md) - Visual representations of these flows
- [C4 Architecture Diagrams](README.md) - Comprehensive system architecture
- [Component Details](c4-components-cli.md) - In-depth component descriptions
- [CLAUDE.md](../../CLAUDE.md) - Developer guide with code examples

---

**Last Updated**: 2026-02-19
