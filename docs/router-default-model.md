# `router-default` 模型别名说明与改名 SOP

本文只讲一件事：`router-default` 是 FlowGate/LiteLLM 对外暴露给客户端的“路由别名”，不是上游厂商的原生模型名。

## TL;DR（改名别名最短路径）

1. 改 `config/flowgate.yaml` 的别名与 fallbacks 引用。
2. 重新生成 active 配置并重启服务：

```bash
./scripts/xgate --config config/flowgate.yaml profile set balanced
./scripts/xgate --config config/flowgate.yaml service restart all
```

3. 同步客户端模型字段（Codex `model`，Claude 的 `ANTHROPIC_*MODEL`）。
4. 用 `/v1/models` 与 `count_tokens` 验收（见本文“验收命令”）。

其它问题（端口/OAuth/权限/就绪探针）看：`docs/runbook-troubleshooting.md`。接入步骤看：`docs/integration-claude-code-codex.md`。

## 目录

- 1. 概念：别名 vs 上游模型名
- 2. 需要同步的配置位置
- 3. 推荐改名流程（SOP）
- 4. 验收命令与判定标准
- 5. 常见错误（只含别名相关）

## 1. 概念：别名 vs 上游模型名

- `router-default` 定义在 `litellm_base.model_list[].model_name`，是“客户端请求时看到/使用的模型名”。
- `litellm_params.model` 是转发到上游 provider 的真实模型标识，两者可以不同。

示例（`config/flowgate.yaml`）：

```json
{
  "litellm_base": {
    "model_list": [
      {
        "model_name": "router-default",
        "litellm_params": {
          "model": "openai/router-default"
        }
      }
    ]
  }
}
```

## 2. 需要同步的配置位置

当你把 `router-default` 改成 `router-main`（或任何别名）时，至少要同步：

- 网关别名：
  - `litellm_base.model_list[].model_name`
- fallback 引用：
  - `profiles.*.litellm_settings.fallbacks` 的 key/value（不能遗留旧别名）
- 客户端模型字段：
  - Codex：`~/.codex/config.toml` 的 `model = "..."`（或你使用的 profile 配置）
  - Claude Code：
    - `ANTHROPIC_MODEL`
    - `ANTHROPIC_DEFAULT_OPUS_MODEL`
    - `ANTHROPIC_DEFAULT_SONNET_MODEL`
    - `ANTHROPIC_DEFAULT_HAIKU_MODEL`

## 3. 推荐改名流程（SOP）

以 `router-default -> router-main` 为例：

1. 修改 `config/flowgate.yaml`：
   - 把 `model_list` 中 `model_name` 从 `router-default` 改为 `router-main`。
   - 把 `fallbacks` 中引用旧别名的位置全部替换为 `router-main`。
2. 重新生成并应用 active 配置，然后重启服务加载新配置：

```bash
./scripts/xgate --config config/flowgate.yaml profile set balanced
./scripts/xgate --config config/flowgate.yaml service restart all
```

3. 同步客户端模型名：
   - Codex：把 `model = "router-main"`。
   - Claude Code：把 `ANTHROPIC_*MODEL` 相关变量改为 `router-main`（或按你的槽位策略分别设置）。

注意：
- `integration print codex` / `integration print claude-code` 默认输出的模型名取决于你的 `config/flowgate.yaml`（通常是 `integration.default_model`）。如果你改了别名但没改 `integration.default_model`，输出可能仍是旧值。

## 4. 验收命令与判定标准

```bash
./scripts/xgate --config config/flowgate.yaml integration print codex
./scripts/xgate --config config/flowgate.yaml integration print claude-code
curl --silent --show-error http://127.0.0.1:4000/v1/models
curl -i http://127.0.0.1:4000/v1/messages/count_tokens \
  -H "content-type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -H "authorization: Bearer sk-local-test" \
  -d '{"model":"router-main","messages":[{"role":"user","content":"ping"}]}'
```

判定标准：
- `/v1/models` 能看到你配置后的路由别名（例如 `router-main`）。
- `count_tokens` 用新别名返回 `2xx`。

## 5. 常见错误（只含别名相关）

- 现象：`404 model not found`
  - 原因：客户端仍请求旧别名，但网关已改为新别名（或反过来）。
  - 修复：统一网关别名、fallback 引用、客户端模型字段。

- 现象：fallback 没触发或触发到错误模型
  - 原因：`profiles.*.litellm_settings.fallbacks` 遗留旧别名。
  - 修复：同步更新 `fallbacks` 的 key/value 并重新 `profile set`。

- 现象：Claude Code 仍请求错模型
  - 原因：只改了 `ANTHROPIC_MODEL`，未改 `ANTHROPIC_DEFAULT_*_MODEL`。
  - 修复：四个模型环境变量一起对齐。

- 现象：Claude 请求 404（路径错误）
  - 原因：`ANTHROPIC_BASE_URL` 配成了 `http://127.0.0.1:4000/v1`。
  - 修复：改成根地址 `http://127.0.0.1:4000`。
