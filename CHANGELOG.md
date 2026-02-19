# Changelog

All notable changes to FlowGate will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-02-19

**Major Release**: Code structure refactoring and configuration system simplification

This release focuses on improving code maintainability, reducing technical debt, and simplifying configuration management. Includes 36 regression tests, 150 new tests, and comprehensive documentation updates.

### Added

#### Phase 1: Code Structure Refactoring
- **CLI Modularization** (Phase 1.1):
  - Introduced `BaseCommand` class for unified command interface
  - Split `cli.py` (1020 lines) into specialized command modules:
    - `cli/commands/health.py` - Diagnostic commands
    - `cli/commands/auth.py` - Authentication commands
    - `cli/commands/profile.py` - Profile management
    - `cli/commands/service.py` - Service lifecycle
    - `cli/commands/bootstrap.py` - Runtime bootstrapping
    - `cli/commands/integration.py` - Client integrations
  - Reduced `cli.py` from 1020 to 292 lines (-71.4%)
  - Added 36 regression tests for CLI commands

- **Unified Error Handling** (Phase 1.2):
  - Created `cli/error_handler.py` with `@handle_command_errors` decorator
  - Standardized exit codes across all commands:
    - `0`: Success
    - `1`: Configuration error
    - `2`: Runtime error
    - `3`: Permission error
    - `99`: Internal error
  - Eliminated 64 lines of duplicate try-catch blocks
  - Added 18 error handling tests
  - Resolved TD-2 (noqa: BLE001) and TD-8 (inconsistent error messages)

- **Configuration Validation** (Phase 1.3):
  - Extracted validation logic to `validators.py` module
  - Created `ConfigValidator` class with 9 validation methods
  - Reduced config.py from 253 to 184 lines (-27.3%)
  - Added 55 comprehensive validator tests
  - Resolved TD-3 (config validation code duplication)

#### Phase 2: Configuration System Simplification
- **Config Version Migration** (Phase 2.1):
  - `flowgate config migrate` command for automatic migration
  - Deprecation warnings for config_version: 1
  - Automatic timestamped backup creation (`.backup-YYYYMMDD-HHMMSS`)
  - Dry-run mode (`--dry-run` flag) for safe preview
  - Post-migration validation with automatic rollback
  - Added 16 migration tests covering 5 real-world scenarios
  - Migration documentation in `docs/config-version-migration.md`
  - Implementation guide in `docs/config-migrate-implementation.md`

- **Path Resolution Simplification** (Phase 2.2):
  - Created `PathResolver` class in `config_utils/path_resolver.py`
  - Unified path resolution for 4 path types:
    - Top-level paths (`paths.*`)
    - Secret files (`secret_files`)
    - Credential files (`credentials.upstream.*.file`)
    - Service working directories (`services.*.command.cwd`)
  - Reduced `cli/utils.py` from 84 to 49 lines (-42%)
  - Eliminated 37 lines of duplicate path resolution code (-92%)
  - Added 21 path resolver tests
  - Technical documentation in `docs/path-resolution.md`

### Deprecated
- **config_version: 1** support (will be removed in v0.3.0)
- Legacy field names:
  - `oauth` → use `auth.providers`
  - `secrets` → use `secret_files`
  - `services.cliproxyapi` → use `services.cliproxyapi_plus`

### Changed
- CLI command structure modularized with `BaseCommand` hierarchy
- Error handling standardized across all commands
- Configuration validation centralized in `ConfigValidator` class
- Path resolution centralized in `PathResolver` class
- Config version 2 is now the recommended and documented format
- All example configs updated to use version 2
- Documentation comprehensively updated with Phase 1-2 changes
- Deprecation warnings displayed when loading version 1 configs

### Fixed
- Config validation now properly handles both version 1 and version 2 schemas
- Legacy field normalization improved for mixed old/new field scenarios
- Error messages now consistent across all commands with proper exit codes
- Path resolution behavior now fully consistent and well-tested

### Technical Metrics
- **Code Quality**:
  - cli.py: 1020 → 292 lines (-71.4%)
  - cli/utils.py: 84 → 49 lines (-42%)
  - config.py: 253 → 184 lines (-27.3%)
  - Eliminated ~138 lines of duplicate code
- **Test Coverage**:
  - Tests: 74 → 224 (+203%)
  - New regression tests: 36
  - New validator tests: 55
  - New migration tests: 16
  - New path resolver tests: 21
  - All tests passing: 224/224 (100%)
- **Documentation**:
  - New technical docs: ~2,900 lines
  - Updated guides and references
  - Complete phase completion reports

### Internal Changes
- Renamed `config/` directory to `config_utils/` to avoid Python naming conflicts
- Created `cli/commands/` directory structure for modular command organization
- Added `cli/error_handler.py` for centralized error handling
- Added `validators.py` for centralized config validation
- Added `config_utils/path_resolver.py` for unified path resolution

### Git History
This release includes 20+ commits across 6 phases:
- Phase 0: Preparation (tests, config migration, tech debt)
- Phase 1.1: CLI modularization
- Phase 1.2: Unified error handling
- Phase 1.3: Configuration validation extraction
- Phase 2.1: Config version migration system
- Phase 2.2: Path resolution simplification

Tags: `phase-0-complete`, `phase-1-1-1-complete`, `phase-1-1-2-complete`, `phase-1-2-complete`, `phase-1-3-complete`, `phase-2-1-complete`, `phase-2-2-complete`

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
