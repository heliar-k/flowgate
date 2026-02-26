# Configuration Version Migration

FlowGate supports `config_version: 2`.

## When you see a migration warning

If you have an older configuration that still uses legacy keys (historical examples: `oauth`, `secrets`, `services.cliproxyapi`), update it to the v2 schema:

- `oauth` → `auth.providers`
- `secrets` → `secret_files`
- `services.cliproxyapi` → `services.cliproxyapi_plus`

## Verify after changes

```bash
flowgate --config config/flowgate.yaml doctor
flowgate --config config/flowgate.yaml status
flowgate --config config/flowgate.yaml health --verbose
```

For the current schema reference, see `docs/user-guide/configuration.md`.

