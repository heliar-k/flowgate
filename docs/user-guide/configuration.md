# Configuration Guide (config_version 3)

FlowGate v3 is a small control-plane wrapper around **CLIProxyAPIPlus**. FlowGate reads your CLIProxyAPIPlus config and derives the managed service from it.

## FlowGate config (`flowgate.yaml`)

### Schema

Required:
- `config_version: 3`
- `paths.runtime_dir`
- `paths.log_file`
- `cliproxyapi_plus.config_file`

Optional:
- `auth.providers` (OAuth endpoints are optional; FlowGate can derive them)
- `secret_files`

### Minimal example

```yaml
config_version: 3

paths:
  runtime_dir: "../.router/runtime"
  log_file: "../.router/runtime/events.log"

cliproxyapi_plus:
  config_file: "cliproxyapi.yaml"

auth:
  providers:
    codex: {}
    copilot: {}
    kiro: {}
```

## CLIProxyAPIPlus config (`cliproxyapi.yaml`)

FlowGate derives `host` and `port` from this file, and starts the CLIProxyAPIPlus binary with:

```bash
CLIProxyAPIPlus -config <cliproxyapi.yaml>
```

Minimal example:

```yaml
host: "127.0.0.1"
port: 8317

# Where FlowGate auth artifacts are written by default.
auth-dir: "./.router/auths"

# Client API keys (Codex / Claude Code / your tools use one of these keys).
api-keys:
  - "sk-local-test"

# Required for `/v0/management/...` endpoints (used by `flowgate auth login`).
remote-management:
  allow-remote: false
  secret-key: "change-me-management-key"
```

## How FlowGate Derives the Service

At config load time, FlowGate:
1) Resolves `cliproxyapi_plus.config_file` relative to the FlowGate config location
2) Parses the file to read `host` (default `127.0.0.1`) and `port` (required)
3) Builds an internal `services.cliproxyapi_plus` entry used by `service/health/doctor/auth`

## Auth Provider Endpoints (optional)

For `auth login`, if `auth_url_endpoint` / `status_endpoint` are missing, FlowGate derives them from the cliproxy `host:port`:

- Codex:
  - `http://<host>:<port>/v0/management/oauth/codex/auth-url`
  - `http://<host>:<port>/v0/management/oauth/codex/status`
- Copilot:
  - `http://<host>:<port>/v0/management/oauth/github-copilot/auth-url`
  - `http://<host>:<port>/v0/management/oauth/github-copilot/status`

Kiro is supported too, but FlowGate does not derive its endpoints automatically.
Configure them explicitly:

- Kiro:
  - `http://<host>:<port>/v0/management/kiro-auth-url`
  - `http://<host>:<port>/v0/management/get-auth-status?provider=kiro`

## Path Resolution

- Paths in `flowgate.yaml` are resolved relative to the config file location.
- `cliproxyapi_plus.config_file` supports relative or absolute paths.

## Version Migration

### v2 → v3 (hard break)

FlowGate v3 removes legacy routing/profile features and only manages CLIProxyAPIPlus.

- Removed: legacy `services` + routing config + `profiles` + `credentials`
- Removed `profile` command
- New: `cliproxyapi_plus.config_file`
- `paths` reduced to: `runtime_dir`, `log_file`

Validate:

```bash
uv run flowgate --config config/flowgate.yaml doctor
```
