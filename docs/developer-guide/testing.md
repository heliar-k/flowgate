# Testing

FlowGate uses pytest.

## Common commands

```bash
uv run pytest tests/ -v
uv run pytest tests/ -v -m integration
uv run pytest tests/ -v -m ""
```

## Notes

- Unit tests are the default selection (`-m 'not integration'` in `pyproject.toml`).
- Integration tests exercise real subprocess/file IO under `tests/integration/`.

