# Repository Guidelines

## Project Structure & Module Organization
- `src/llm_router/`: main Python package and CLI entrypoint (`llm_router:main`).
- `src/llm_router/cli.py`: command routing for profile, auth, service, health, and bootstrap workflows.
- `src/llm_router/bootstrap.py`: runtime artifact setup (`CLIProxyAPIPlus` download + LiteLLM runner generation).
- `tests/`: `unittest`-based test suite (`test_*.py`), including integration-style profile switching coverage.
- `config/examples/`: tracked sample configs. Copy these to `config/routertool.yaml` and `config/cliproxyapi.yaml` for local runs.
- Runtime output is intentionally untracked under `.router/` (pids, logs, generated binaries, auth artifacts).

## Build, Test, and Development Commands
- Install deps: `export UV_CACHE_DIR=.uv-cache && uv sync --group runtime --group test`
- Run CLI help: `uv run llm-router --help`
- Bootstrap runtime binaries: `uv run llm-router --config config/routertool.yaml bootstrap download`
- Activate profile: `uv run llm-router --config config/routertool.yaml profile set balanced`
- Start/stop services: `uv run llm-router --config config/routertool.yaml service start all` / `service stop all`
- Run tests: `uv run python -m unittest discover -s tests -v`

## Coding Style & Naming Conventions
- Python 3.12+ (`requires-python >=3.12,<3.14`), 4-space indentation, type hints for public functions.
- Module names use `snake_case`; classes use `PascalCase`; constants use `UPPER_SNAKE_CASE`.
- Prefer small, focused functions with explicit error messages (`ConfigError`, `RuntimeError`, `ValueError`).
- Keep config paths explicit and relative to config location unless absolute paths are required.

## Testing Guidelines
- Framework: standard library `unittest`.
- Test files follow `tests/test_*.py`; test names should describe behavior (for example, `test_bootstrap_download_rejects_litellm_version_flag`).
- For behavior changes, add/adjust tests first, then run the full suite before committing.

## Commit & Pull Request Guidelines
- Follow Conventional Commit style seen in history: `type(scope): summary` (for example, `fix(bootstrap): ...`, `refactor(cli): ...`).
- Keep commits focused to one feature/fix and include related tests in the same commit.
- PRs should include:
  - what changed and why,
  - test evidence (exact command + result),
  - config or migration notes when behavior/path defaults change.

## Security & Configuration Tips
- Never commit real credentials or local auth artifacts.
- Keep local secrets in environment variables (`ROUTER_UPSTREAM_API_KEY`, `CUSTOM_API_KEY`) and ignored config files.
- Validate file permissions for sensitive auth files when troubleshooting status output.
