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
uv sync --group runtime --group test
```

**Requirements**: Python 3.11+, `uv` package manager

### 2. Configure

```bash
mkdir -p config
cp config/examples/flowgate.yaml config/flowgate.yaml
cp config/examples/cliproxyapi.yaml config/cliproxyapi.yaml
```

Set credentials:

```bash
mkdir -p .router/secrets
printf '%s\n' "sk-..." > .router/secrets/upstream_cliproxyapi_api_key
chmod 600 .router/secrets/upstream_cliproxyapi_api_key
```

### 3. Bootstrap & Start

```bash
# Download runtime binaries
uv run flowgate --config config/flowgate.yaml bootstrap download

# Activate profile
uv run flowgate --config config/flowgate.yaml profile set balanced

# Start services
uv run flowgate --config config/flowgate.yaml service start all

# Check status
uv run flowgate --config config/flowgate.yaml health
```

## Documentation

📚 **[Complete Documentation](docs/README.md)**

### User Guides
- [Installation Guide](docs/user-guide/installation.md) - Detailed setup instructions
- [Configuration Reference](docs/user-guide/configuration.md) - Config schema and options
- [Profile Management](docs/user-guide/profiles.md) - Strategy profiles explained
- [Authentication Setup](docs/user-guide/authentication.md) - OAuth and credential management
- [CLI Reference](docs/user-guide/cli-reference.md) - All commands and options
- [Troubleshooting](docs/user-guide/troubleshooting.md) - Common issues and solutions

### Developer Resources
- [Developer Guide](docs/developer-guide/README.md) - Contributing and development setup
- [Architecture](docs/architecture/README.md) - System design and components
- [API Documentation](docs/api/README.md) - API reference

## Common Commands

```bash
# Service management
uv run flowgate --config config/flowgate.yaml service {start|stop|restart} {all|litellm|cliproxyapi_plus}

# Profile switching
uv run flowgate --config config/flowgate.yaml profile set {reliability|balanced|cost}

# OAuth authentication
uv run flowgate --config config/flowgate.yaml auth login {codex|copilot}

# Health checks
uv run flowgate --config config/flowgate.yaml {status|health|doctor}

# Client integration
uv run flowgate --config config/flowgate.yaml integration print {codex|claude-code}
```

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Unit tests only
uv run pytest tests/ -v -m unit

# Integration tests
uv run pytest tests/ -v -m integration

# With coverage
uv run pytest --cov=src/flowgate --cov-report=term-missing
```

**Test Stats**: 394 tests (351 unit, 43 integration) | 100% passing

## Project Structure

```
flowgate/
├── src/flowgate/          # Main package
│   ├── cli/               # CLI commands
│   ├── config_utils/      # Configuration utilities
│   └── *.py               # Core modules
├── tests/                 # Test suite
├── config/                # Configuration files
├── docs/                  # Documentation
├── scripts/               # Helper scripts
└── .router/               # Runtime artifacts (gitignored)
```

## Key Features

### Policy Profiles
- **reliability**: High retries, conservative fallbacks
- **balanced**: Default for daily usage
- **cost**: Cost-optimized with minimal retries

### OAuth Support
- Codex: Browser OAuth or headless import
- GitHub Copilot: OAuth login
- Extensible for new providers

### Observability
- JSON event logging (`.router/runtime/events.log`)
- Health checks (`liveness`, `readiness`)
- Performance metrics tracking

## Config Migration (Important!)

⚠️ **Config version 1 is deprecated as of v0.2.0 and will be removed in v0.3.0.**

Migrate now:

```bash
# Preview changes
uv run flowgate --config config/flowgate.yaml config migrate --dry-run

# Apply migration (creates backup)
uv run flowgate --config config/flowgate.yaml config migrate
```

See [Config Migration Guide](docs/user-guide/configuration.md#migration-from-v1-to-v2) for details.

## Contributing

We welcome contributions! See the [Developer Guide](docs/developer-guide/README.md) for:
- Development setup
- Coding standards
- Testing guidelines
- PR requirements

## Support

- **Issues**: Check [Troubleshooting Guide](docs/user-guide/troubleshooting.md)
- **Questions**: See [CLI Reference](docs/user-guide/cli-reference.md) or [Documentation](docs/README.md)
- **Bugs/Features**: [GitHub Issues](https://github.com/heliar-k/flowgate/issues)

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Latest Release**: [v0.2.0](docs/releases/v0.2.0.md) | **Changelog**: [CHANGELOG.md](CHANGELOG.md)
