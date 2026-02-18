# FlowGate 接入指南（Codex CLI + Claude Code）

把 `FlowGate` 当作本地统一网关时，这份文档是唯一入口：启动网关、生成客户端配置、做最小验收。

## TL;DR（最小可跑）

1. 生成并应用 active 配置，然后启动服务：

```bash
./scripts/xgate --config config/flowgate.yaml profile set balanced
./scripts/xgate --config config/flowgate.yaml service start all
./scripts/xgate --config config/flowgate.yaml status
```

2. 生成客户端配置片段（以输出为准）：

```bash
./scripts/xgate --config config/flowgate.yaml integration print codex
./scripts/xgate --config config/flowgate.yaml integration print claude-code
```

3. 验收（OpenAI-compatible / Anthropic Messages）：

```bash
curl --silent --show-error http://127.0.0.1:4000/v1/models
curl -i http://127.0.0.1:4000/v1/messages/count_tokens \
  -H "content-type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -H "authorization: Bearer sk-local-test" \
  -d '{"model":"router-default","messages":[{"role":"user","content":"ping"}]}'
```

遇到问题：
- 故障排查（端口/OAuth/401/404/权限/就绪探针）：`docs/runbook-troubleshooting.md`
- 模型别名改名（`router-default`）：`docs/router-default-model.md`
- 发版与回滚：`docs/release-and-rollback.md`

## 目录

- 1. 兼容性与结论
- 2. 启动并验证 FlowGate
- 3. 生成客户端配置片段（权威来源）
- 4. Codex CLI 接入
- 5. Claude Code 接入
- 6. 最小验收清单
- 附录 A：Codex 双上游示例（OpenAI 主路由 + Copilot 兜底）
- 附录 B：Claude Code 三槽位示例
- 参考链接

## 1. 兼容性与结论

- `FlowGate` 北向由 LiteLLM 提供，默认入口是 `http://127.0.0.1:4000`。
- `Codex CLI` 通过 OpenAI-compatible `.../v1` 接入。
- Claude Code 可通过 `ANTHROPIC_BASE_URL` 指向同一网关入口接入（要求网关支持 Anthropic Messages API）。

## 2. 启动并验证 FlowGate

以下命令使用仓库内脚本（无需手动激活 venv）。示例里使用本地假 token，你可按自身网关鉴权策略替换：

```bash
mkdir -p .router/secrets
printf '%s\n' "sk-local-test" > .router/secrets/upstream_cliproxyapi_api_key
chmod 600 .router/secrets/upstream_cliproxyapi_api_key
export CUSTOM_API_KEY="sk-dummy"

./scripts/xgate --config config/flowgate.yaml profile set balanced
./scripts/xgate --config config/flowgate.yaml service start all
./scripts/xgate --config config/flowgate.yaml status
curl --silent --show-error http://127.0.0.1:4000/v1/models
```

## 3. 生成客户端配置片段（权威来源）

不要手写猜测配置，优先用 FlowGate 输出作为单一事实来源：

```bash
./scripts/xgate --config config/flowgate.yaml integration print codex
./scripts/xgate --config config/flowgate.yaml integration print claude-code
```

其中：
- `integration print codex` 输出 `~/.codex/config.toml` 可用的 TOML 片段
- `integration print claude-code` 输出 Claude Code 需要的 env 变量（含 `ANTHROPIC_BASE_URL`、`ANTHROPIC_DEFAULT_*_MODEL`）

## 4. Codex CLI 接入

推荐直接使用 `integration print codex` 的输出。一个典型片段形态如下（以你的输出为准）：

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
- 若 `router-default` 走 `CLIProxyAPIPlus` 的 Codex provider，需要先完成 provider 侧授权

```bash
./scripts/xgate --config config/flowgate.yaml auth login codex
# 或（你已在 Codex CLI 做过 device auth）
./scripts/xgate --config config/flowgate.yaml auth import-headless codex --source ~/.codex/auth.json
```

## 5. Claude Code 接入

推荐使用 `integration print claude-code` 输出的环境变量。一个典型片段形态如下（以你的输出为准）：

```bash
ANTHROPIC_BASE_URL=http://127.0.0.1:4000
ANTHROPIC_AUTH_TOKEN=your-gateway-token
ANTHROPIC_MODEL=router-default
ANTHROPIC_DEFAULT_OPUS_MODEL=router-default
ANTHROPIC_DEFAULT_SONNET_MODEL=router-default
ANTHROPIC_DEFAULT_HAIKU_MODEL=router-default
```

说明：
- `ANTHROPIC_BASE_URL` 必须指向网关根地址（例如 `http://127.0.0.1:4000`），不要带 `/v1`。
- `ANTHROPIC_AUTH_TOKEN` 用于网关鉴权（可静态 token，也可配合 Claude `apiKeyHelper`）。
- `ANTHROPIC_DEFAULT_*_MODEL` 用于映射 Claude Code 的模型槽位，避免槽位解析漂移。

## 6. 最小验收清单

每次接入或改动配置后，建议用以下“固定动作”验收：

```bash
./scripts/xtest
./scripts/xgate --config config/flowgate.yaml status
./scripts/xgate --config config/flowgate.yaml health
curl --silent --show-error http://127.0.0.1:4000/v1/models
```

若 Claude Code 相关请求异常，优先按 runbook 的“401/404”与“模型别名不一致”分支排查：`docs/runbook-troubleshooting.md`。

## 附录 A：Codex 双上游示例（OpenAI 主路由 + GitHub Copilot 兜底）

`config/flowgate.yaml` 关键片段（示例）：

```json
{
  "credentials": {
    "upstream": {
      "cliproxy_default": {
        "file": "../.router/secrets/upstream_cliproxyapi_api_key"
      }
    }
  },
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
          "api_base": "http://127.0.0.1:8317/v1",
          "api_key_ref": "cliproxy_default"
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

配套密钥配置（示例）：

```bash
export OPENAI_API_KEY="sk-gateway-token"
export UPSTREAM_OPENAI_API_KEY="sk-openai-upstream"
mkdir -p .router/secrets
printf '%s\n' "sk-coproxy-local" > .router/secrets/upstream_cliproxyapi_api_key
chmod 600 .router/secrets/upstream_cliproxyapi_api_key
./scripts/xgate --config config/flowgate.yaml auth login copilot
```

## 附录 B：Claude Code 三槽位示例（Copilot + 自定义 API 混用）

`config/flowgate.yaml` 关键片段（示例）：

```json
{
  "credentials": {
    "upstream": {
      "cliproxy_default": {
        "file": "../.router/secrets/upstream_cliproxyapi_api_key"
      }
    }
  },
  "litellm_base": {
    "model_list": [
      {
        "model_name": "router-claude-opus-4-6-copilot",
        "litellm_params": {
          "model": "openai/claude-opus-4.6",
          "api_base": "http://127.0.0.1:8317/v1",
          "api_key_ref": "cliproxy_default"
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
- `ANTHROPIC_BASE_URL` 需指向网关根地址（`http://127.0.0.1:4000`），不要带 `/v1`。
- 目前 `integration print claude-code` 默认是 `default_model` 同时映射到 `OPUS/SONNET`、`fast_model` 映射到 `HAIKU`；若三槽位要分别指定，请按上面方式手动设置 `ANTHROPIC_DEFAULT_*_MODEL`。
- 若你的上游厂商模型命名不同，请按厂商要求替换示例中的模型名。

## 参考链接

- Codex config: <https://developers.openai.com/codex/config-advanced/>
- Codex auth: <https://developers.openai.com/codex/auth/>
- Claude Code LLM gateway: <https://docs.anthropic.com/en/docs/claude-code/llm-gateway>
- LiteLLM Anthropic unified endpoint: <https://docs.litellm.ai/docs/anthropic_unified/>
