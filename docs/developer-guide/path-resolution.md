# Path Resolution in FlowGate

## Overview

FlowGate uses a unified `PathResolver` class to handle all configuration path resolution, ensuring consistent behavior across absolute and relative paths.

## Path Resolution Rules

### Absolute Paths
Absolute paths are preserved unchanged.

**Example**:
```yaml
paths:
  runtime_dir: /var/flowgate/runtime  # Unchanged
```

### Relative Paths
Relative paths are resolved relative to the configuration file's directory.

**Example**:
```yaml
# Config file: /etc/flowgate/config.yaml
paths:
  runtime_dir: .router  # Resolved to: /etc/flowgate/.router
```

## Supported Path Types

### 1. Top-Level Paths (`paths.*`)
All fields under `paths` section:
- `runtime_dir`
- `active_config`
- `state_file`
- `log_file`

**Example**:
```yaml
paths:
  runtime_dir: .router
  active_config: .router/runtime/active_config.yaml
  state_file: .router/runtime/state.json
  log_file: .router/runtime/events.log
```

### 2. Secret Files (`secret_files`)
List of secret file paths:
```yaml
secret_files:
  - secrets/api.key
  - secrets/db.password
```

### 3. Credential Files (`credentials.upstream.*.file`)
Nested credential file paths:
```yaml
credentials:
  upstream:
    openai:
      file: creds/openai.key
```

### 4. Service Working Directories (`services.*.command.cwd`)
Optional service working directories:
```yaml
services:
  litellm:
    command:
      cwd: runtime/litellm
```

## PathResolver API

### Class: `PathResolver`

**Location**: `src/flowgate/config_utils/path_resolver.py`

**Usage**:
```python
from pathlib import Path
from flowgate.config_utils.path_resolver import PathResolver

# Initialize resolver
config_path = Path("/etc/flowgate/config.yaml")
resolver = PathResolver(config_path)

# Resolve single path
resolved = resolver.resolve("logs/app.log")
# Returns: "/etc/flowgate/logs/app.log"

# Resolve all paths in config
config = {...}
resolved_config = resolver.resolve_config_paths(config)
```

### Methods

#### `__init__(config_path: Path)`
Initialize resolver with configuration file path.

**Parameters**:
- `config_path`: Path to the configuration file

**Attributes**:
- `config_dir`: Resolved absolute path to config file's directory

#### `resolve(path_str: str) -> str`
Resolve a single path string.

**Parameters**:
- `path_str`: Path string to resolve

**Returns**:
- Resolved absolute path as string

**Rules**:
- Absolute paths: returned unchanged
- Relative paths: resolved relative to `config_dir`

**Examples**:
```python
resolver = PathResolver(Path("/etc/flowgate/config.yaml"))

# Absolute path
resolver.resolve("/var/log/app.log")
# Returns: "/var/log/app.log"

# Relative path
resolver.resolve("logs/app.log")
# Returns: "/etc/flowgate/logs/app.log"

# Path with parent directory
resolver.resolve("../shared/data")
# Returns: "/etc/shared/data"
```

#### `resolve_config_paths(config: dict) -> dict`
Recursively resolve all path fields in configuration.

**Parameters**:
- `config`: Configuration dictionary

**Returns**:
- New configuration dictionary with all paths resolved (deep copy)

**Path types handled**:
1. `paths.*` fields
2. `secret_files` list
3. `credentials.upstream.*.file` paths
4. `services.*.command.cwd` paths

**Example**:
```python
resolver = PathResolver(Path("/etc/flowgate/config.yaml"))

config = {
    "paths": {"runtime_dir": ".router"},
    "secret_files": ["secrets/api.key"],
    "credentials": {
        "upstream": {
            "openai": {"file": "creds/openai.key"}
        }
    },
    "services": {
        "litellm": {
            "command": {"cwd": "runtime"}
        }
    }
}

resolved = resolver.resolve_config_paths(config)

# Results:
# resolved["paths"]["runtime_dir"] == "/etc/flowgate/.router"
# resolved["secret_files"][0] == "/etc/flowgate/secrets/api.key"
# resolved["credentials"]["upstream"]["openai"]["file"] == "/etc/flowgate/creds/openai.key"
# resolved["services"]["litellm"]["command"]["cwd"] == "/etc/flowgate/runtime"
```

## Implementation Details

### Deep Copy
`resolve_config_paths()` creates a deep copy of the configuration to avoid modifying the original:
```python
cfg = json.loads(json.dumps(config))
```

This ensures that:
- Original configuration remains unchanged
- Multiple resolvers can work on the same config
- No side effects from path resolution

### Type Safety
All path resolution includes appropriate type checks:
```python
if isinstance(value, str):
    cfg["paths"][key] = self.resolve(value)
```

This prevents errors when:
- Path fields are missing
- Path values are not strings
- Configuration structure is unexpected

### Null Safety
The implementation safely handles missing sections:
```python
cfg["secret_files"] = [
    self.resolve(p) for p in cfg.get("secret_files", [])
]
```

This ensures:
- Optional sections don't cause errors
- Empty lists are handled correctly
- Configuration can omit unused features

## Migration from Old Implementation

### Before (cli/utils.py)
```python
def _resolve_path(base_dir: Path, value: str) -> str:
    """Resolve single path (37 lines total with _resolve_config_paths)"""
    # ...

def _resolve_config_paths(config: dict, config_path: Path) -> dict:
    """Resolve all config paths (duplicate logic)"""
    # ...
```

### After (config_utils/path_resolver.py)
```python
class PathResolver:
    def resolve(self, path_str: str) -> str:
        """Resolve single path (unified implementation)"""
        # ...

    def resolve_config_paths(self, config: dict) -> dict:
        """Resolve all config paths (single source of truth)"""
        # ...
```

### Benefits
- **Code reduction**: 37 lines of duplicate code eliminated
- **Testability**: Dedicated test suite (21 tests)
- **Maintainability**: Single source of truth for path resolution
- **Documentation**: Clear API with docstrings and examples
- **Type safety**: Full type annotations with modern Python syntax

## Testing

PathResolver has comprehensive test coverage:
- **Total tests**: 21
- **Test file**: `tests/test_path_resolver.py`
- **Coverage**: All 4 path types, edge cases, data integrity

### Test Categories

**1. Initialization Tests** (2 tests)
- Absolute config path
- Relative config path

**2. Single Path Resolution** (5 tests)
- Absolute paths
- Relative paths
- Paths with parent directory (`../`)
- Current directory (`.`)
- Nested relative paths

**3. Config Path Resolution** (14 tests)
- Top-level paths (`paths.*`)
- Secret files list
- Credential files (nested)
- Service working directories
- Mixed absolute and relative paths
- Empty lists and missing sections
- Deep copy verification
- Original config preservation

**Run tests**:
```bash
# Run all PathResolver tests
uv run python -m unittest tests.test_path_resolver -v

# Run specific test case
uv run python -m unittest tests.test_path_resolver.TestPathResolverResolve -v

# Run with coverage
uv run pytest tests/test_path_resolver.py --cov=src/flowgate/config_utils/path_resolver --cov-report=term-missing
```

## Common Issues

### Q: Why was `config/` renamed to `config_utils/`?
**A**: Python naming conflict. Both `config.py` (module) and `config/` (directory) existed at the same level. Python prioritized the directory, causing import errors for `ConfigError` and other symbols from `config.py`.

**Solution**: Renamed directory to `config_utils/` to avoid the conflict while keeping the module name descriptive.

### Q: Do I need to update my configuration files?
**A**: No. PathResolver maintains complete backward compatibility with existing configurations. All path resolution behavior remains unchanged.

### Q: What happens if a path doesn't exist?
**A**: PathResolver only resolves paths; it does not validate existence. This is intentional:
- Allows configuration of paths that will be created later
- Separates path resolution from validation concerns
- Use `flowgate doctor` to check for missing files

### Q: Can I use `~` for home directory in paths?
**A**: Not directly. Python's `Path.expanduser()` is not applied by PathResolver. Use absolute paths or relative paths instead:

```yaml
# Not supported:
runtime_dir: ~/flowgate/.router

# Use instead:
runtime_dir: /home/username/flowgate/.router

# Or relative to config file:
runtime_dir: .router
```

### Q: How do I debug path resolution issues?
**A**: Use Python's interactive shell to test path resolution:

```python
from pathlib import Path
from flowgate.config_utils.path_resolver import PathResolver

resolver = PathResolver(Path("/path/to/your/config.yaml"))
print(resolver.resolve("your/relative/path"))
```

## Performance Considerations

### Deep Copy Overhead
Path resolution creates a deep copy of the configuration using `json.loads(json.dumps(config))`. This is:
- **Fast enough**: Configuration is typically small (< 1KB)
- **Safe**: Prevents accidental mutations
- **Simple**: Works with all JSON-serializable Python types

For large configurations, this takes ~1ms, which is negligible compared to I/O operations.

### Caching
PathResolver does not cache resolved paths. This is intentional:
- Configuration is loaded once at startup
- Path resolution is fast (< 1ms for typical configs)
- Caching would add complexity without measurable benefit

## References

- **Implementation**: `src/flowgate/config_utils/path_resolver.py` (127 lines)
- **Tests**: `tests/test_path_resolver.py` (414 lines, 21 tests)
- **Phase 2.2 Plan**: `docs/plans/phase-2-2-path-resolution-plan.md`
- **Task Reports**:
  - `docs/plans/phase-2-2-task-1-report.md` (PathResolver implementation)
  - `docs/plans/phase-2-2-task-2-report.md` (Test implementation)
  - `docs/plans/phase-2-2-task-3-report.md` (CLI refactoring)
  - `docs/plans/phase-2-2-task-4-report.md` (Validation)
- **Completion Report**: `docs/plans/phase-2-2-completion-report.md` (to be created)
