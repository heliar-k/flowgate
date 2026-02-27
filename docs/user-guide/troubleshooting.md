# Troubleshooting (v3, cliproxy-only)

Start with:

```bash
uv run flowgate --config config/flowgate.yaml status
uv run flowgate --config config/flowgate.yaml health --verbose
uv run flowgate --config config/flowgate.yaml doctor
```

## Common issues

### `port-in-use` when starting

- Another process is already using the configured `host:port` from `config/cliproxyapi.yaml`.
- Fix: change `port` in `config/cliproxyapi.yaml` or stop the conflicting process.

### `401` / `Unauthorized` when calling `/v1/...`

- Your client is missing `Authorization: Bearer <api-key>` or the key is not in `api-keys`.
- Fix: update your client config or `api-keys` in `config/cliproxyapi.yaml`.

### `auth login` fails with “endpoints not configured or derivable”

- FlowGate can’t find cliproxy `host`/`port` to derive endpoints, and you didn’t provide explicit endpoints.
- Fix: ensure `cliproxyapi_plus.config_file` is correct and the cliproxy config includes `port`.

### `auth login` returns `404` from `/v0/management/...`

- CLIProxyAPIPlus management endpoints require `remote-management.secret-key`.
- Fix: set `remote-management.secret-key` in `config/cliproxyapi.yaml`, restart the service, then retry.

## Where to look

- PIDs: `.router/runtime/pids/`
- Events: `.router/runtime/events.log`
- Auth artifacts: `.router/auths/` (or `auth-dir` in cliproxy config)

