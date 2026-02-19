# Configuration Guide

Complete reference for FlowGate configuration, including schema documentation, migration guides, and best practices.

---

## Table of Contents

- [Configuration Schema](#configuration-schema)
- [Version Migration](#version-migration)
- [Configuration Reference](#configuration-reference)
- [Path Resolution](#path-resolution)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Configuration Schema

### Current Version: 2

FlowGate uses versioned configuration schemas. **Version 2 is the current standard.**

```yaml
config_version: 2  # Always specify explicitly
```

**Important**: Config version 1 is deprecated as of v0.2.0 and will be removed in v0.3.0.

### Required Top-Level Keys

| Key | Type | Description |
|-----|------|-------------|
| `config_version` | integer | Schema version (use `2`) |
| `paths` | object | Runtime directory paths |
| `services` | object | Service definitions (litellm, cliproxyapi_plus) |
| `litellm_base` | object | LiteLLM base configuration |
| `profiles` | object | Policy profiles (reliability, balanced, cost) |

### Optional Top-Level Keys

| Key | Type | Description |
|-----|------|-------------|
| `auth` | object | Authentication provider configuration |
| `credentials` | object | Upstream API credentials |
| `secret_files` | array | Additional sensitive file paths |

---

## Version Migration

### Deprecation Timeline

| Version | Status | Action Required |
|---------|--------|-----------------|
| **v0.2.0** | ✅ Current | Version 1 works with warnings, migration tool available |
| **v0.3.0** | ⚠️ Breaking | Version 1 will stop working |

### Quick Migration

**Check if you need to migrate:**

```bash
flowgate --config config/flowgate.yaml status

# If you see this warning, migrate immediately:
⚠️  WARNING: config_version 1 is deprecated and will be removed in v0.3.0
```

**Automated Migration (Recommended):**

```bash
# Preview changes without applying
flowgate --config config/flowgate.yaml config migrate --dry-run

# Perform migration (creates automatic backup)
flowgate --config config/flowgate.yaml config migrate
```

### Migration Command Features

The `flowgate config migrate` command provides:

- ✅ **Automatic Backup**: Creates `.backup-TIMESTAMP` before changes
- ✅ **Dry-Run Mode**: Preview changes with `--dry-run`
- ✅ **Validation**: Validates migrated config before finalizing
- ✅ **Idempotent**: Safe to run multiple times
- ✅ **Rollback**: Automatic backup for easy restoration

### What Changed (v1 → v2)

| Version 1 Field | Version 2 Field | Migration |
|----------------|-----------------|-----------|
| `oauth` | `auth.providers` | OAuth config moved under auth section |
| `secrets` | `secret_files` | Clearer naming for secret file paths |
| `services.cliproxyapi` | `services.cliproxyapi_plus` | Service name updated |

### Migration Example

**Before (Version 1):**
```yaml
config_version: 1
oauth:
  codex:
    auth_url_endpoint: "http://127.0.0.1:9000/auth-url"
    status_endpoint: "http://127.0.0.1:9000/status"
secrets:
  - "auth/codex.json"
services:
  cliproxyapi:
    host: "127.0.0.1"
    port: 9000
    command:
      args: [".router/runtime/bin/CLIProxyAPIPlus"]
```

**After (Version 2):**
```yaml
config_version: 2
auth:
  providers:
    codex:
      auth_url_endpoint: "http://127.0.0.1:9000/auth-url"
      status_endpoint: "http://127.0.0.1:9000/status"
secret_files:
  - "auth/codex.json"
services:
  cliproxyapi_plus:
    host: "127.0.0.1"
    port: 9000
    command:
      args: [".router/runtime/bin/CLIProxyAPIPlus"]
```

### Manual Migration Steps

If you prefer manual migration:

1. Add `config_version: 2` to your config file
2. Rename fields according to the mapping table:
   - `oauth` → `auth.providers`
   - `secrets` → `secret_files`
   - `services.cliproxyapi` → `services.cliproxyapi_plus`
3. Validate with: `flowgate --config config/flowgate.yaml doctor`

---

## Configuration Reference

### Paths Configuration

Defines runtime directory structure:

```yaml
paths:
  runtime_dir: ".router/runtime"           # Base runtime directory
  active_config: ".router/runtime/active_config.yaml"
  state_file: ".router/runtime/state.json"
  log_file: ".router/runtime/events.log"
  pid_dir: ".router/runtime/pids"
```

**Path Resolution**: Paths are resolved relative to the config file directory. See [Path Resolution](#path-resolution) for details.

### Services Configuration

Define service endpoints and commands:

```yaml
services:
  litellm:
    command:
      args: [".router/runtime/bin/litellm"]
      cwd: "."
    host: "127.0.0.1"
    port: 4000
    health_path: "/health/liveliness"
    readiness_path: "/v1/models"

  cliproxyapi_plus:
    command:
      args: [".router/runtime/bin/CLIProxyAPIPlus"]
      cwd: "."
    host: "127.0.0.1"
    port: 5000
    health_path: "/health"
    readiness_path: "/v1/models"
```

**Required Service Fields**:
- `command.args`: Array of command and arguments
- `host`: Bind address (usually "127.0.0.1")
- `port`: Port number (1024-65535)

**Optional Service Fields**:
- `command.cwd`: Working directory (default: ".")
- `health_path`: Liveness check endpoint
- `readiness_path`: Readiness check endpoint

### Authentication Configuration

OAuth provider setup:

```yaml
auth:
  providers:
    codex:
      auth_url_endpoint: "http://127.0.0.1:9000/auth-url"
      status_endpoint: "http://127.0.0.1:9000/status"
    copilot:
      auth_url_endpoint: "http://127.0.0.1:9000/copilot/auth-url"
      status_endpoint: "http://127.0.0.1:9000/copilot/status"
```

### Credentials Configuration

Upstream API credentials:

```yaml
credentials:
  upstream:
    openai:
      file: ".router/secrets/openai_api_key"
    anthropic:
      env: "ANTHROPIC_API_KEY"
    custom:
      file: ".router/secrets/custom_api_key"
```

**Credential Types**:
- `file`: Path to file containing API key
- `env`: Environment variable name

### LiteLLM Base Configuration

Core LiteLLM settings:

```yaml
litellm_base:
  model_list:
    - model_name: "gpt-4"
      litellm_params:
        model: "openai/gpt-4"
        api_key: "${OPENAI_API_KEY}"

  router_settings:
    num_retries: 2
    timeout: 300
    fallbacks:
      - ["gpt-4", "claude-opus-4-6"]

  litellm_settings:
    drop_params: true
    success_callback: ["langfuse"]
```

### Profiles Configuration

Policy profiles for different strategies:

```yaml
profiles:
  reliability:
    litellm_settings:
      num_retries: 5
      retry_delay: 2
      timeout: 600
      fallbacks:
        - ["primary-model", "backup-model-1", "backup-model-2"]

  balanced:
    litellm_settings:
      num_retries: 2
      retry_delay: 1
      timeout: 300

  cost:
    litellm_settings:
      num_retries: 1
      retry_delay: 0.5
      timeout: 180
```

**Profile Strategies**:
- **reliability**: High retries, long cooldown, conservative fallbacks
- **balanced**: Default for daily usage
- **cost**: Minimal retries, cost-optimized fallback chain

---

## Path Resolution

FlowGate resolves paths using the `PathResolver` class. See [Path Resolution Technical Reference](../developer-guide/path-resolution.md) for implementation details.

### Resolution Rules

1. **Absolute Paths**: Used as-is
   ```yaml
   runtime_dir: "/absolute/path/to/runtime"  # Not modified
   ```

2. **Relative Paths**: Resolved relative to config file directory
   ```yaml
   # If config is at /project/config/flowgate.yaml:
   runtime_dir: ".router/runtime"
   # Resolves to: /project/.router/runtime
   ```

3. **Home Directory (`~`)**: Expanded to user home
   ```yaml
   runtime_dir: "~/.flowgate/runtime"
   # Resolves to: /Users/username/.flowgate/runtime
   ```

### Path Types Resolved

The following configuration paths are automatically resolved:

- `paths.*`: All path fields (runtime_dir, active_config, etc.)
- `secret_files`: Array of secret file paths
- `credentials.upstream.*.file`: Credential file paths
- `services.*.command.cwd`: Service working directories

---

## Best Practices

### Configuration Organization

1. **Use Version 2**: Always set `config_version: 2` explicitly
2. **Relative Paths**: Use relative paths for portability
3. **Environment Variables**: Use env vars for credentials when possible
4. **Validate Early**: Run `flowgate doctor` after config changes

### Security

1. **Never Commit Secrets**: Add `.router/secrets/` to `.gitignore`
2. **File Permissions**: Restrict secret files to 600 (owner read/write only)
3. **Use Secret Files**: Prefer file-based credentials over inline API keys
4. **Separate Configs**: Keep sensitive config separate from repo

Example `.gitignore`:
```
.router/secrets/
.router/auth/
config/flowgate.yaml
config/cliproxyapi.yaml
```

### Profile Management

1. **Start with Balanced**: Use `balanced` profile for daily work
2. **Reliability for Production**: Switch to `reliability` for critical work
3. **Cost for Experiments**: Use `cost` profile for testing and development
4. **Test Profile Switching**: Verify profile changes work before deployment

### Configuration Validation

Always validate configuration after changes:

```bash
# Comprehensive validation
flowgate --config config/flowgate.yaml doctor

# Quick check
flowgate --config config/flowgate.yaml status
```

---

## Troubleshooting

### Common Issues

#### "config_version 1 is deprecated" Warning

**Cause**: Using legacy config version 1
**Solution**: Run `flowgate config migrate`

```bash
flowgate --config config/flowgate.yaml config migrate
```

#### "Missing required key" Error

**Cause**: Required configuration field not present
**Solution**: Check [Configuration Reference](#configuration-reference) and add missing fields

Example fix:
```yaml
config_version: 2
paths:
  runtime_dir: ".router/runtime"  # Add missing paths
```

#### Port Conflict Errors

**Cause**: Port already in use by another process
**Solution**: Change port in services configuration

```yaml
services:
  litellm:
    port: 4001  # Changed from 4000
```

Check with: `lsof -i :4000`

#### Credential File Not Found

**Cause**: Credential file path incorrect
**Solution**: Verify path resolution relative to config directory

```yaml
credentials:
  upstream:
    openai:
      # If config is at /project/config/flowgate.yaml:
      file: "../.router/secrets/openai_api_key"  # Correct relative path
```

### Validation Commands

```bash
# Full diagnostic check
flowgate --config config/flowgate.yaml doctor

# Service status
flowgate --config config/flowgate.yaml status

# Health check
flowgate --config config/flowgate.yaml health

# Profile list
flowgate --config config/flowgate.yaml profile list
```

### Getting Help

- **Configuration Issues**: See [Troubleshooting Guide](troubleshooting.md)
- **Migration Problems**: Check migration backup files
- **Schema Questions**: Refer to example configs in `config/examples/`
- **Bugs**: [GitHub Issues](https://github.com/heliar-k/flowgate/issues)

---

## Migration FAQ

**Q: Do I need to migrate immediately?**
A: Yes, strongly recommended. Version 1 will stop working in v0.3.0.

**Q: Will my existing config break?**
A: No, version 1 configs work in v0.2.x with a deprecation warning.

**Q: Can I use both old and new field names?**
A: No, use only version 2 field names. New names take precedence.

**Q: What if migration fails?**
A: Restore from the automatic backup file (e.g., `flowgate.yaml.backup-TIMESTAMP`).

**Q: Can I rollback after migration?**
A: Yes, restore from the backup file created during migration.

---

## Related Documentation

- [Developer Guide: Config Internals](../developer-guide/config-internals.md) - Implementation details
- [Developer Guide: Path Resolution](../developer-guide/path-resolution.md) - Technical reference
- [User Guide: Profiles](profiles.md) - Profile management guide
- [User Guide: Authentication](authentication.md) - OAuth setup

---

**Last Updated**: 2026-02-19
**Config Version**: 2
**Status**: Current
