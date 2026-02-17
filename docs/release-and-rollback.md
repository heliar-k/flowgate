# Release and Rollback Guide

This guide standardizes local release and emergency rollback for `flowgate`.

## Release Flow

### 1) Pre-release checks

```bash
uv sync --group runtime --group test
uv run python -m unittest discover -s tests -v
uv run flowgate --config config/flowgate.yaml doctor
```

Required before release:
- Working tree is clean (`git status`)
- Tests are green
- Runtime preflight (`doctor`) is green

### 2) Version and changelog

1. Bump `project.version` in `pyproject.toml`.
2. Summarize notable changes (feature/fix/breaking/migration) in release notes.
3. Verify docs impacted by behavior changes are updated.

### 3) Tag and publish

```bash
git add pyproject.toml README.md docs/
git commit -m "chore(release): prepare vX.Y.Z" -m "Why this change was needed:\n...\n\nWhat changed:\n...\n\nProblem solved:\n..."
git tag -a vX.Y.Z -m "flowgate vX.Y.Z"
git push origin main --follow-tags
```

## Rollback Flow

Use rollback when a new release causes broken auth/service/bootstrap flows.

### 1) Select last known good version

```bash
git tag --sort=-creatordate | head -n 10
git checkout v<last-good>
```

### 2) Restore runtime/config state

- Restore known-good `config/flowgate.yaml` and `config/cliproxyapi.yaml`.
- Re-bootstrap runtime binaries from the known-good revision:

```bash
uv run flowgate --config config/flowgate.yaml bootstrap download
uv run flowgate --config config/flowgate.yaml profile set balanced
uv run flowgate --config config/flowgate.yaml service restart all
```

### 3) Verify recovery

```bash
uv run flowgate --config config/flowgate.yaml status
uv run flowgate --config config/flowgate.yaml health
```

Expected:
- services report running
- `health` returns `liveness=ok` and `readiness=ok`

## Release Checklist

- [ ] Tests pass (`unittest discover`)
- [ ] `doctor` passes
- [ ] Version updated in `pyproject.toml`
- [ ] Migration/compatibility notes documented
- [ ] Tag created and pushed

## Rollback Checklist

- [ ] Last known good tag selected
- [ ] Config restored to known-good revision
- [ ] Runtime binaries regenerated from known-good code
- [ ] `status` and `health` green after restart
