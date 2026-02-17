# Troubleshooting Runbook

This runbook focuses on common local issues for `flowgate` + `CLIProxyAPIPlus` + `LiteLLM`.

## 1) Port Conflict

Symptoms:
- `service start all` returns quickly but one service is not running.
- Process log shows bind/port-in-use errors.

Checks:
```bash
lsof -nP -iTCP:4000 -sTCP:LISTEN
lsof -nP -iTCP:8317 -sTCP:LISTEN
uv run flowgate --config config/flowgate.yaml status
```

Fix:
- Stop conflicting process or change `services.<name>.port` in `config/flowgate.yaml`.
- Run `uv run flowgate --config config/flowgate.yaml service restart all`.

## 2) OAuth Login Fails

Symptoms:
- `auth login codex` / `auth login copilot` exits non-zero.
- `oauth_status` is never returned.

Checks:
```bash
uv run flowgate --config config/flowgate.yaml auth list
uv run flowgate --config config/flowgate.yaml auth status
uv run flowgate --config config/flowgate.yaml auth login codex --timeout 30 --poll-interval 2
uv run flowgate --config config/flowgate.yaml auth login copilot --timeout 30 --poll-interval 2
tail -n 50 .router/runtime/events.log
```

Expected:
- Event line with `"event": "oauth_login"` and `"result": "success"`.

Fix:
- Verify OAuth endpoint paths in config.
- Prefer `auth.providers` in config. Legacy `oauth` is still accepted but no longer preferred.
- Re-run `bootstrap download` if CLIProxyAPIPlus binary is missing.
- If stderr includes timeout `hint=...`, increase `--timeout` and re-check `auth status`.

## 3) Secret/Auth Permission Issues

Symptoms:
- `status` shows `secret_permission_issues>0`.

Checks:
```bash
uv run flowgate --config config/flowgate.yaml status
ls -l .router/auths
```

Fix:
```bash
chmod 600 .router/auths/*.json
```

## 4) Missing Runtime Dependencies or Binaries

Symptoms:
- `service start` fails with command-not-found or missing binary messages.

Checks:
```bash
uv sync --group runtime --group test
uv run flowgate --config config/flowgate.yaml bootstrap download
ls -l .router/runtime/bin
```

Expected:
- `.router/runtime/bin/CLIProxyAPIPlus`
- `.router/runtime/bin/litellm`

## 5) Readiness Check Fails

Symptoms:
- `health` output shows `readiness=fail`.

Checks:
```bash
uv run flowgate --config config/flowgate.yaml health
curl -i http://127.0.0.1:4000/v1/models
curl -i http://127.0.0.1:8317/v1/models
```

Expected:
- Readiness endpoint returns HTTP `2xx`.

Fix:
- Ensure active profile has been generated (`profile set ...`).
- Check `.router/runtime/process-logs/*.log` for upstream error details.
