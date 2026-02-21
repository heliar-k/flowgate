# FlowGate

[![CI Status](https://github.com/heliar-k/flowgate/actions/workflows/ci.yml/badge.svg)](https://github.com/heliar-k/flowgate/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A local control tool for managing **CLIProxyAPIPlus + LiteLLM** stacks with policy profile switching and unified CLI.

## What It Does

- **Unified Gateway**: LiteLLM as northbound OpenAI-compatible endpoint
- **OAuth Integration**: CLIProxyAPIPlus for Codex, GitHub Copilot providers
- **Policy Profiles**: Switch between `reliability`, `balanced`, `cost` strategies
- **Lifecycle Management**: Health checks, service control, and observability

## Quick Start

### 1. Install

```bash
export UV_CACHE_DIR=.uv-cache
uv sync --group test --group dev
```

**Requirements**: Python 3.11+, [uv package manager](https://docs.astral.sh/uv/)

### 2. Configure

```bash
mkdir -p config .router/secrets
cp config/examples/flowgate.yaml config/flowgate.yaml
printf '%s\n' "sk-..." > .router/secrets/upstream_cliproxyapi_api_key
chmod 600 .router/secrets/upstream_cliproxyapi_api_key
```

### 3. Bootstrap & Start

```bash
# Download runtime binaries
uv run flowgate --config config/flowgate.yaml bootstrap download

# Check for updates (recommended)
uv run flowgate --config config/flowgate.yaml bootstrap update

# Activate profile and start services
uv run flowgate --config config/flowgate.yaml profile set balanced
uv run flowgate --config config/flowgate.yaml service start all
uv run flowgate --config config/flowgate.yaml health
```

**See**: [Quick Start Guide](docs/user-guide/quick-start.md) for detailed 5-minute setup.

## Documentation

📚 **[Complete Documentation](docs/README.md)**

### User Guides
- [Installation Guide](docs/user-guide/installation.md) - Detailed setup instructions
- [Quick Start Guide](docs/user-guide/quick-start.md) - 5-minute getting started
- [Configuration Reference](docs/user-guide/configuration.md) - Config schema and options
- [Authentication Setup](docs/user-guide/authentication.md) - OAuth and credentials
- [Troubleshooting](docs/user-guide/troubleshooting.md) - Common issues

### Developer Resources
- [Developer Guide](docs/developer-guide/README.md) - Contributing and development
- [Architecture Overview](docs/architecture/README.md) - System design
- [API Documentation](docs/api/README.md) - API reference

## Key Features

**Policy Profiles**: Switch between `reliability` (max retries), `balanced` (default), and `cost` (optimized) strategies with automatic service restart.

**OAuth Support**: Browser-based OAuth for Codex and GitHub Copilot, plus headless import for CI/CD environments.

**Observability**: JSON event logging, health checks (liveness/readiness), and performance metrics tracking.

## Common Commands

```bash
# Service management
flowgate service {start|stop|restart} {all|litellm|cliproxyapi_plus}

# Profile switching
flowgate profile set {reliability|balanced|cost}

# Health & diagnostics
flowgate {status|health|doctor}
```

**Note**: Prefix commands with `uv run` or use `./scripts/xgate` wrapper.

**See**: [CLI Reference](docs/user-guide/cli-reference.md) for all commands.

## Testing

```bash
# Unit tests (default)
uv run pytest tests/ -v

# All tests (unit + integration)
uv run pytest tests/ -v -m ""
```

**Test Stats**: 417 tests (417 unit, 43 integration) | 100% passing

## Config Migration

⚠️ **Config version 1 is deprecated** (v0.2.0) and will be removed in v0.3.0.

```bash
# Check if migration needed
uv run flowgate --config config/flowgate.yaml status

# Migrate (creates backup)
uv run flowgate --config config/flowgate.yaml config migrate
```

**See**: [Configuration Guide](docs/user-guide/configuration.md#version-migration) for details.

## Contributing

We welcome contributions! See [Developer Guide](docs/developer-guide/README.md) for:
- Development setup and testing
- Coding standards and PR requirements
- Architecture and design decisions

## Support

- **Documentation**: [Complete Docs](docs/README.md)
- **Troubleshooting**: [Common Issues](docs/user-guide/troubleshooting.md)
- **Bugs/Features**: [GitHub Issues](https://github.com/heliar-k/flowgate/issues)

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Latest Release**: [v0.4.4](CHANGELOG.md#044---2026-02-21) | **Changelog**: [CHANGELOG.md](CHANGELOG.md)
