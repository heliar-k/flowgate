# Deprecation Warning for config_version 1

## Summary
Implemented deprecation warning that displays when `config_version: 1` is detected during configuration loading. This is part of Phase 2.1 (v0.2.0) of the migration plan.

## Changes Made

### 1. Modified `src/flowgate/config.py`
- Added `sys` import for stderr output
- Enhanced `_normalize_legacy_fields()` to track detected legacy fields
- Added deprecation warning output to stderr when version 1 is detected
- Warning includes:
  - Clear deprecation message
  - Version removal timeline (v0.3.0)
  - Migration command suggestion
  - List of specific legacy fields detected

### 2. Added Tests in `tests/test_config.py`
Added 4 new test cases:
- `test_deprecation_warning_for_config_version_1`: Verifies warning appears for v1
- `test_deprecation_warning_includes_legacy_fields`: Verifies legacy fields are listed
- `test_no_deprecation_warning_for_config_version_2`: Verifies no warning for v2
- `test_no_deprecation_warning_when_version_defaults_to_2`: Verifies no warning when defaulting to v2

## Warning Output Example

When loading a config with `config_version: 1` and legacy fields:

```
⚠️  WARNING: config_version 1 is deprecated and will be removed in v0.3.0
Please migrate your configuration to version 2.
Run: flowgate config migrate --to-version 2

Legacy field mappings detected:
- 'secrets' → use 'secret_files' instead
- 'cliproxyapi' → use 'cliproxyapi_plus' instead
- 'oauth' → use 'auth.providers' instead
```

## Test Results
- All 191 tests pass (187 existing + 4 new)
- No breaking changes to existing functionality
- Warning appears on stderr, not stdout
- Warning only appears once per config load

## Backward Compatibility
- Config version 1 continues to work normally
- All legacy field mappings still function
- Warning is informational only, does not block operation

## Next Steps (Future Phases)
- v0.2.1: Implement `flowgate config migrate` command
- v0.3.0: Remove config_version 1 support entirely
