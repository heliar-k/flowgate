# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FlowGate is a local control tool for managing `CLIProxyAPIPlus + LiteLLM` stacks. It provides unified management of LiteLLM (northbound OpenAI-compatible endpoint) and CLIProxyAPIPlus (OAuth-backed providers like Codex, GitHub Copilot) with policy profile switching and service lifecycle management.

## Architecture

### Core Components

**CLI Layer** (`src/flowgate/cli.py`):
- Entry point for all commands: profile, auth, service, health, bootstrap, integration
- Parses config, resolves paths, and delegates to specialized modules
- Uses argparse with subcommands pattern

**Configuration** (`src/flowgate/config.py`):
- Supports config schema version 2 (explicit or defaulted)
- JSON/YAML parsing with backward compatibility for legacy keys
- Path resolution via PathResolver class (`config_utils/path_resolver.py`)
- Validates required top-level keys and service definitions

**Path Resolution** (`src/flowgate/config_utils/path_resolver.py`):
- Unified path resolution for all configuration paths
- Supports absolute paths (unchanged) and relative paths (relative to config dir)
- Handles 4 path types: paths.*, secret_files, credentials.upstream.*.file, services.*.command.cwd
- Deep-copy configuration to avoid mutations

**Bootstrap** (`src/flowgate/bootstrap.py`):
- Downloads platform-specific CLIProxyAPIPlus binary from GitHub releases
- Generates LiteLLM runner script that wraps `uv run litellm`
- Platform detection for darwin/linux and amd64/arm64

**Profile Management** (`src/flowgate/profile.py`):
- Merges `litellm_base` with profile-specific overlays
- Resolves `api_key_ref` from credential files
- Atomically writes active config and state files
- Automatic LiteLLM restart when switching profiles while service is running

**Process Supervision** (`src/flowgate/process.py`):
- `ProcessSupervisor` manages service lifecycle (start/stop/restart)
- PID-based process tracking under `.router/runtime/pids/`
- JSON event logging to `.router/runtime/events.log`

**Authentication** (`src/flowgate/oauth.py`, `auth_methods.py`):
- OAuth polling flow for Codex and GitHub Copilot
- Headless import for device-auth flows (imports from `~/.codex/auth.json`)
- Extensible handler registry in `auth_methods.py`

**Integration** (`src/flowgate/integration.py`, `client_apply.py`):
- Generate client config snippets (Codex, Claude Code)
- Apply settings to client config files with backup

### Key Data Flows

1. **Profile Activation**: User runs `profile set <name>` → `profile.py` merges base + overlay → resolves credential refs → writes active config + state → auto-restarts LiteLLM if running
2. **Service Start**: User runs `service start all` → CLI validates port availability → `ProcessSupervisor.start()` spawns processes → records PIDs → logs events
3. **OAuth Login**: User runs `auth login codex` → fetches auth URL → polls status endpoint → writes auth artifact → records event

## Directory Layout

- `src/flowgate/`: Main package code
  - `config.py`: Configuration loading and validation
  - `config_utils/`: Configuration utilities
    - `path_resolver.py`: Unified path resolution
  - `cli/`: Command-line interface
  - `validators.py`: Configuration validators
- `tests/`: unittest suite (unit + integration tests)
- `config/examples/`: Sample configs (copy to `config/flowgate.yaml` and `config/cliproxyapi.yaml`)
- `.router/`: Runtime artifacts (PIDs, logs, binaries, auth files) - intentionally gitignored
- `scripts/`: Helper scripts (`xgate`, `xtest`, `smoke_local.sh`, `doctor.sh`, `debug_cliproxyapi.sh`)

## Common Development Commands

### Setup and Installation
```bash
export UV_CACHE_DIR=.uv-cache
uv sync --group runtime --group test
```

### Running the CLI
```bash
# With venv
uv run flowgate --config config/flowgate.yaml <command>

# Without venv activation (uvx wrapper)
./scripts/xgate --config config/flowgate.yaml <command>
```

### Bootstrap Runtime
```bash
uv run flowgate --config config/flowgate.yaml bootstrap download
# Custom version:
uv run flowgate --config config/flowgate.yaml bootstrap download --cliproxy-version v6.8.18-1
```

### Configuration Management
```bash
# Migrate config from version 1 to version 2
uv run flowgate --config config/flowgate.yaml config migrate

# Preview migration changes without applying
uv run flowgate --config config/flowgate.yaml config migrate --dry-run
```

### Profile Management
```bash
uv run flowgate --config config/flowgate.yaml profile list
uv run flowgate --config config/flowgate.yaml profile set balanced
```

### Service Control
```bash
uv run flowgate --config config/flowgate.yaml service start all
uv run flowgate --config config/flowgate.yaml service stop all
uv run flowgate --config config/flowgate.yaml status
uv run flowgate --config config/flowgate.yaml health
```

### Config Migration
```bash
# Check if migration is needed (loads config and shows warnings)
uv run flowgate --config config/flowgate.yaml status

# Preview migration changes without applying
uv run flowgate --config config/flowgate.yaml config migrate --dry-run

# Perform migration (creates automatic backup)
uv run flowgate --config config/flowgate.yaml config migrate
```

### OAuth and Authentication
```bash
uv run flowgate --config config/flowgate.yaml auth list
uv run flowgate --config config/flowgate.yaml auth status
uv run flowgate --config config/flowgate.yaml auth login codex --timeout 180
uv run flowgate --config config/flowgate.yaml auth import-headless codex --source ~/.codex/auth.json
```

### Testing
```bash
# Run all tests
uv run python -m unittest discover -s tests -v

# Without venv activation
./scripts/xtest

# Run single test file
uv run python -m unittest tests.test_config

# Run single test case
uv run python -m unittest tests.test_config.TestConfigValidation.test_missing_required_keys

# With coverage
uv run pytest --cov=src/flowgate --cov-report=term-missing
```

### Health Checks and Diagnostics
```bash
# Preflight checks
uv run flowgate --config config/flowgate.yaml doctor
./scripts/doctor.sh config/flowgate.yaml

# Smoke tests
./scripts/smoke_local.sh config/flowgate.yaml
PROFILE=reliability ./scripts/smoke_local.sh config/flowgate.yaml

# Debug CLIProxyAPI standalone
./scripts/debug_cliproxyapi.sh start
./scripts/debug_cliproxyapi.sh stop
```

## Testing Strategy

- **Unit tests**: Core modules (`test_config.py`, `test_process.py`, `test_security.py`)
- **Integration tests**: Cross-module workflows (`test_cli.py`, `test_integration_profile_switch.py`)
- **Smoke tests**: Real runtime validation (`scripts/smoke_local.sh`)
- Test naming convention: `test_<behavior_description>`
- Tests use `unittest` framework exclusively
- Add/update tests before changing behavior
- PRs must include tests for affected functionality

## Configuration Schema

Current version: `config_version: 2` (recommended)

**IMPORTANT**: Config version 1 is deprecated as of v0.2.0 and will be removed in v0.3.0.
Use `flowgate config migrate` to upgrade your configuration.

Required top-level keys:
- `config_version`: Should be set to `2` explicitly
- `paths`: runtime_dir, active_config, state_file, log_file
- `services`: litellm, cliproxyapi_plus (each with command.args, host, port)
- `litellm_base`: model_list, router_settings, litellm_settings
- `profiles`: at least one profile (reliability, balanced, cost)

Optional:
- `credentials.upstream.<name>.file`: Path to API key credential files
- `auth.providers.<name>`: OAuth configuration (replaces legacy `oauth`)
- `secret_files`: Additional sensitive file paths for permission checks

### Config Version Migration

Version 1 configs are deprecated and will stop working in v0.3.0. Migrate using:

```bash
# Preview migration changes
flowgate --config config/flowgate.yaml config migrate --dry-run

# Perform migration (creates backup automatically)
flowgate --config config/flowgate.yaml config migrate
```

Legacy field mappings (v1 → v2):
- `oauth` → `auth.providers` (auto-normalized in v0.2.x)
- `services.cliproxyapi` → `services.cliproxyapi_plus`
- `secrets` → `secret_files`

See `docs/config-version-migration.md` for detailed migration guide.

## Code Style

- Python 3.12+ with type hints for public functions
- 4-space indentation, `snake_case` for modules/functions, `PascalCase` for classes
- Use explicit exceptions: `ConfigError`, `RuntimeError`, `ValueError`
- Keep functions small and focused
- Paths: relative to config file location by default, support absolute paths

## Commit and PR Guidelines

**Commit format** (Conventional Commits):
```
type(scope): summary

Why this change was needed:
...

What changed:
...

Problem solved:
...
```

Example types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
Example scopes: `bootstrap`, `cli`, `config`, `profile`, `auth`, `service`

**PR requirements**:
- Include test evidence (command + result)
- Document config/migration impact if applicable
- One focused change per commit
- Tests must be included for behavior changes

## Adding New Features

### Adding an Auth Provider
1. Add provider config under `auth.providers.<provider>` in config with `auth_url_endpoint`, `status_endpoint`
2. For headless import, add handler to `headless_import_handlers()` in `auth_methods.py`
3. Add CLI and config tests in `tests/test_cli.py` and `tests/test_config.py`
4. Verify with `auth list` and `auth status`

### Adding a Profile Strategy
1. Add profile name under `profiles.<name>` in config
2. Define `litellm_settings` overrides (retries, cooldown, fallbacks)
3. Test profile activation and LiteLLM restart behavior
4. Update docs with use case description

## CI/CD

Workflow: `.github/workflows/ci.yml`
- Runs on: push to main, all PRs
- Steps: `uv sync`, `unittest discover`, CLI help checks
- Intentionally excludes: OAuth network flows, service startup

## Security

- Never commit credentials or auth artifacts
- Secrets stored in `.router/secrets/` (gitignored)
- Environment variables for non-file credentials (e.g., `CUSTOM_API_KEY`)
- Run `./scripts/security_check.sh` before push to verify permissions and gitignore

## Observability

Event logging: `.router/runtime/events.log` (JSON lines)
- Fields: `event`, `service`, `profile`, `provider`, `result`, `detail`, `timestamp`
- Events: `service_start`, `service_stop`, `service_restart`, `profile_switch`, `oauth_login`, `auth_import`

Quick inspection:
```bash
tail -n 50 .router/runtime/events.log
```

## Troubleshooting

See `docs/runbook-troubleshooting.md` for common issues.

Start with:
1. `uv run flowgate --config config/flowgate.yaml status`
2. `uv run flowgate --config config/flowgate.yaml health`
3. `tail -n 50 .router/runtime/events.log`
4. `uv run flowgate --config config/flowgate.yaml doctor`
