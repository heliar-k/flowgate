# Auth Usability and Extensibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让认证操作对用户更直观（低记忆成本），并把新增认证方式的改动范围收敛到可插拔注册点。

**Architecture:** CLI 统一使用 `auth <action> <provider>` 交互，配置层从仅 `oauth` 逐步过渡到统一 `auth.providers` 能力声明；认证方法通过注册表分发，避免把 provider/method 逻辑散落在命令分支中。保留旧命令和旧配置兼容层，确保平滑升级。

**Tech Stack:** Python 3.12, argparse, unittest, JSON/YAML config

---

### Task 1: 统一认证配置契约（兼容旧字段）

**Files:**
- Modify: `src/flowgate/config.py`
- Modify: `config/examples/flowgate.yaml`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

```python
def test_load_auth_providers_new_schema(self):
    data = self._base_config()
    data["auth"] = {
        "providers": {
            "codex": {"method": "oauth_poll", "auth_url_endpoint": "...", "status_endpoint": "..."}
        }
    }
    data.pop("oauth", None)
    path = self._write_config(data)
    cfg = load_router_config(path)
    self.assertIn("auth", cfg)
    self.assertIn("codex", cfg["auth"]["providers"])
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_config.ConfigTests.test_load_auth_providers_new_schema -v`
Expected: FAIL with unknown top-level key `auth` or missing schema mapping.

**Step 3: Write minimal implementation**

- 在 `config.py` 增加 `auth` 顶层 key 支持。
- 新增归一化逻辑：若仅有 `oauth`，迁移为 `auth.providers`。
- 输出结构中保留兼容读取入口，避免 CLI 一次性破坏。

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_config.ConfigTests.test_load_auth_providers_new_schema -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/flowgate/config.py config/examples/flowgate.yaml tests/test_config.py
git commit -m "feat(auth): add unified auth.providers schema with oauth compatibility"
```

### Task 2: 增加认证状态可观测命令

**Files:**
- Modify: `src/flowgate/cli.py`
- Modify: `README.md`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
def test_auth_status_reports_provider_capabilities(self):
    out = io.StringIO()
    code = run_cli(["--config", str(self.cfg), "auth", "status"], stdout=out)
    self.assertEqual(code, 0)
    self.assertIn("provider=codex", out.getvalue())
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_cli.CLITests.test_auth_status_reports_provider_capabilities -v`
Expected: FAIL with argparse invalid choice.

**Step 3: Write minimal implementation**

- 增加 `auth status` 子命令。
- 输出 provider、支持方法、默认认证文件路径、权限检查摘要。

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_cli.CLITests.test_auth_status_reports_provider_capabilities -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/flowgate/cli.py tests/test_cli.py README.md
git commit -m "feat(auth): add auth status command for operator visibility"
```

### Task 3: OAuth 登录容错与用户体验补齐

**Files:**
- Modify: `src/flowgate/oauth.py`
- Modify: `src/flowgate/cli.py`
- Test: `tests/test_oauth.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
def test_poll_auth_status_tolerates_transient_network_error(self):
    responses = [TimeoutError("x"), {"status": "pending"}, {"status": "success"}]
    with mock.patch("flowgate.oauth._get_json", side_effect=responses):
        status = poll_auth_status("http://example.local/status", timeout_seconds=3, poll_interval_seconds=0.01)
    self.assertEqual(status, "success")
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_oauth.OAuthTests.test_poll_auth_status_tolerates_transient_network_error -v`
Expected: FAIL with immediate exception.

**Step 3: Write minimal implementation**

- 在轮询中捕获短暂网络错误并继续重试直到超时。
- 在 CLI 错误信息中输出最后状态与可执行修复提示。

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_oauth.OAuthTests.test_poll_auth_status_tolerates_transient_network_error -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/flowgate/oauth.py src/flowgate/cli.py tests/test_oauth.py tests/test_cli.py
git commit -m "fix(auth): add transient error tolerance for oauth polling"
```

### Task 4: 认证方法插件化最小闭环

**Files:**
- Create: `src/flowgate/auth_methods.py`
- Modify: `src/flowgate/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
def test_auth_import_dispatches_by_registered_method(self):
    # provider method registry returns a fake handler and should be invoked once.
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_cli.CLITests.test_auth_import_dispatches_by_registered_method -v`
Expected: FAIL because registry abstraction does not exist.

**Step 3: Write minimal implementation**

- 抽取认证方法注册表与统一 handler 接口。
- CLI 只做参数解析和错误映射，不内嵌 provider-specific 逻辑。

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_cli.CLITests.test_auth_import_dispatches_by_registered_method -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/flowgate/auth_methods.py src/flowgate/cli.py tests/test_cli.py
git commit -m "refactor(auth): extract auth method registry and dispatch layer"
```

### Task 5: 全量回归与文档迁移说明

**Files:**
- Modify: `README.md`
- Modify: `docs/runbook-troubleshooting.md`
- Modify: `docs/plans/2026-02-16-current-plan-and-implementation-status.md`

**Step 1: Write the failing test**

```python
# 文档任务，无自动化测试，改为“命令可运行验收”。
```

**Step 2: Run verification commands**

Run: `uv run flowgate --help`
Run: `uv run flowgate auth --help`
Run: `uv run python -m unittest discover -s tests -v`
Expected: all pass.

**Step 3: Update docs**

- 增加新旧命令对照表。
- 标注配置迁移路径与兼容窗口。
- 补充“新增 provider/method 的最小步骤”。

**Step 4: Commit**

```bash
git add README.md docs/runbook-troubleshooting.md docs/plans/2026-02-16-current-plan-and-implementation-status.md
git commit -m "docs(auth): document migration path and extension playbook"
```
