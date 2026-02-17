# `router-default` 模型名配置说明

本文聚焦一个核心点：`router-default` 不是上游厂商的原生模型名，而是 FlowGate/LiteLLM 对外暴露的“路由别名”。

## 1. `router-default` 是什么

- `router-default` 是 `litellm_base.model_list[].model_name` 中定义的对外模型别名。
- 客户端（Codex/Claude Code）请求时传入的是这个别名，不是 `litellm_params.model`。
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

## 2. 必须保持一致的配置位置

当你改动 `router-default`（例如改成 `router-main`）时，至少要同步以下位置：

- `litellm_base.model_list[].model_name`
- `profiles.*.litellm_settings.fallbacks` 的 key/value
- 客户端配置里的模型名

Codex 侧：
- `~/.codex/config.toml` 中 `model = "..."`。

Claude Code 侧：
- `ANTHROPIC_MODEL`
- `ANTHROPIC_DEFAULT_OPUS_MODEL`
- `ANTHROPIC_DEFAULT_SONNET_MODEL`
- `ANTHROPIC_DEFAULT_HAIKU_MODEL`

## 3. 推荐改名流程（`router-default` -> `router-main`）

1. 修改 `config/flowgate.yaml`：
   - 把 `model_list` 中 `model_name` 从 `router-default` 改为 `router-main`。
   - 把 `fallbacks` 中引用旧别名的位置全部替换为新别名。
2. 重新生成并应用 active 配置：

```bash
./scripts/xgate --config config/flowgate.yaml profile set balanced
./scripts/xgate --config config/flowgate.yaml service restart all
```

3. 同步客户端模型名：
   - Codex：把 `model = "router-main"`。
   - Claude Code：把 `ANTHROPIC_*MODEL` 相关变量改为 `router-main`（或按你的快慢模型策略分别设置）。

当前版本注意：
- `integration print codex` / `integration print claude-code` 默认片段模型名是 `router-default`。
- 如果你已改名为 `router-main`，请在客户端配置中手动替换为新别名。

## 4. 验证命令

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
- `/v1/models` 能看到你配置后的路由别名。
- `count_tokens` 用新别名返回 `2xx`。

## 5. 常见错误与修复

- 现象：`404 model not found`  
  原因：客户端模型名仍是 `router-default`，但网关已改为 `router-main`（或反过来）。  
  修复：统一网关与客户端的模型别名。

- 现象：fallback 没触发  
  原因：`profiles.*.litellm_settings.fallbacks` 仍引用旧别名。  
  修复：同步更新 `fallbacks` 的 key/value 并重新 `profile set`。

- 现象：Claude Code 仍请求错模型  
  原因：只改了 `ANTHROPIC_MODEL`，未改 `ANTHROPIC_DEFAULT_*_MODEL`。  
  修复：四个模型环境变量一起对齐。

- 现象：Claude 请求 404（路径错误）  
  原因：`ANTHROPIC_BASE_URL` 配成了 `http://127.0.0.1:4000/v1`。  
  修复：改成根地址 `http://127.0.0.1:4000`。
