# FlowGate

A local control tool built for `CLIProxyAPIPlus + LiteLLM` stacks.

## What this does

- Uses LiteLLM as the single northbound OpenAI-compatible endpoint
- Uses CLIProxyAPIPlus for OAuth-backed providers (Codex, GitHub Copilot)
- Supports manual policy profile switching (`reliability`, `balanced`, `cost`)
- Provides health/status/service controls from one CLI

## Requirements

- Python 3.12+
- `uv` (dependency and runtime manager)
- Network access for first-time runtime bootstrap download

## Install

```bash
export UV_CACHE_DIR=.uv-cache
uv sync --group runtime --group test
```

## Quick start

1. Copy sample config:

```bash
mkdir -p config
cp config/examples/flowgate.yaml config/flowgate.yaml
cp config/examples/cliproxyapi.yaml config/cliproxyapi.yaml
```

Generated runtime files are kept under `./.router/` (not inside `config/`).

2. Set runtime secrets:

```bash
export ROUTER_UPSTREAM_API_KEY="sk-..."
export CUSTOM_API_KEY="sk-..."
```

3. Bootstrap runtime binaries (auto download):

```bash
uv run flowgate --config config/flowgate.yaml bootstrap download
```

4. Generate active profile config:

```bash
uv run flowgate --config config/flowgate.yaml profile set balanced
```

5. Start services:

```bash
uv run flowgate --config config/flowgate.yaml service start all
```

6. Check status and health:

```bash
uv run flowgate --config config/flowgate.yaml status
uv run flowgate --config config/flowgate.yaml health
```

`health` command semantics:
- `liveness`: process supervisor sees the service process as alive.
- `readiness`: HTTP check on `services.<name>.readiness_path` (fallback: `health_path`, default: `/v1/models`) and only `2xx` is treated as ready.

7. Run preflight checks:

```bash
uv run flowgate --config config/flowgate.yaml doctor
# or
./scripts/doctor.sh config/flowgate.yaml
```

8. Run minimal smoke validation:

```bash
./scripts/smoke_local.sh config/flowgate.yaml
```

Optional controls:
- `PROFILE=reliability ./scripts/smoke_local.sh config/flowgate.yaml`
- `STARTUP_TIMEOUT=60 ./scripts/smoke_local.sh config/flowgate.yaml`

## Directory layout

- `src/flowgate/`: CLI and core modules
- `tests/`: unit/integration tests
- `config/examples/`: tracked templates
- `config/flowgate.yaml`, `config/cliproxyapi.yaml`: local runtime config (ignored)
- `.router/`: runtime binaries, active profile, pids, logs, auth artifacts (ignored)

## Observability

- Runtime lifecycle events are written to `.router/runtime/events.log` as JSON lines.
- Event fields are standardized: `event`, `service`, `profile`, `provider`, `result`, `detail`, `timestamp`.
- Typical events include `service_start`, `service_stop`, `service_restart`, `profile_switch`, `oauth_login`.

Quick inspect:

```bash
tail -n 50 .router/runtime/events.log
```

## Runtime bootstrap

`bootstrap download` will:

- Download a platform-matched `CLIProxyAPIPlus` release binary into `.router/runtime/bin/CLIProxyAPIPlus`
- Generate a `litellm` runner script at `.router/runtime/bin/litellm` (uses project environment via `uv run --project ... --group runtime`)

Custom CLIProxyAPIPlus version:

```bash
uv run flowgate --config config/flowgate.yaml \
  bootstrap download \
  --cliproxy-version v6.8.16-0
```

## OAuth login

List configured providers and supported auth actions:

```bash
uv run flowgate --config config/flowgate.yaml auth list
uv run flowgate --config config/flowgate.yaml auth status
```

Command migration quick map:
- `auth login <provider>` -> preferred command shape
- `auth import-headless <provider>` -> preferred command shape
- `auth <provider> login` -> legacy-compatible
- `auth codex import-headless` -> legacy-compatible

### Codex OAuth

```bash
uv run flowgate --config config/flowgate.yaml auth login codex --timeout 180 --poll-interval 2
```

### Codex headless import (device auth)

If you already authenticated with Codex CLI using device auth (`codex login --device-auth`),
import `~/.codex/auth.json` into CLIProxyAPI auth storage:

```bash
uv run flowgate --config config/flowgate.yaml auth import-headless codex
```

Custom source or destination:

```bash
uv run flowgate --config config/flowgate.yaml auth import-headless codex \
  --source ~/.codex/auth.json \
  --dest-dir ./.router/auths
```

If `--dest-dir` is omitted, the default is `<runtime_dir parent>/auths` (example: `./.router/auths`).

### GitHub Copilot OAuth

```bash
uv run flowgate --config config/flowgate.yaml auth login copilot --timeout 180 --poll-interval 2
```

Legacy provider-first commands are still supported for compatibility:
- `auth codex login`
- `auth codex import-headless`
- `auth copilot login`

## Add auth provider/method

Minimal extension path:
1. Add provider config under `auth.providers.<provider>` in `config/flowgate.yaml` with required endpoints for OAuth polling (`auth_url_endpoint`, `status_endpoint`) when needed.
2. For headless/device import support, register handler in `src/flowgate/auth_methods.py` via `headless_import_handlers()`.
3. Run `uv run flowgate --config config/flowgate.yaml auth list` and `auth status` to verify capability exposure.
4. Add/adjust CLI and config tests in `tests/test_cli.py` and `tests/test_config.py`.

## Strategy profiles

- `reliability`: higher retries + longer cooldown + conservative fallback
- `balanced`: default for day-to-day usage
- `cost`: lower retries + cost-first fallback chain

Switch with:

```bash
uv run flowgate --config config/flowgate.yaml profile set reliability
```

## Run tests

```bash
uv run python -m unittest discover -s tests -v
```

## Testing strategy

Test layers:
- Unit tests: core modules and pure logic (`tests/test_config.py`, `tests/test_process.py`, `tests/test_security.py`).
- Integration tests: cross-module behavior with temp runtime/config (`tests/test_cli.py`, `tests/test_integration_profile_switch.py`).
- Local smoke checks: operator flow validation on a real runtime (`doctor`, `profile set`, `service start`, `health`, `service stop`).

Recommended commands:
```bash
# unit + integration (CI baseline)
uv run python -m unittest discover -s tests -v

# optional coverage report (local quality gate)
uv run pytest --cov=src/flowgate --cov-report=term-missing
```

Coverage/acceptance baseline:
- PRs must include or update tests for affected behavior.
- Critical paths (`bootstrap`, `profile`, `auth`, `service`, `health`) must each keep at least one automated regression test.
- For non-trivial runtime behavior changes, include one local smoke validation command/result in PR notes.

## CI baseline

- Workflow file: `.github/workflows/ci.yml`
- CI currently covers:
  - `uv sync --group runtime --group test --locked`
  - `uv run python -m unittest discover -s tests -v`
  - CLI static help checks (`--help`)
- CI intentionally does not start external services or run OAuth network flows.

## Troubleshooting

- See `docs/runbook-troubleshooting.md` for common issues and direct repair commands.
- Start from:
  - `uv run flowgate --config config/flowgate.yaml status`
  - `uv run flowgate --config config/flowgate.yaml health`
  - `tail -n 50 .router/runtime/events.log`

## Release and rollback

- Follow `docs/release-and-rollback.md` for standardized release tagging and rollback steps.

## Security checks

- Run local security baseline checks:

```bash
./scripts/security_check.sh
```

- This script verifies:
  - sensitive files are not tracked by git
  - auth/secret file permissions are restrictive
  - required ignore rules exist for common secret patterns

- Recommended: run before push, or wire into CI as a non-blocking first stage.

## Notes

- Config parser accepts YAML via PyYAML when installed, and always accepts JSON (JSON is valid YAML subset).
- In this repo example, sample config is stored in JSON-compatible YAML to avoid hard dependency for parsing during bootstrap.

## Config upgrade notes

- Current schema version is `config_version: 2` (recommended to set explicitly in local config).
- If omitted, parser defaults to version `2`.
- Compatibility migration is built in for common legacy keys:
  - top-level `secrets` -> `secret_files`
  - `services.cliproxyapi` -> `services.cliproxyapi_plus`
  - top-level `oauth` -> `auth.providers`
- As of February 17, 2026, `auth.providers` is the preferred schema for new configurations.
- `oauth` input remains backward-compatible for existing local setups and is normalized internally.
