# Phase 2.1 Migration Plan - Executive Summary

**Date**: 2026-02-19  
**Full Plan**: See `phase-2-1-migration-plan.md`

## Quick Facts

- **Objective**: Remove config_version: 1 support
- **Target Version**: v0.3.0 (Breaking Change)
- **Code Reduction**: ~100 lines (-10.9% in affected files)
- **Implementation Time**: 2 days
- **Migration Period**: 4-6 weeks

## Legacy Code Identified

| Component | File | Lines | Impact |
|-----------|------|-------|--------|
| Normalization | `config.py` | 50 | -27.2% |
| Validation | `validators.py` | 14 | -4.8% |
| Auth Helper | `auth.py` | 16 | -6.5% |
| Tests | `test_config.py` | 20 | -10.2% |
| **Total** | **4 files** | **100** | **-10.9%** |

## Field Mappings to Remove

1. **oauth → auth.providers** (Lines 100-110 in config.py)
2. **secrets → secret_files** (Lines 89-91 in config.py)
3. **cliproxyapi → cliproxyapi_plus** (Lines 93-98 in config.py)

## Two-Stage Strategy

### Stage 1: v0.2.0 (Deprecation)
- Add deprecation warnings
- Create `flowgate config migrate` command
- Full backward compatibility maintained
- Duration: 1 day

### Stage 2: v0.3.0 (Removal)
- Remove all legacy code (~100 lines)
- Reject v1 configs with clear error
- Update documentation
- Duration: 0.5 days

## Key Deliverables

### v0.2.0
- [ ] Deprecation warning system
- [ ] Migration command with dry-run
- [ ] Automatic backup creation
- [ ] Migration guide document

### v0.3.0
- [ ] Remove `_normalize_legacy_fields()`
- [ ] Remove `validate_oauth()`
- [ ] Simplify `_auth_providers()`
- [ ] Update all tests to v2 format
- [ ] Breaking change documentation

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Users miss warnings | Display on every command |
| Migration bugs | Dry-run mode + automatic backup |
| Breaking change impact | 4-6 week migration period |
| Documentation gaps | Comprehensive migration guide |

## Success Metrics

- ✅ Code reduction: -100 lines
- ✅ config.py: -27% complexity
- ✅ Migration success rate: 100%
- ✅ Zero data loss
- ✅ All tests pass (200+ tests)

## Timeline

```
2026-02-19: Analysis Complete ✅
2026-02-20: Implement deprecation (v0.2.0)
2026-02-21: Release v0.2.0
2026-03-15: Migration period ends
2026-03-16: Implement removal (v0.3.0)
2026-03-17: Release v0.3.0
```

## Next Steps

1. Review full migration plan
2. Approve implementation approach
3. Create feature branch
4. Begin Phase 2.1.1 (deprecation)

---

**Status**: ✅ Analysis Complete - Ready for Implementation  
**Approval**: [ ] Pending Review
