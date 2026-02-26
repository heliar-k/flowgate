# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FlowGate is a local control tool for managing `CLIProxyAPIPlus + LiteLLM` stacks. It provides unified management of LiteLLM (northbound OpenAI-compatible endpoint) and CLIProxyAPIPlus (OAuth-backed providers like Codex, GitHub Copilot) with policy profile switching and service lifecycle management.

## Architecture

For detailed docs: [Architecture Overview](docs/architecture/README.md), [Diagrams](docs/architecture/diagrams.md), [Data Flows](docs/architecture/data-flows.md), [API Reference](docs/api/python-api.md).

### Key Components

- **CLI** (`src/flowgate/cli/`): BaseCommand pattern, @handle_command_errors decorator, argparse subcommands
- **Config** (`src/flowgate/config.py`, `config_utils/`): Schema v2 validation, PathResolver for path resolution, credential management
- **Process** (`src/flowgate/process.py`): ProcessSupervisor for service lifecycle, PID tracking in `.router/runtime/pids/`, port conflict detection
- **Profile** (`src/flowgate/profile.py`): Policy switching (reliability/balanced/cost), deep merge base + overlay, `api_key_ref` resolution, auto-restart on change
- **Auth** (`src/flowgate/oauth.py`, `auth_methods.py`): OAuth polling, headless import, multi-provider (Codex, GitHub Copilot)
- **Bootstrap** (`src/flowgate/bootstrap.py`): Platform-specific binary downloads, LiteLLM runner script generation
- **Integration** (`src/flowgate/integration.py`, `client_apply.py`): Client config snippets (Codex, Claude Code), automated config updates

### Key Data Flows

1. **Profile Activation**: `profile set <name>` → merge base + overlay → resolve credentials → write active config → auto-restart LiteLLM
2. **Service Start**: `service start all` → validate ports → spawn processes → record PIDs → log events
3. **OAuth Login**: `auth login codex` → fetch auth URL → poll status → write auth artifact → record event

## Directory Layout

- `src/flowgate/`: Main package (`config.py`, `config_utils/`, `cli/`, `process.py`, `profile.py`, `oauth.py`, `bootstrap.py`, `validators.py`)
- `tests/`: Unit + integration tests
- `config/examples/`: Sample configs
- `.router/`: Runtime artifacts (gitignored)
- `scripts/`: Helper scripts (`xgate`, `xtest`, `smoke_local.sh`, `security_check.sh`, `generate_docs.sh`)

## Common Commands

```bash
# Setup
uv sync --group test

# Run CLI
uv run flowgate --config config/flowgate.yaml <command>

# Bootstrap
uv run flowgate --config config/flowgate.yaml bootstrap download
uv run flowgate --config config/flowgate.yaml bootstrap update --yes

# Profile & Service
uv run flowgate --config config/flowgate.yaml profile list
uv run flowgate --config config/flowgate.yaml profile set balanced
uv run flowgate --config config/flowgate.yaml service start all
uv run flowgate --config config/flowgate.yaml service stop all
uv run flowgate --config config/flowgate.yaml status
uv run flowgate --config config/flowgate.yaml health

# Auth
uv run flowgate --config config/flowgate.yaml auth login codex --timeout 180
uv run flowgate --config config/flowgate.yaml auth import-headless codex --source ~/.codex/auth.json

# Config migration (v1 deprecated, removed in v0.3.0)
uv run flowgate --config config/flowgate.yaml config migrate --dry-run
uv run flowgate --config config/flowgate.yaml config migrate

# Testing
uv run pytest tests/ -v                    # unit tests only (default)
uv run pytest tests/ -v -m integration     # integration tests only
uv run pytest tests/ -v -m ""              # all tests
uv run pytest tests/test_config.py -v      # specific file
uv run pytest --cov=src/flowgate --cov-report=term-missing  # with coverage

# Diagnostics
uv run flowgate --config config/flowgate.yaml doctor
./scripts/smoke_local.sh config/flowgate.yaml
```

## Testing Strategy

- **Unit tests** (`@pytest.mark.unit`): Fast, no external deps, default in CI
- **Integration tests** (`@pytest.mark.integration`): Real subprocess/file I/O, in `tests/integration/`
- **Smoke tests**: `scripts/smoke_local.sh`
- Framework: pytest with unittest.TestCase
- Naming: `test_<behavior_description>`
- PRs must include tests for behavior changes

## Configuration Schema

Version: `config_version: 2` (v1 deprecated since v0.2.0, removed in v0.3.0)

Required keys: `config_version`, `paths` (runtime_dir, active_config, state_file, log_file), `services` (litellm, cliproxyapi_plus), `litellm_base` (model_list, router_settings, litellm_settings), `profiles` (at least one).

Optional: `credentials.upstream.<name>.file`, `auth.providers.<name>`, `secret_files`.

Legacy mappings (v1 → v2): `oauth` → `auth.providers`, `services.cliproxyapi` → `services.cliproxyapi_plus`, `secrets` → `secret_files`. See `docs/config-version-migration.md`.

## Code Style

- Python 3.12+, type hints for public functions
- 4-space indent, `snake_case` functions, `PascalCase` classes
- Explicit exceptions: `ConfigError`, `RuntimeError`, `ValueError`
- Paths relative to config file location, support absolute

## Commit and PR Guidelines

Conventional Commits: `type(scope): summary` (types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`; scopes: `bootstrap`, `cli`, `config`, `profile`, `auth`, `service`).

PRs: include test evidence, document config impact, one focused change per commit.

## Adding New Features

**Auth Provider**: Add config under `auth.providers.<provider>`, add handler in `auth_methods.py`, add tests, verify with `auth list`/`auth status`.

**Profile Strategy**: Add under `profiles.<name>`, define `litellm_settings` overrides, test activation and restart behavior.

## CI/CD

`.github/workflows/ci.yml`: push to main + all PRs → `uv sync` → `uv run pytest tests/ -v -m ""` → CLI help checks.

## Security

- Never commit credentials; secrets in `.router/secrets/` (gitignored)
- Run `./scripts/security_check.sh` before push

## Observability

Event log: `.router/runtime/events.log` (JSON lines). Events: `service_start/stop/restart`, `profile_switch`, `oauth_login`, `auth_import`.

## Troubleshooting

See `docs/runbook-troubleshooting.md`. Start with: `status` → `health` → `events.log` → `doctor`.
