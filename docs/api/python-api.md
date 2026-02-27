# Python API Reference (v3)

FlowGate’s primary interface is the CLI, but its modules can be imported for automation.

## Generate full API docs

```bash
./scripts/generate_docs.sh
# or
uv run pdoc --output-dir docs/api/_generated src/flowgate
```

## Key modules

### Configuration

**`flowgate.config`**
- `load_router_config(path: str | Path) -> dict` - Loads `flowgate.yaml` and derives `services.cliproxyapi_plus` from the CLIProxyAPIPlus config.
- `merge_dicts(base: dict, overlay: dict) -> dict` - Deep merge utility.
- `ConfigError` - Raised for configuration issues.

### Process management

**`flowgate.process`**
- `ProcessSupervisor` - Start/stop/restart and PID tracking for `cliproxyapi_plus`.

### Bootstrap

**`flowgate.bootstrap`**
- Downloads the CLIProxyAPIPlus binary into `paths.runtime_dir`.

### Auth

**`flowgate.oauth`**
- `fetch_auth_url(auth_url_endpoint: str, *, timeout: float = 5) -> str`
- `poll_auth_status(status_endpoint: str, *, timeout_seconds: float, poll_interval_seconds: float) -> str`

### Integration

**`flowgate.integration`** / **`flowgate.client_apply`**
- Builds and applies client snippets targeting the local CLIProxyAPIPlus base URL.

## Example: start/stop CLIProxyAPIPlus

```python
from flowgate.process import ProcessSupervisor

supervisor = ProcessSupervisor(".router/runtime", events_log=".router/runtime/events.log")
pid = supervisor.start("cliproxyapi_plus", ["./.router/runtime/bin/CLIProxyAPIPlus", "-config", "config/cliproxyapi.yaml"])
assert supervisor.is_running("cliproxyapi_plus")
supervisor.stop("cliproxyapi_plus")
```

