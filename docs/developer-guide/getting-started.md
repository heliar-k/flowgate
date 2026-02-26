# Getting Started (Developer)

## Setup

```bash
export UV_CACHE_DIR=.uv-cache
uv sync --group test --group dev
```

## Run the CLI

```bash
uv run flowgate --config config/flowgate.yaml status
```

## Run tests

```bash
uv run pytest tests/ -v
```

For release workflows, see `docs/developer-guide/release-process.md`.

