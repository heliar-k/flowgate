# LLM Router Tool

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
UV_CACHE_DIR=.uv-cache uv sync
```

## Quick start

1. Copy sample config:

```bash
mkdir -p config
cp config/examples/routertool.yaml config/routertool.yaml
```

2. Set runtime secrets:

```bash
export ROUTER_UPSTREAM_API_KEY="sk-..."
export CUSTOM_API_KEY="sk-..."
```

3. Bootstrap runtime binaries (auto download):

```bash
UV_CACHE_DIR=.uv-cache uv run llm-router --config config/routertool.yaml bootstrap download
```

4. Generate active profile config:

```bash
UV_CACHE_DIR=.uv-cache uv run llm-router --config config/routertool.yaml profile set balanced
```

5. Start services:

```bash
UV_CACHE_DIR=.uv-cache uv run llm-router --config config/routertool.yaml service start all
```

6. Check status and health:

```bash
UV_CACHE_DIR=.uv-cache uv run llm-router --config config/routertool.yaml status
UV_CACHE_DIR=.uv-cache uv run llm-router --config config/routertool.yaml health
```

## Runtime bootstrap

`bootstrap download` will:

- Download a platform-matched `CLIProxyAPIPlus` release binary into `runtime/bin/CLIProxyAPIPlus`
- Generate a pinned `litellm` runner script at `runtime/bin/litellm` (using `uvx --from litellm==<version>`)

Custom versions:

```bash
UV_CACHE_DIR=.uv-cache uv run llm-router --config config/routertool.yaml \
  bootstrap download \
  --cliproxy-version v6.8.16-0 \
  --litellm-version 1.75.8
```

## OAuth login

### Codex OAuth

```bash
UV_CACHE_DIR=.uv-cache uv run llm-router --config config/routertool.yaml auth codex login --timeout 180 --poll-interval 2
```

### GitHub Copilot OAuth

```bash
UV_CACHE_DIR=.uv-cache uv run llm-router --config config/routertool.yaml auth copilot login --timeout 180 --poll-interval 2
```

## Strategy profiles

- `reliability`: higher retries + longer cooldown + conservative fallback
- `balanced`: default for day-to-day usage
- `cost`: lower retries + cost-first fallback chain

Switch with:

```bash
UV_CACHE_DIR=.uv-cache uv run llm-router --config config/routertool.yaml profile set reliability
```

## Run tests

```bash
UV_CACHE_DIR=.uv-cache PYTHONPATH=src uv run python -m unittest discover -s tests -v
```

## Notes

- Config parser accepts YAML via PyYAML when installed, and always accepts JSON (JSON is valid YAML subset).
- In this repo example, sample config is stored in JSON-compatible YAML to avoid hard dependency for parsing during bootstrap.
