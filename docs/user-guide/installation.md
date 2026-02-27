# Installation Guide (v3, cliproxy-only)

This guide installs FlowGate and sets up a working local CLIProxyAPIPlus proxy managed by FlowGate.

## Requirements

- Python 3.11+
- `uv`
- macOS or Linux

## Install dependencies

```bash
export UV_CACHE_DIR=.uv-cache
uv sync --group test --group dev
```

## Create config files

```bash
mkdir -p config
cp config/examples/flowgate.yaml config/flowgate.yaml
cp config/examples/cliproxyapi.yaml config/cliproxyapi.yaml
```

Edit `config/cliproxyapi.yaml`:
- Set `api-keys` (clients must use one of these keys)
- Set `remote-management.secret-key` (required for OAuth management endpoints)

## Bootstrap runtime

```bash
uv run flowgate --config config/flowgate.yaml bootstrap download
```

## Start/stop the service

```bash
uv run flowgate --config config/flowgate.yaml service start all
uv run flowgate --config config/flowgate.yaml health
uv run flowgate --config config/flowgate.yaml service stop all
```

