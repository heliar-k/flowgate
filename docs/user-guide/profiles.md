# Profile Management

FlowGate profiles provide a simple way to switch LiteLLM routing/policy settings without editing multiple config files.

## Concepts

- `litellm_base`: The base LiteLLM configuration template.
- `profiles.<name>`: A profile overlay applied on top of `litellm_base` via a deep-merge.
- `api_key_ref`: A reference to `credentials.upstream.<ref>`; resolved at activation time into an `api_key`.

## Common Workflows

### List profiles

```bash
flowgate --config config/flowgate.yaml profile list
```

### Activate a profile

```bash
flowgate --config config/flowgate.yaml profile set balanced
```

What happens:
1. FlowGate merges `litellm_base` + `profiles.balanced`
2. Resolves `api_key_ref` into concrete `api_key` values
3. Writes the active LiteLLM config to `paths.active_config`
4. Writes profile state to `paths.state_file`
5. If `litellm` is already running, FlowGate restarts it to apply immediately

## Tips

- Use `flowgate status` to confirm the active profile.
- Use `flowgate health --verbose` if `litellm` readiness fails after switching.

