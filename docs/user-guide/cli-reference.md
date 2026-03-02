# CLI Command Reference

This document lists the current FlowGate CLI commands and flags.

## Global Options

- `--config <path>`: Path to FlowGate config file (default: `config/flowgate.yaml`)
- `--debug`: Enable debug logging and show stack traces on internal errors
- `--format {auto,legacy,kv,json}`: Output format (default: `legacy`)
  - `legacy`: current human-oriented output per command
  - `kv`: machine-friendly `key=value` (values are JSON scalars)
  - `json`: machine-friendly single JSON object
  - `auto`: `legacy` when stdout is a TTY, otherwise `kv`
- `--quiet`: Reduce non-essential output (progress messages, hints)
- `--plain`: Avoid unicode status icons in legacy output

## Commands

### `service`

- `flowgate service start [all|<service>]`
- `flowgate service stop [all|<service>]`
- `flowgate service restart [all|<service>]`

In `config_version: 3`, FlowGate only manages a single service: `cliproxyapi_plus`.

### `status`

- `flowgate status`
  - Prints per-service running status (via PID files), cliproxy config path, and secret permission issues.

### `health`

- `flowgate health [--verbose]`
  - Runs comprehensive host checks (disk/memory/credentials/port conflicts) and per-service liveness/readiness checks.

### `doctor`

- `flowgate doctor`
  - Runs diagnostics for runtime directories/binaries, secret file permissions, and cliproxy config readability.

### `auth`

- `flowgate auth list`
  - Lists configured auth providers and whether OAuth login / headless import are supported.
- `flowgate auth status`
  - Shows auth-related configuration and secret permission issues.
- `flowgate auth login <provider> [--timeout <sec>] [--poll-interval <sec>]`
  - Fetches `login_url=...` then polls the provider status endpoint until success/failure/timeout.
- `flowgate auth import-headless <provider> [--source <path>] [--dest-dir <path>]`
  - Imports headless auth artifacts (currently: `codex`) and writes them under the auth directory.

### `bootstrap`

- `flowgate bootstrap download [--cliproxy-version <tag>] [--cliproxy-repo <owner/repo>] [--require-sha256]`
  - Downloads runtime artifacts (CLIProxyAPIPlus binary).
- `flowgate bootstrap update [--cliproxy-repo <owner/repo>] [--yes|-y] [--require-sha256]`
  - Checks for a newer CLIProxyAPIPlus release, downloads it, and restarts `cliproxyapi_plus` if running.
  - In non-interactive runs, use `--yes` to apply updates (otherwise FlowGate exits with code `2`).

## Exit Codes (high level)

FlowGate commands generally follow:
- `0`: success
- `1`: runtime failure / operation failed
- `2`: configuration/usage error

Note: `argparse`-level usage errors also exit with `2`.
