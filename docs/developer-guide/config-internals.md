# Config Internals

Key modules:

- `src/flowgate/config.py`: config load/normalize/validate + merge helper
- `src/flowgate/validators.py`: structural validation
- `src/flowgate/config_utils/path_resolver.py`: resolves relative paths against config directory
- `src/flowgate/profile.py`: profile activation + api_key_ref resolution

For user-facing schema reference, see `docs/user-guide/configuration.md`.

