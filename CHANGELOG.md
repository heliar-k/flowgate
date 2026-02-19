# Changelog

All notable changes to FlowGate will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-02-19

### Added
- `flowgate config migrate` command for automatic config version migration
- Deprecation warnings for config_version: 1
- Automatic backup creation during config migration
- Dry-run mode for config migration (`--dry-run` flag)
- Comprehensive migration test suite with 5 real-world scenarios
- Migration documentation in `docs/config-version-migration.md`

### Deprecated
- config_version: 1 support (will be removed in v0.3.0)
- Legacy field names:
  - `oauth` (use `auth.providers` instead)
  - `secrets` (use `secret_files` instead)
  - `services.cliproxyapi` (use `services.cliproxyapi_plus` instead)

### Changed
- Config version 2 is now the recommended format
- All example configs updated to use version 2
- Documentation updated with migration instructions
- Deprecation warnings displayed when loading version 1 configs

### Fixed
- Config validation now properly handles both version 1 and version 2 schemas
- Legacy field normalization improved for mixed old/new field scenarios

## [0.1.0] - 2026-02-18

### Added
- Initial release of FlowGate
- LiteLLM and CLIProxyAPIPlus service management
- Profile-based policy switching (reliability, balanced, cost)
- OAuth authentication for Codex and GitHub Copilot
- Headless auth import for device-auth flows
- Bootstrap command for runtime binary downloads
- Health checks and status monitoring
- Integration snippets for Codex and Claude Code
- Comprehensive test suite (203 tests)
- Event logging to `.router/runtime/events.log`
- Security checks for credentials and permissions
- Doctor command for preflight validation
- Smoke test scripts for runtime validation

### Documentation
- README.md with quick start guide
- CLAUDE.md with development guidelines
- Architecture documentation (C4 diagrams)
- Troubleshooting runbook
- Integration guides for Claude Code and Codex
- Release and rollback procedures

## Migration Guide

### Upgrading from v0.1.0 to v0.2.0

If you have an existing FlowGate installation with version 1 config:

1. **Check your config version**:
   ```bash
   uv run flowgate --config config/flowgate.yaml status
   ```

   If you see a deprecation warning, proceed with migration.

2. **Preview migration changes**:
   ```bash
   uv run flowgate --config config/flowgate.yaml config migrate --dry-run
   ```

3. **Apply migration**:
   ```bash
   uv run flowgate --config config/flowgate.yaml config migrate
   ```

4. **Verify migration**:
   ```bash
   uv run flowgate --config config/flowgate.yaml status
   ```

See `docs/config-version-migration.md` for detailed migration instructions.

## Breaking Changes

### Planned for v0.3.0
- Config version 1 support will be completely removed
- Legacy field names will no longer be recognized
- Configs without explicit `config_version: 2` will fail to load

**Action Required**: Migrate to config version 2 before upgrading to v0.3.0.

## Support

For issues, questions, or contributions:
- Check `docs/runbook-troubleshooting.md` for common issues
- Review `docs/config-version-migration.md` for migration help
- Run `flowgate doctor` for configuration validation
- Check event logs: `tail -n 50 .router/runtime/events.log`

[Unreleased]: https://github.com/yourusername/flowgate/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/yourusername/flowgate/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/yourusername/flowgate/releases/tag/v0.1.0
