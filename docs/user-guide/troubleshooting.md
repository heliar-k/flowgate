# 故障排查 Runbook（本地 FlowGate）

本文覆盖 `flowgate` + `CLIProxyAPIPlus` + `LiteLLM` 的常见本地故障，按“症状 -> 快速确认 -> 修复动作”的节奏组织。

接入与验收主流程请看：`docs/integration-claude-code-codex.md`。模型别名改名请看：`docs/router-default-model.md`。

## TL;DR（先跑这三条）

```bash
uv run flowgate --config config/flowgate.yaml status
uv run flowgate --config config/flowgate.yaml health
tail -n 50 .router/runtime/events.log
```

如果还不清楚原因，再看：

```bash
ls -l .router/runtime/process-logs
curl -i http://127.0.0.1:4000/v1/models
```

## 1) 端口冲突（Port conflict）

现象：
- `service start all` 很快返回，但有服务没起来
- 日志出现 bind/port-in-use

快速确认：

```bash
lsof -nP -iTCP:4000 -sTCP:LISTEN
lsof -nP -iTCP:8317 -sTCP:LISTEN
uv run flowgate --config config/flowgate.yaml status
```

修复：
- 停掉冲突进程，或修改 `config/flowgate.yaml` 的 `services.<name>.port`
- 重启服务加载新端口：

```bash
uv run flowgate --config config/flowgate.yaml service restart all
```

## 2) OAuth 登录失败（Codex/Copilot）

现象：
- `auth login codex` / `auth login copilot` 非 0 退出
- 一直拿不到 `oauth_status`（或 events.log 没有 success）

快速确认：

```bash
uv run flowgate --config config/flowgate.yaml auth list
uv run flowgate --config config/flowgate.yaml auth status
uv run flowgate --config config/flowgate.yaml auth login codex --timeout 30 --poll-interval 2
uv run flowgate --config config/flowgate.yaml auth login copilot --timeout 30 --poll-interval 2
tail -n 50 .router/runtime/events.log
```

判定标准：
- events.log 出现 `"event": "oauth_login"` 且 `"result": "success"`

修复：
- 检查 config 里的 OAuth endpoint 路径是否正确
- 优先使用新 schema：`auth.providers`（旧的 `oauth` 仍兼容但不推荐）
- 如缺少 CLIProxyAPIPlus 二进制，先跑 `bootstrap download`
- 如 stderr 包含 timeout 的 `hint=...`，适当增大 `--timeout`，并复查 `auth status`

## 3) secret/auth 文件权限过宽

现象：
- `status` 显示 `secret_permission_issues>0`

快速确认：

```bash
uv run flowgate --config config/flowgate.yaml status
ls -l .router/auths
```

修复：

```bash
chmod 600 .router/auths/*.json
```

## 4) 运行时依赖或二进制缺失

现象：
- `service start` 报 command-not-found 或 missing binary

快速确认：

```bash
uv sync --group runtime --group test
uv run flowgate --config config/flowgate.yaml bootstrap download
ls -l .router/runtime/bin
```

判定标准：
- `.router/runtime/bin/CLIProxyAPIPlus`
- `.router/runtime/bin/litellm`

## 5) Readiness 探针失败

现象：
- `health` 输出 `readiness=fail`

快速确认：

```bash
uv run flowgate --config config/flowgate.yaml health
curl -i http://127.0.0.1:4000/v1/models
curl -i http://127.0.0.1:8317/v1/models
```

修复：
- 确认已生成并应用 active 配置（先跑 `profile set ...`）
- 查看 `.router/runtime/process-logs/*.log` 定位上游错误

## 6) Claude Code 走网关时 401/403/404

现象：
- Claude Code 通过代理访问时返回 `401 Unauthorized` / `403 Forbidden` / `404 Not Found`

快速确认：

```bash
uv run flowgate --config config/flowgate.yaml integration print claude-code
curl -i http://127.0.0.1:4000/v1/models
```

修复要点：
- `ANTHROPIC_BASE_URL` 必须是网关根地址（例如 `http://127.0.0.1:4000`），不要带 `/v1`
- `ANTHROPIC_AUTH_TOKEN` 要与网关鉴权策略匹配（静态 token 或 apiKeyHelper）
- 如模型槽位解析不稳定，显式设置：
  - `ANTHROPIC_DEFAULT_OPUS_MODEL`
  - `ANTHROPIC_DEFAULT_SONNET_MODEL`
  - `ANTHROPIC_DEFAULT_HAIKU_MODEL`

进一步验收（Anthropic Messages）请按接入文档执行：`docs/integration-claude-code-codex.md`。

## 7) 模型别名不一致（`router-default` 改了但没同步全链路）

现象：
- `Codex` 或 `Claude Code` 报 `404 model not found`
- `/v1/models` 能看到新别名，但客户端仍请求旧别名
- fallback 行为异常（未触发或触发到错误模型）

快速确认：

```bash
rg -n "router-default|router-main|fallbacks|model_name" config/flowgate.yaml
curl --silent --show-error http://127.0.0.1:4000/v1/models
```

修复（按 SOP 做完再验收）：
- 见：`docs/router-default-model.md`
