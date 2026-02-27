# Data Flows (v3, cliproxy-only)

FlowGate v3 manages a single local service: **CLIProxyAPIPlus**.

## 1) Config Load Flow

1. Operator runs a FlowGate CLI command with `--config config/flowgate.yaml`
2. FlowGate loads `flowgate.yaml` (config_version 3)
3. FlowGate resolves `cliproxyapi_plus.config_file` and parses `cliproxyapi.yaml`
4. FlowGate derives internal `services.cliproxyapi_plus`:
   - `host`/`port` from cliproxy config
   - `command.args` pointing at the bootstrapped CLIProxyAPIPlus binary
   - `readiness_path` set to `/v1/models`

This derived service definition is used by `service`, `health`, `doctor`, `auth`, and `integration`.

## 2) Bootstrap Download Flow

1. Operator runs `flowgate bootstrap download`
2. FlowGate detects platform/arch
3. FlowGate downloads CLIProxyAPIPlus release asset
4. FlowGate writes runtime artifacts under `paths.runtime_dir`:
   - `bin/CLIProxyAPIPlus`
   - version marker file (used by update checks)

## 3) Service Start/Stop/Restart Flow

1. Operator runs `flowgate service start all`
2. FlowGate checks port availability for `host:port`
3. FlowGate spawns `CLIProxyAPIPlus -config <cliproxyapi.yaml>` and records PID
4. Health checks probe `http://<host>:<port>/v1/models`

## 4) OAuth Login Flow (Codex/Copilot)

1. Operator runs `flowgate auth login codex`
2. FlowGate uses either configured endpoints (`auth.providers.*`) or derives them from cliproxy `host:port`
3. FlowGate calls `.../auth-url` to get a browser login URL
4. Operator completes login in browser
5. FlowGate polls `.../status` until success/timeout
6. CLIProxyAPIPlus writes auth artifacts under its configured `auth-dir` (default `./.router/auths`)

