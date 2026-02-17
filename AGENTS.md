# Repository Guidelines

## Project Structure & Module Organization
- `src/flowgate/`: main Python package and CLI entrypoint (`flowgate:main`).
- `src/flowgate/cli.py`: command routing for profile, auth, service, health, and bootstrap workflows.
- `src/flowgate/bootstrap.py`: runtime artifact setup (`CLIProxyAPIPlus` download + LiteLLM runner generation).
- `tests/`: `unittest`-based test suite (`test_*.py`), including integration-style profile switching coverage.
- `config/examples/`: tracked sample configs. Copy these to `config/flowgate.yaml` and `config/cliproxyapi.yaml` for local runs.
- Runtime output is intentionally untracked under `.router/` (pids, logs, generated binaries, auth artifacts).

## Build, Test, and Development Commands
- Install deps: `export UV_CACHE_DIR=.uv-cache && uv sync --group runtime --group test`
- Run CLI help: `uv run flowgate --help`
- Run CLI help (uvx, no venv activation): `./scripts/xgate --help`
- Bootstrap runtime binaries: `uv run flowgate --config config/flowgate.yaml bootstrap download`
- Activate profile: `uv run flowgate --config config/flowgate.yaml profile set balanced`
- Start/stop services: `uv run flowgate --config config/flowgate.yaml service start all` / `service stop all`
- Run tests: `uv run python -m unittest discover -s tests -v`
- Run tests (uvx, no venv activation): `./scripts/xtest`

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
- Use Conventional Commit subject line: `type(scope): summary` (for example, `fix(bootstrap): ...`, `refactor(cli): ...`).
- Commit message body should follow the `@git-commit` style used in this repo:
  - `Why this change was needed:`
  - `What changed:`
  - `Problem solved:`
- Example:
  - `feat(cli): add profile switch restart behavior`
  - `Why this change was needed:`
  - `...`
  - `What changed:`
  - `...`
  - `Problem solved:`
  - `...`
- Keep each commit focused to one feature/fix and include related tests in the same commit.
- PRs should include change intent, test evidence (exact command + result), and migration/config impact.

## Security & Configuration Tips
- Never commit real credentials or local auth artifacts.
- Keep local secrets in environment variables (`ROUTER_UPSTREAM_API_KEY`, `CUSTOM_API_KEY`) and ignored config files.
- Validate file permissions for sensitive auth files when troubleshooting status output.
