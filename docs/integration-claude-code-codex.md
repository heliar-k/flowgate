# FlowGate 接入指南（Codex + Claude Code）

本文面向把 `FlowGate` 作为本地统一网关的场景，覆盖：
- `Codex CLI` 接入（OpenAI-compatible）
- `Claude Code` 接入（Anthropic Messages-compatible）
- 可复现的本地验收命令与排障路径

## 1. 兼容性结论（先看）

- `FlowGate` 北向由 LiteLLM 提供，默认入口是 `http://127.0.0.1:4000`。
- `Codex CLI` 可通过 OpenAI-compatible `.../v1` 入口接入。
- `Claude Code` 可通过 `ANTHROPIC_BASE_URL` 指向同一网关入口接入（要求网关支持 Anthropic Messages API）。
- `Claude Code 可通过` FlowGate 接入，不再需要额外的独立适配层。

参考：
- Codex config: <https://developers.openai.com/codex/config-advanced/>
- Codex auth: <https://developers.openai.com/codex/auth/>
- Claude Code LLM gateway: <https://docs.anthropic.com/en/docs/claude-code/llm-gateway>
- LiteLLM Anthropic unified endpoint: <https://docs.litellm.ai/docs/anthropic_unified/>

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
- `status` 用于确认进程是否运行。
- `/v1/models` 用于确认 OpenAI-compatible 北向入口是否可达。

## 3. 使用 FlowGate 自动生成客户端配置片段

FlowGate 提供统一生成命令：

```bash
./scripts/xgate --config config/flowgate.yaml integration print codex
./scripts/xgate --config config/flowgate.yaml integration print claude-code
```

其中：
- `integration print codex` 输出 `~/.codex/config.toml` 可用的 TOML 片段。
- `integration print claude-code` 输出 Claude Code 需要的 env 变量（含 `ANTHROPIC_BASE_URL`、`ANTHROPIC_DEFAULT_*_MODEL`）。

## 4. Codex CLI 接入

推荐直接使用 `integration print codex` 的输出，核心字段如下：

```toml
model_provider = "flowgate"
model = "router-default"

[model_providers.flowgate]
name = "FlowGate Local"
base_url = "http://127.0.0.1:4000/v1"
env_key = "OPENAI_API_KEY"
wire_api = "responses"
```

运行示例：

```bash
export OPENAI_API_KEY="sk-local-test"
codex --profile flowgate
```

上游鉴权提醒：
- 若 `router-default` 走 `CLIProxyAPIPlus` 的 Codex provider，仍需先完成 provider 侧授权：

```bash
./scripts/xgate --config config/flowgate.yaml auth login codex
# 或
./scripts/xgate --config config/flowgate.yaml auth import-headless codex --source ~/.codex/auth.json
```

## 5. Claude Code 接入

推荐使用 `integration print claude-code` 输出的环境变量，核心字段如下：

```bash
ANTHROPIC_BASE_URL=http://127.0.0.1:4000
ANTHROPIC_AUTH_TOKEN=your-gateway-token
ANTHROPIC_MODEL=router-default
ANTHROPIC_DEFAULT_OPUS_MODEL=router-default
ANTHROPIC_DEFAULT_SONNET_MODEL=router-default
ANTHROPIC_DEFAULT_HAIKU_MODEL=router-default
```

说明：
- `ANTHROPIC_BASE_URL` 指向 FlowGate/LiteLLM 网关入口。
- `ANTHROPIC_AUTH_TOKEN` 用于网关鉴权（可静态 token，也可配合 Claude `apiKeyHelper`）。
- `ANTHROPIC_DEFAULT_*_MODEL` 用于映射 Claude Code 的模型槽位，避免别名解析漂移。

## 6. 本地验收清单

建议每次改动后执行：

```bash
./scripts/xtest
./scripts/xgate --help
./scripts/xgate --config config/flowgate.yaml integration print codex
./scripts/xgate --config config/flowgate.yaml integration print claude-code
```
