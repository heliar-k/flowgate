# CLI Command Reference

This document lists the current FlowGate CLI commands and flags.

## Global Options

- `--config <path>`: Path to FlowGate config file (default: `config/flowgate.yaml`)

## Commands

### `profile`

- `flowgate profile list`
  - Lists available profiles.
- `flowgate profile set <name>`
  - Activates a profile by writing the merged LiteLLM config to `paths.active_config` and updating `paths.state_file`.
  - If `litellm` is running, FlowGate restarts it to apply changes immediately.

### `service`

- `flowgate service start [all|<service>]`
- `flowgate service stop [all|<service>]`
- `flowgate service restart [all|<service>]`

`<service>` is one of the keys under `services.*` in your config (typically `litellm` and `cliproxyapi_plus`).

### `status`

- `flowgate status`
  - Prints current profile (from state file), per-service running status (via PID files), and secret permission issues.

### `health`

- `flowgate health [--verbose]`
  - Runs comprehensive host checks (disk/memory/credentials/port conflicts) and per-service liveness/readiness checks.

### `doctor`

- `flowgate doctor`
  - Runs diagnostics for runtime directories/binaries, secret file permissions, upstream credential references, and runtime dependencies.

### `auth`

- `flowgate auth list`
  - Lists configured auth providers and whether OAuth login / headless import are supported.
- `flowgate auth status`
  - Shows auth-related configuration and secret permission issues.
- `flowgate auth login <provider> [--timeout <sec>] [--poll-interval <sec>]`
  - Fetches `login_url=...` then polls the provider status endpoint until success/failure/timeout.
- `flowgate auth import-headless <provider> [--source <path>] [--dest-dir <path>]`
  - Imports headless auth artifacts (currently: `codex`) and writes them under the auth directory.

### `integration`

- `flowgate integration print {codex|claude-code}`
  - Prints client configuration snippets.
- `flowgate integration apply {codex|claude-code} [--target <path>]`
  - Applies integration settings to the target config file and creates a timestamped backup.

### `bootstrap`

- `flowgate bootstrap download [--cliproxy-version <tag>] [--cliproxy-repo <owner/repo>]`
  - Downloads runtime artifacts and generates the LiteLLM runner script.
- `flowgate bootstrap update [--cliproxy-repo <owner/repo>] [--yes|-y]`
  - Checks for a newer CLIProxyAPIPlus release, downloads it, and restarts `cliproxyapi_plus` if running.

## Exit Codes (high level)

FlowGate commands generally follow:
- `0`: success
- `1`: runtime failure / operation failed
- `2`: configuration/usage error

Note: `argparse`-level usage errors also exit with `2`.
