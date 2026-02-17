# FlowGate 接入指南（Claude Code / Codex）

本文面向把 `FlowGate` 作为本地统一网关的场景，重点覆盖：
- `Codex CLI` 如何直接接入
- `Claude Code` 当前可接入边界
- 一组可复现的本地验收命令

## 1. 兼容性结论（先看）

- `FlowGate` 北向接口是 **OpenAI-compatible**（默认 `http://127.0.0.1:4000/v1`）。
- `Codex CLI` 支持自定义 `model_providers`，可直接接入该接口。
- `Claude Code` 官方设置文档当前未提供“通用 OpenAI-compatible Base URL”开关。
  - 结论：`Claude Code` 不能直接指向 `FlowGate /v1`。
  - 如果必须走 Claude Code，需要额外提供 **Anthropic-compatible 适配层**（不在本仓库默认能力内）。

参考：
- Codex config: <https://developers.openai.com/codex/config>
- Codex auth: <https://developers.openai.com/codex/auth>
- Claude Code settings: <https://docs.anthropic.com/zh-CN/docs/claude-code/settings>

## 2. 启动并验证 FlowGate

以下命令使用仓库内脚本（无需手动激活 venv）：

```bash
export ROUTER_UPSTREAM_API_KEY="sk-local-test"
export CUSTOM_API_KEY="sk-dummy"

./scripts/xgate --config config/flowgate.yaml profile set balanced
./scripts/xgate --config config/flowgate.yaml service start all
./scripts/xgate --config config/flowgate.yaml status
curl --silent --show-error http://127.0.0.1:4000/v1/models
./scripts/xgate --config config/flowgate.yaml service stop all
```

说明：
- `status` 能确认进程是否在跑。
- `/v1/models` 能确认北向 OpenAI-compatible 入口是否可访问。
- `health` 会做更严格的上游探测；当上游模型不可用或超时时，`health` 可能失败，但这不一定代表网关进程没启动。

## 3. Codex CLI 接入（推荐路径）

### 3.1 配置 `~/.codex/config.toml`

追加示例（按需调整模型名和端口）：

```toml
[model_providers.flowgate]
name = "FlowGate Local"
base_url = "http://127.0.0.1:4000/v1"
env_key = "FLOWGATE_API_KEY"
wire_api = "chat"

[profiles.flowgate]
model_provider = "flowgate"
model = "router-default"
```

### 3.2 运行 Codex

```bash
export FLOWGATE_API_KEY="sk-local-test"

# 交互模式
codex --profile flowgate

# 非交互模式
codex exec --profile flowgate --skip-git-repo-check "say hello"
```

### 3.3 上游鉴权提醒

如果你的 `router-default` 走的是 `CLIProxyAPIPlus` 的 Codex provider，仍需先完成 provider 侧授权：

```bash
./scripts/xgate --config config/flowgate.yaml auth login codex
# 或
./scripts/xgate --config config/flowgate.yaml auth import-headless codex --source ~/.codex/auth.json
```

未授权时通常表现为：`/v1/models` 可访问，但真实对话请求返回上游鉴权/provider 错误。

## 4. Claude Code 接入说明

截至 2026-02-17，本仓库默认产出的北向接口是 OpenAI-compatible；
而 Claude Code 官方配置路径主要围绕 `ANTHROPIC_AUTH_TOKEN` 与 Claude 模型配置。

因此建议：
- 若目标是“今天就稳定可用”，优先走 `Codex + FlowGate`。
- 若必须接入 `Claude Code`，请先在 FlowGate 前增加 Anthropic-compatible 适配层，再让 Claude Code 指向该适配层。

## 5. 本地验收清单

建议在每次改动后执行：

```bash
./scripts/xtest
./scripts/xgate --help
./scripts/xgate --config config/flowgate.yaml profile list
```

