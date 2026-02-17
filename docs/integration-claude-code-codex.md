# FlowGate 接入指南（Codex + Claude Code）

本文面向把 `FlowGate` 作为本地统一网关的场景，覆盖：
- `Codex CLI` 接入（OpenAI-compatible）
- `Claude Code` 接入（Anthropic Messages-compatible）
- 可复现的本地验收命令与排障路径

## 1. 兼容性结论（先看）

- `FlowGate` 北向由 LiteLLM 提供，默认入口是 `http://127.0.0.1:4000`。
- `Codex CLI` 可通过 OpenAI-compatible `.../v1` 入口接入。
- `Claude Code` 可通过 `ANTHROPIC_BASE_URL` 指向同一网关入口接入（要求网关支持 Anthropic Messages API）。
- Claude Code 可通过 FlowGate 接入，不再需要额外的独立适配层。

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

## 6. `router-default`（模型名称）配置要点

`router-default` 是 FlowGate/LiteLLM 暴露给客户端的路由别名，不是上游厂商模型名本身。

- 改名时要同时更新：
  - `litellm_base.model_list[].model_name`
  - `profiles.*.litellm_settings.fallbacks`
  - 客户端模型字段（Codex `model`，Claude 的 `ANTHROPIC_*MODEL`）
- 改完配置必须执行一次：
  - `profile set <name>` 重新生成 active 配置
  - `service restart all` 让运行中的服务加载新配置

完整操作步骤与排障细节见：`docs/router-default-model.md`。

## 7. 本地验收清单

建议每次改动后执行：

```bash
./scripts/xtest
./scripts/xgate --help
./scripts/xgate --config config/flowgate.yaml integration print codex
./scripts/xgate --config config/flowgate.yaml integration print claude-code
```

## 8. 示例 A：Codex 配置 `gpt-5.2`（OpenAI 主路由 + GitHub Copilot 兜底）

`config/flowgate.yaml` 关键片段（示例）：

```json
{
  "litellm_base": {
    "model_list": [
      {
        "model_name": "router-gpt52-openai",
        "litellm_params": {
          "model": "openai/gpt-5.2",
          "api_base": "https://api.openai.com/v1",
          "api_key": "os.environ/UPSTREAM_OPENAI_API_KEY"
        }
      },
      {
        "model_name": "router-gpt52-copilot-fallback",
        "litellm_params": {
          "model": "openai/gpt-5.2",
          "api_base": "http://127.0.0.1:18317/v1",
          "api_key": "os.environ/ROUTER_UPSTREAM_API_KEY"
        }
      }
    ]
  },
  "profiles": {
    "balanced": {
      "litellm_settings": {
        "fallbacks": [{"router-gpt52-openai": ["router-gpt52-copilot-fallback"]}]
      }
    }
  },
  "integration": {
    "default_model": "router-gpt52-openai",
    "fast_model": "router-gpt52-copilot-fallback"
  }
}
```

`~/.codex/config.toml` 示例：

```toml
model_provider = "flowgate"
model = "router-gpt52-openai"

[model_providers.flowgate]
name = "FlowGate Local"
base_url = "http://127.0.0.1:4000/v1"
env_key = "OPENAI_API_KEY"
wire_api = "responses"
```

配套环境变量（示例）：

```bash
export OPENAI_API_KEY="sk-gateway-token"
export UPSTREAM_OPENAI_API_KEY="sk-openai-upstream"
export ROUTER_UPSTREAM_API_KEY="sk-coproxy-local"
./scripts/xgate --config config/flowgate.yaml auth login copilot
```

## 9. 示例 B：Claude Code 三槽位模型（`claude-opus-4.6` / `claude-sonnet-4.5` / `claude-haiku-4.5`，来源为 GitHub Copilot + 自定义 API）

`config/flowgate.yaml` 关键片段（示例）：

```json
{
  "litellm_base": {
    "model_list": [
      {
        "model_name": "router-claude-opus-4-6-copilot",
        "litellm_params": {
          "model": "openai/claude-opus-4.6",
          "api_base": "http://127.0.0.1:18317/v1",
          "api_key": "os.environ/ROUTER_UPSTREAM_API_KEY"
        }
      },
      {
        "model_name": "router-claude-sonnet-4-5-custom",
        "litellm_params": {
          "model": "openai/claude-sonnet-4.5",
          "api_base": "https://api.vendor.example/v1",
          "api_key": "os.environ/CUSTOM_API_KEY"
        }
      },
      {
        "model_name": "router-claude-haiku-4-5-custom",
        "litellm_params": {
          "model": "openai/claude-haiku-4.5",
          "api_base": "https://api.vendor.example/v1",
          "api_key": "os.environ/CUSTOM_API_KEY"
        }
      }
    ]
  },
  "integration": {
    "default_model": "router-claude-sonnet-4-5-custom",
    "fast_model": "router-claude-haiku-4-5-custom"
  }
}
```

`~/.claude/settings.json`（或等效 env）示例：

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
    "ANTHROPIC_AUTH_TOKEN": "sk-gateway-token",
    "ANTHROPIC_MODEL": "router-claude-sonnet-4-5-custom",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "router-claude-opus-4-6-copilot",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "router-claude-sonnet-4-5-custom",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "router-claude-haiku-4-5-custom"
  }
}
```

说明：
- `ANTHROPIC_BASE_URL` 需指向网关根地址（`http://127.0.0.1:4000`），不是 `/v1`。
- 目前 `integration print claude-code` 默认是 `default_model` 同时映射到 `OPUS/SONNET`、`fast_model` 映射到 `HAIKU`；若三槽位要分别指定，请按上面方式手动设置 `ANTHROPIC_DEFAULT_*_MODEL`。
- 若你的上游厂商模型命名不同，请按厂商要求替换示例中的模型名。
