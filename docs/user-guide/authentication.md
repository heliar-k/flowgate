# Authentication (CLIProxyAPIPlus)

There are two different “auth” layers to keep in mind:

1) **Client auth (your local proxy)**: CLIProxyAPIPlus `api-keys` control who can call your local OpenAI-compatible endpoints (e.g. `/v1/models`). Your clients send `Authorization: Bearer <api-key>`.
2) **Upstream OAuth (Codex / Copilot)**: CLIProxyAPIPlus uses OAuth to talk to upstream providers. FlowGate helps you acquire/import those auth artifacts.

## OAuth login (interactive)

Prerequisites:
- CLIProxyAPIPlus is running (`flowgate service start all`)
- `config/cliproxyapi.yaml` sets `remote-management.secret-key`

Run:

```bash
uv run flowgate --config config/flowgate.yaml auth login codex
uv run flowgate --config config/flowgate.yaml auth login copilot
```

FlowGate prints a `login_url=...` and polls the status endpoint until success/timeout. Auth artifacts are written under the auth directory (by default `./.router/auths/`).

## Headless import (Codex)

If you already have a Codex auth JSON:

```bash
uv run flowgate --config config/flowgate.yaml auth import-headless codex --source ~/.codex/auth.json
```

## Check auth status and file permissions

```bash
uv run flowgate --config config/flowgate.yaml auth status
uv run flowgate --config config/flowgate.yaml doctor
```

## Endpoint derivation

If `auth.providers.<name>.auth_url_endpoint` / `status_endpoint` are omitted from `flowgate.yaml`, FlowGate derives them from the cliproxy `host:port`.

## Claude Code gateway env

Claude Code 可通过设置 `ANTHROPIC_BASE_URL` 指向本地代理来接入 CLIProxyAPIPlus。

When using Claude Code against your local proxy, you typically configure:

```bash
ANTHROPIC_BASE_URL=http://127.0.0.1:8317
ANTHROPIC_AUTH_TOKEN=sk-local-test
```

FlowGate can print/apply these settings via:

```bash
uv run flowgate --config config/flowgate.yaml integration print claude-code
uv run flowgate --config config/flowgate.yaml integration apply claude-code
```
