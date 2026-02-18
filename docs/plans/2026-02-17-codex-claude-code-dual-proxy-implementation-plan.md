# Codex + Claude Code Dual Proxy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在同一套 FlowGate 运行时中，同时稳定支持 Codex 与 Claude Code 通过本地代理接入，并提供可重复配置与验收路径。

**Architecture:** 继续以 LiteLLM 作为北向统一网关，不新增独立适配服务。Codex 走 OpenAI-compatible `/v1`，Claude Code 走 Anthropic Messages-compatible `/v1/messages`。FlowGate 新增“客户端集成配置生成 + 可选安全写入”能力，避免手工配置漂移。

**Tech Stack:** Python 3.12, FlowGate CLI, LiteLLM Proxy, CLIProxyAPIPlus, unittest, shell scripts, TOML/JSON config management.

---

## 1. 调研结论（2026-02-17）

### 1.1 官方文档关键点

- Codex 已支持自定义 `model_providers`，可配置 `base_url` / `env_key` / `wire_api`，并支持通过 `OPENAI_BASE_URL` 覆盖默认 OpenAI 端点。
- Codex 本地凭据可落盘在 `~/.codex/auth.json`（或系统凭据存储），因此可以和 FlowGate 现有 headless 导入能力协同。
- Claude Code 现已明确支持 LLM Gateway：通过 `ANTHROPIC_BASE_URL` 指向网关，且要求网关至少暴露 Anthropic Messages API（`/v1/messages`、`/v1/messages/count_tokens`）并正确传递 `anthropic-*` 头。
- Claude Code 支持 `ANTHROPIC_AUTH_TOKEN`（静态 token）和 `apiKeyHelper`（动态 token）两种认证接入网关。
- LiteLLM 官方已提供 Anthropic unified endpoint（`/v1/messages` + `/v1/messages/count_tokens`），说明 FlowGate 可以在不新增独立 Anthropic 适配服务的前提下完成双客户端接入。

### 1.2 开源实现可借鉴点

- `cc-switch`：
  - Claude 侧采用 `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`，并显式管理 `ANTHROPIC_DEFAULT_*_MODEL` 槽位。
  - 在“接管模式”切换供应商时会清理旧模型覆盖变量，避免客户端继续发旧模型名导致失败。
  - Codex 侧只改 `model_providers.<active>.base_url`，并注意保留非供应商配置（例如 MCP 段）。
- `quotio`：
  - 对 `~/.claude/settings.json` 做“可恢复变更”：写入前备份，恢复时按受管键清理。
  - 将 Claude 的 Opus/Sonnet/Haiku 作为独立 model slot 管理，避免单一模型字段造成体验不稳定。

### 1.3 对本仓库的直接影响

- 当前 `docs/integration-claude-code-codex.md` 中“Claude Code 不能直接接入 FlowGate”的结论已过期，需要改为“可通过 Anthropic gateway 接入，前提是网关端点与头传递满足要求”。
- FlowGate 代码层缺少统一的“客户端配置生成能力”：当前用户仍需手写 `~/.codex/config.toml` 与 `~/.claude/settings.json`。
- FlowGate 缺少双客户端回归验收项（仅有通用健康检查与 smoke）。

---

## 2. 改造范围（P0 / P1）

### P0（必须）

1. 新增“客户端集成渲染”模块，统一生成 Codex/Claude Code 配置片段。
2. CLI 新增 `integration` 命令，输出可直接复制的配置（Codex TOML、Claude JSON/env）。
3. 文档修正与升级（兼容性结论、操作路径、验收命令）。
4. 增加双客户端最小回归测试（单元 + CLI）。

### P1（建议）

1. `integration apply` 安全写入模式（可选），带备份与受管字段合并策略。
2. `smoke` 增加 Claude Messages 端点探测，覆盖 `/v1/messages` 与 `/v1/messages/count_tokens`。
3. `doctor` 增加客户端配置一致性提示（不强制修改用户 home 配置）。

---

## 3. 详细执行任务（TDD + 小步提交）

### Task 1: 新增客户端集成渲染核心模块

**Files:**
- Create: `src/flowgate/integration.py`
- Create: `tests/test_integration.py`

**Step 1: Write the failing test**

```python
def test_build_integration_specs_from_litellm_service():
    cfg = {
        "services": {"litellm": {"host": "127.0.0.1", "port": 4000}},
        "integration": {"default_model": "router-default", "fast_model": "router-cheap"},
    }
    specs = build_integration_specs(cfg)
    assert specs["codex"]["base_url"] == "http://127.0.0.1:4000/v1"
    assert specs["claude_code"]["base_url"] == "http://127.0.0.1:4000"
    assert specs["claude_code"]["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "router-default"
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_integration -v`
Expected: FAIL with `ModuleNotFoundError` or missing function `build_integration_specs`.

**Step 3: Write minimal implementation**

```python
def build_integration_specs(config: dict[str, Any]) -> dict[str, Any]:
    litellm = config["services"]["litellm"]
    host = litellm.get("host", "127.0.0.1")
    port = litellm["port"]
    base = f"http://{host}:{port}"
    model = config.get("integration", {}).get("default_model", "router-default")
    fast = config.get("integration", {}).get("fast_model", model)
    return {
        "codex": {"base_url": f"{base}/v1", "model": model},
        "claude_code": {
            "base_url": base,
            "env": {
                "ANTHROPIC_MODEL": model,
                "ANTHROPIC_DEFAULT_SONNET_MODEL": model,
                "ANTHROPIC_DEFAULT_OPUS_MODEL": model,
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": fast,
            },
        },
    }
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_integration -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/flowgate/integration.py tests/test_integration.py
git commit -m "feat(integration): add dual-client integration spec builder"
```

### Task 2: CLI 增加 `integration` 命令（只读输出）

**Files:**
- Modify: `src/flowgate/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
def test_integration_print_claude(self):
    out = io.StringIO()
    code = run_cli(["--config", str(self.cfg), "integration", "print", "claude-code"], stdout=out)
    self.assertEqual(code, 0)
    self.assertIn("ANTHROPIC_BASE_URL=", out.getvalue())
    self.assertIn("ANTHROPIC_DEFAULT_SONNET_MODEL=", out.getvalue())
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_cli.CLITests.test_integration_print_claude -v`
Expected: FAIL with argparse unknown command `integration`.

**Step 3: Write minimal implementation**

```python
integration = sub.add_parser("integration")
integration_sub = integration.add_subparsers(dest="integration_cmd", required=True)
integration_print = integration_sub.add_parser("print")
integration_print.add_argument("client", choices=["codex", "claude-code"])
```

并在 `run_cli()` 分支调用 `build_integration_specs()`，分别输出：
- Codex: `model_provider` + `[model_providers.flowgate]` TOML 片段
- Claude Code: `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_DEFAULT_*_MODEL`

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_cli.CLITests.test_integration_print_claude -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/flowgate/cli.py tests/test_cli.py
git commit -m "feat(cli): add integration print command for codex and claude-code"
```

### Task 3: 文档升级与结论纠偏

**Files:**
- Modify: `docs/integration-claude-code-codex.md`
- Modify: `README.md`
- Modify: `docs/runbook-troubleshooting.md`

**Step 1: Write the failing test**

```python
def test_integration_doc_mentions_claude_gateway_support():
    text = Path("docs/integration-claude-code-codex.md").read_text(encoding="utf-8")
    self.assertIn("ANTHROPIC_BASE_URL", text)
    self.assertNotIn("不能直接指向", text)
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_defaults_sync -v` (or dedicated new doc test module)
Expected: FAIL because old文档仍写“不能直接接入”。

**Step 3: Write minimal implementation**

- 将“兼容性结论”改为：
  - Codex -> `http://127.0.0.1:4000/v1`
  - Claude Code -> `ANTHROPIC_BASE_URL=http://127.0.0.1:4000`
- 增加 `integration print codex|claude-code` 产物示例。
- 增加“模型槽位映射”说明（`ANTHROPIC_DEFAULT_*_MODEL`）。
- runbook 新增“Claude Code 走代理时 401/404 排查”。

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest discover -s tests -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add docs/integration-claude-code-codex.md README.md docs/runbook-troubleshooting.md
git commit -m "docs(integration): update dual-client gateway guidance for codex and claude-code"
```

### Task 4 (P1): 增加安全写入模式（受管键 + 备份）

**Files:**
- Create: `src/flowgate/client_apply.py`
- Modify: `src/flowgate/cli.py`
- Create: `tests/test_client_apply.py`

**Step 1: Write the failing test**

```python
def test_apply_claude_creates_backup_and_merges_managed_env_keys(self):
    # 1) 预置 ~/.claude/settings.json 模拟文件
    # 2) 运行 integration apply claude-code
    # 3) 断言 backup 文件存在
    # 4) 断言仅受管键被更新，其他用户配置保留
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_client_apply -v`
Expected: FAIL with missing module/command.

**Step 3: Write minimal implementation**

- 新增 `integration apply codex|claude-code --target <path>`。
- 写入前生成 `*.backup.<epoch>`。
- Claude 仅管理以下键：
  - `ANTHROPIC_BASE_URL`
  - `ANTHROPIC_AUTH_TOKEN`（若已有则更新）
  - `ANTHROPIC_DEFAULT_OPUS_MODEL`
  - `ANTHROPIC_DEFAULT_SONNET_MODEL`
  - `ANTHROPIC_DEFAULT_HAIKU_MODEL`
- Codex 仅更新当前 provider 的 `model_providers.<name>.base_url`，保留 `mcp_servers.*`。

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_client_apply -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/flowgate/client_apply.py src/flowgate/cli.py tests/test_client_apply.py
git commit -m "feat(integration): add safe apply mode with backup and managed-key merge"
```

### Task 5 (P1): 双客户端 smoke 验收

**Files:**
- Modify: `scripts/smoke_local.sh`
- Modify: `tests/test_dev_scripts.py`

**Step 1: Write the failing test**

```python
def test_smoke_script_has_claude_endpoint_probe(self):
    text = Path("scripts/smoke_local.sh").read_text(encoding="utf-8")
    self.assertIn("/v1/messages/count_tokens", text)
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_dev_scripts.DevScriptTests.test_smoke_script_has_claude_endpoint_probe -v`
Expected: FAIL (脚本尚未覆盖该端点)。

**Step 3: Write minimal implementation**

- 在 smoke 第 4.5 步后新增 Claude 端点探测：
  - `POST /v1/messages/count_tokens`
  - 请求头携带 `anthropic-version`
  - 验证 HTTP 非 404（推荐校验 2xx/4xx，排除 5xx/404）

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_dev_scripts -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/smoke_local.sh tests/test_dev_scripts.py
git commit -m "test(smoke): add claude messages endpoint probe in smoke flow"
```

---

## 4. 验收标准

- `integration print codex` 能输出可直接落地到 `~/.codex/config.toml` 的片段。
- `integration print claude-code` 能输出可直接落地到 `~/.claude/settings.json` 或 shell env 的片段。
- 文档明确声明：FlowGate 可同时支持 Codex（OpenAI-compatible）与 Claude Code（Anthropic Messages-compatible）。
- 全量测试通过：`uv run python -m unittest discover -s tests -v`。
- 本地 smoke 通过，且包含 Claude 消息端点探测（P1）。

---

## 5. 风险与对策

- 风险：Claude Code 模型名与网关模型别名不一致导致 400/404。
  对策：显式输出 `ANTHROPIC_DEFAULT_*_MODEL` 槽位，并在文档中给出推荐映射。

- 风险：直接覆盖用户 `~/.claude/settings.json` 或 `~/.codex/config.toml` 导致既有配置丢失。
  对策：P0 只做只读输出；P1 才引入 backup + 受管键合并。

- 风险：历史文档结论过期造成误导。
  对策：将兼容性结论集中到一处文档，并在 README 链接单一来源。

---

## 6. 参考资料

- OpenAI Codex Authentication: <https://developers.openai.com/codex/auth/>
- OpenAI Codex Advanced Config: <https://developers.openai.com/codex/config-advanced/>
- OpenAI Codex Config Reference: <https://developers.openai.com/codex/config-reference/>
- Anthropic Claude Code LLM Gateway: <https://docs.anthropic.com/en/docs/claude-code/llm-gateway>
- Anthropic Claude Code Model Configuration: <https://docs.anthropic.com/en/docs/claude-code/model-config>
- LiteLLM Anthropic Unified `/v1/messages`: <https://docs.litellm.ai/docs/anthropic_unified/>
- LiteLLM `/v1/messages/count_tokens`: <https://docs.litellm.ai/docs/anthropic_count_tokens>
- cc-switch (Claude/Codex proxy integration patterns): <https://github.com/farion1231/cc-switch>
- quotio (Claude settings backup/merge patterns): <https://github.com/nguyenphutrong/quotio>
