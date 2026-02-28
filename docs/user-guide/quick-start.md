# Quick Start Guide (v3, cliproxy-only)

FlowGate (config_version 3) manages a single local service: **CLIProxyAPIPlus**. Configure CLIProxyAPIPlus in `config/cliproxyapi.yaml`, and let FlowGate handle bootstrap/service/auth/integration/health/doctor.

## Prerequisites

- Python 3.11+
- `uv` ([install guide](https://docs.astral.sh/uv/getting-started/installation))
- macOS or Linux

## 1) Install

```bash
export UV_CACHE_DIR=.uv-cache
uv sync --group test --group dev
```

## 2) Configure

```bash
mkdir -p config
cp config/examples/flowgate.yaml config/flowgate.yaml
cp config/examples/cliproxyapi.yaml config/cliproxyapi.yaml
```

Edit `config/cliproxyapi.yaml`:
- Set `api-keys` (clients must use one of these keys)
- Set `remote-management.secret-key` (required for `/v0/management/...` OAuth endpoints)

## 3) Bootstrap + Doctor

```bash
uv run flowgate --config config/flowgate.yaml bootstrap download
uv run flowgate --config config/flowgate.yaml doctor
```

## 4) Start + Probe

```bash
uv run flowgate --config config/flowgate.yaml service start all
curl --silent --show-error -H "Authorization: Bearer sk-local-test" http://127.0.0.1:8317/v1/models
uv run flowgate --config config/flowgate.yaml service stop all
```

## Next

- OAuth login: `uv run flowgate --config config/flowgate.yaml auth login codex`
- Client snippets: `uv run flowgate --config config/flowgate.yaml integration print codex`
