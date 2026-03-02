# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FlowGate is a local control tool for managing `CLIProxyAPIPlus`. It focuses on being an easy-to-configure wrapper around CLIProxyAPIPlus with unified CLI for bootstrap/service/auth/integration/health/doctor.

## Architecture

For detailed docs: [Architecture Overview](docs/architecture/README.md), [Diagrams](docs/architecture/diagrams.md), [Data Flows](docs/architecture/data-flows.md), [API Reference](docs/api/python-api.md).

### Key Components

- **CLI** (`src/flowgate/cli/`): BaseCommand pattern, @handle_command_errors decorator, argparse subcommands
- **Config** (`src/flowgate/core/config.py`): Schema v3 validation, PathResolver for path resolution
- **Process** (`src/flowgate/core/process.py`): ProcessSupervisor for service lifecycle, PID tracking in `.router/runtime/pids/`, port conflict detection
- **Auth** (`src/flowgate/core/auth.py`): OAuth polling, headless import, multi-provider (Codex, GitHub Copilot)
- **Bootstrap** (`src/flowgate/core/bootstrap.py`): Platform-specific binary downloads (CLIProxyAPIPlus), version checking
- **CLIProxyAPIPlus** (`src/flowgate/core/cliproxyapiplus.py`): Version management, update checking, auto-update
- **Health** (`src/flowgate/core/health.py`): Comprehensive health checks

### Key Data Flows

1. **Config Load**: load FlowGate config → parse CLIProxyAPIPlus config → derive `services.cliproxyapi_plus` (host/port/command) for reuse by commands
2. **Service Start**: `service start all` → validate ports → spawn process → record PID → log events
3. **OAuth Login**: `auth login codex` → fetch auth URL → poll status → write auth artifact → record event

## Directory Layout

- `src/flowgate/`: Main package (`__init__.py` entry, `core/`, `cli/`)
- `src/flowgate/core/`: Core business logic (`config.py`, `process.py`, `bootstrap.py`, `cliproxyapiplus.py`, `auth.py`, `health.py`, `security.py`, `observability.py`)
- `src/flowgate/cli/`: CLI commands (`run_cli`, `base.py`, `parser.py`, `auth.py`, `bootstrap.py`, `health.py`, `service.py`, etc.)
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

# Service
uv run flowgate --config config/flowgate.yaml service start all
uv run flowgate --config config/flowgate.yaml service stop all
uv run flowgate --config config/flowgate.yaml status
uv run flowgate --config config/flowgate.yaml health

# Auth
uv run flowgate --config config/flowgate.yaml auth login codex --timeout 180
uv run flowgate --config config/flowgate.yaml auth import-headless codex --source ~/.codex/auth.json

# Config migration (config_version 1 removed since v0.3.0)
# See docs/developer-guide/config-version-migration.md for manual steps

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

Version: `config_version: 3`

Required keys: `config_version`, `paths` (runtime_dir, log_file), `cliproxyapi_plus.config_file`.

Optional: `auth.providers.<name>`, `secret_files`, `integration`.

## Code Style

- Python 3.11+, type hints for public functions
- 4-space indent, `snake_case` functions, `PascalCase` classes
- Explicit exceptions: `ConfigError`, `RuntimeError`, `ValueError`
- Paths relative to config file location, support absolute

## Commit and PR Guidelines

Conventional Commits: `type(scope): summary` (types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`; scopes: `bootstrap`, `cli`, `config`, `profile`, `auth`, `service`).

PRs: include test evidence, document config impact, one focused change per commit.

## Adding New Features

**Auth Provider**: Add config under `auth.providers.<provider>`, add handler in `auth.py`, add tests, verify with `auth list`/`auth status`.

## CI/CD

`.github/workflows/ci.yml`: push to main + all PRs → `uv sync` → `uv run pytest tests/ -v -m ""` → CLI help checks.

## Security

- Never commit credentials; auth artifacts in `.router/auths/` (gitignored)
- Run `./scripts/security_check.sh` before push

## Observability

Event log: `.router/runtime/events.log` (JSON lines). Events: `service_start/stop/restart`, `profile_switch`, `oauth_login`, `auth_import`.

## Troubleshooting

See `docs/user-guide/troubleshooting.md`. Start with: `status` → `health` → `events.log` → `doctor`.
