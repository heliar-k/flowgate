# Remove LiteLLM (FlowGate → CLIProxyAPIPlus Wrapper) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 彻底移除 FlowGate 对 LiteLLM 的依赖与相关功能，让 FlowGate 专注成为「更易配置的 CLIProxyAPIPlus 控制面包装器」（bootstrap/service/auth/integration/health/doctor）。

**Architecture:** FlowGate 只管理一个本地进程：`CLIProxyAPIPlus`。FlowGate 的配置（`config/flowgate.yaml`）仅保存运行时目录与 `CLIProxyAPIPlus` 配置文件路径；FlowGate 在加载配置时解析 `cliproxyapi.yaml` 得到 `host/port`，并生成内部 `services.cliproxyapi_plus`（供现有 service/health/auth 逻辑复用）。移除所有 LiteLLM runner、profile/active config/state file、litellm_base/profiles/credentials 相关逻辑与文档。

**Tech Stack:** Python 3.11+, uv, **PyYAML**, pytest, subprocess, urllib

---

## Summary / Success Criteria

## Tradeoffs / What We’re Intentionally Dropping

- **No OpenAI-compatible “router layer” owned by FlowGate**: 不再通过 LiteLLM 提供统一的模型路由、（可选的）fallback/负载均衡、请求级别的策略拼装等；FlowGate 只负责启动/停止/健康检查/集成输出，真正的转发与策略能力以 CLIProxyAPIPlus 为准。
- **No profile-based policy switching**: 移除 `profile`（可靠性/均衡/成本）策略切换与 “active config/state file” 维护逻辑；如需多上游/重试/超时/路由策略，统一在 `cliproxyapi.yaml` 中配置。
- **Config version hard break**: 采用 `config_version: 3` 作为“只支持 cliproxy” 的新 schema；不做 v2 兼容与自动迁移（按计划提供文档迁移说明）。

### 用户可见行为（最终态）

- `flowgate profile ...` **不存在**（argparse 报错退出码 2）。
- `flowgate bootstrap download` 只下载/校验 `CLIProxyAPIPlus`，不再生成 `litellm` runner。
- `flowgate service start|stop|restart [all|cliproxyapi_plus]` 只管理 `cliproxyapi_plus`。
- `flowgate integration print codex` 输出 `base_url = "http://<cliproxy_host>:<cliproxy_port>/v1"`。
- `flowgate integration print claude-code` 输出 `ANTHROPIC_BASE_URL=http://<cliproxy_host>:<cliproxy_port>`。
- `flowgate doctor`/`health` 不再检查 LiteLLM（二进制/依赖/端口），而检查：
  - runtime dir 是否存在
  - `CLIProxyAPIPlus` 二进制是否存在且可执行
  - `cliproxyapi.yaml` 是否存在且可解析、包含 `port`
  - （提示项）若 `remote-management.secret-key` 为空则提示会导致 `/v0/management` 404
  - （提示项）若 `api-keys` 为空则提示客户端无法认证
- 文档与示例配置不再提 LiteLLM、profile、`router-default` 作为“网关别名”。

### 验收命令（repo 根目录）

1) 单测：

- Run: `uv run pytest tests/ -v`
- Expected: PASS

> 如果本地环境无法 `uv sync`（例如离线/无网络），先使用现有虚拟环境直接跑：`python -m pytest -p no:rerunfailures tests/ -v`。

2) 最小运行（本地手动）：

- Run: `uv run flowgate --config config/flowgate.yaml bootstrap download`
- Run: `uv run flowgate --config config/flowgate.yaml service start all`
- Run: `curl --silent --show-error http://127.0.0.1:8317/v1/models`
- Run: `uv run flowgate --config config/flowgate.yaml service stop all`
- Expected: `/v1/models` 返回 2xx，且进程可启动/停止

---

## Important Public API / Interface Changes

### CLI

- Removed: `flowgate profile list`, `flowgate profile set <name>`
- `status` 输出不再包含 `current_profile/updated_at`（因为不再维护 state file）

### Config Schema

- **New:** `config_version: 3`
- **Removed keys:** `litellm_base`, `profiles`, `credentials`
- **Changed `paths` required keys:**
  - Before: `runtime_dir`, `active_config`, `state_file`, `log_file`
  - After: `runtime_dir`, `log_file`
- **New required section:** `cliproxyapi_plus.config_file`（指向 CLIProxyAPIPlus 的 YAML 配置）

### Dependencies

- Remove: `litellm[proxy]`
- Add: `pyyaml`

---

## Assumptions (Explicit)

- FlowGate 配置文件推荐放在 `config/` 目录下，`cliproxyapi.yaml` 默认也放在同目录（便于相对路径）。
- `CLIProxyAPIPlus` 的相对路径（例如 `auth-dir: "./.router/auths"`）按 **进程工作目录** 解析；FlowGate 将把 `CLIProxyAPIPlus` 的 `cwd` 设为项目根目录（与当前 `config/examples/cliproxyapi.yaml` 语义一致）。
- 先不支持/不处理 `tls.enable: true` 的健康检查差异（如需支持再加任务）。

---

## Detailed Tasks (TDD, bite-sized)

### Task 0: Create a safe workspace + baseline

**Files:**
- Create: `docs/plans/2026-02-27-remove-litellm-focus-on-cliproxyapi-wrapper.md` (this file)

**Step 1: Create a worktree**

Run:
- `git worktree add .worktrees/remove-litellm -b remove-litellm`
- `cd .worktrees/remove-litellm`

Expected: worktree created

**Step 2: Snapshot current tests**

Run:
- `uv run pytest tests/ -q`

Expected: baseline result recorded in terminal (don’t fix unrelated failures)

---

### Task 1: Pin YAML parsing as a first-class dependency

**Files:**
- Modify: `pyproject.toml`
- (Later) Modify: `uv.lock`
- Test: `tests/test_yaml_dependency.py`

**Step 1: Write the failing test**

```python
import importlib
import pytest

@pytest.mark.unit
def test_pyyaml_is_installed():
    assert importlib.util.find_spec("yaml") is not None
```

**Step 2: Run test to verify it fails (current env may pass due to transitive deps)**

Run: `uv run pytest tests/test_yaml_dependency.py -v`

Expected: If it FAILs, proceed; if it PASSes, keep it anyway as regression.

**Step 3: Add explicit dependency**

Edit `pyproject.toml`:
- Add `pyyaml>=6,<7` to `[project].dependencies` (keep litellm for now; remove later)

**Step 4: Run test to verify it passes**

Run:
- `uv sync --group test --group dev`
- `uv run pytest tests/test_yaml_dependency.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml tests/test_yaml_dependency.py
git commit -m "chore(deps): add explicit pyyaml dependency"
```

---

### Task 2: Introduce `config_version: 3` (cliproxy-only) loader + validator

**Files:**
- Modify: `src/flowgate/config.py`
- Modify: `src/flowgate/validators.py`
- Modify: `src/flowgate/config_utils/path_resolver.py`
- Test: `tests/test_config_v3.py`

**Step 1: Write the failing test**

```python
import json
import tempfile
from pathlib import Path

import pytest

from flowgate.config import load_router_config

@pytest.mark.unit
def test_load_config_v3_derives_service_from_cliproxy_config():
    root = Path(tempfile.mkdtemp())
    cfg_dir = root / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)

    cliproxy_cfg = cfg_dir / "cliproxyapi.yaml"
    cliproxy_cfg.write_text(
        'host: "127.0.0.1"\\n'
        "port: 8317\\n"
        'api-keys: ["sk-local-test"]\\n'
        "remote-management:\\n"
        '  secret-key: "x"\\n',
        encoding="utf-8",
    )

    flowgate_cfg = cfg_dir / "flowgate.yaml"
    flowgate_cfg.write_text(
        json.dumps(
            {
                "config_version": 3,
                "paths": {
                    "runtime_dir": str(root / ".router" / "runtime"),
                    "log_file": str(root / ".router" / "runtime" / "events.log"),
                },
                "cliproxyapi_plus": {"config_file": str(cliproxy_cfg)},
                "auth": {"providers": {"codex": {"method": "oauth_poll"}}},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_router_config(flowgate_cfg)
    assert loaded["config_version"] == 3
    svc = loaded["services"]["cliproxyapi_plus"]
    assert svc["host"] == "127.0.0.1"
    assert svc["port"] == 8317
    assert svc["readiness_path"] == "/v1/models"
    assert "command" in svc and "args" in svc["command"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config_v3.py -v`

Expected: FAIL

**Step 3: Implement v3 config parsing**

- Set `_LATEST_CONFIG_VERSION = 3`
- Set `_SUPPORTED_CONFIG_VERSIONS = {3}` (hard removal per decision)
- Update required keys: only `paths` + `cliproxyapi_plus`
- Resolve `cliproxyapi_plus.config_file` relative to FlowGate config dir
- Parse cliproxy config to derive `host/port` and build `services.cliproxyapi_plus`

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config_v3.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/flowgate/config.py src/flowgate/validators.py tests/test_config_v3.py
git commit -m "refactor(config): add v3 cliproxy-only schema"
```

---

### Task 3: Make path resolution aware of `cliproxyapi_plus.config_file`

**Files:**
- Modify: `src/flowgate/config_utils/path_resolver.py`
- Test: `tests/test_path_resolver.py`

**Step 1: Write failing test**

Add to `tests/test_path_resolver.py`:

```python
def test_resolves_cliproxy_config_file_path(tmp_path):
    from flowgate.config_utils.path_resolver import PathResolver
    cfg_path = tmp_path / "config" / "flowgate.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)

    resolver = PathResolver(cfg_path)
    cfg = {
        "paths": {"runtime_dir": ".router/runtime", "log_file": ".router/runtime/events.log"},
        "cliproxyapi_plus": {"config_file": "cliproxyapi.yaml"},
        "services": {},
        "secret_files": [],
    }
    out = resolver.resolve_config_paths(cfg)
    assert out["cliproxyapi_plus"]["config_file"].endswith("/config/cliproxyapi.yaml")
```

**Step 2: Run to see FAIL**

Run: `uv run pytest tests/test_path_resolver.py -v`

Expected: FAIL

**Step 3: Implement**

In `PathResolver.resolve_config_paths()` add:
- If `cfg.get("cliproxyapi_plus", {})` contains `config_file: str`, resolve it.

**Step 4: Re-run**

Run: `uv run pytest tests/test_path_resolver.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/flowgate/config_utils/path_resolver.py tests/test_path_resolver.py
git commit -m "fix(config): resolve cliproxy config path"
```

---

### Task 4: Remove Profile feature end-to-end

**Files:**
- Delete: `src/flowgate/profile.py`
- Delete: `src/flowgate/cli/commands/profile.py`
- Modify: `src/flowgate/cli/parser.py`
- Modify: `src/flowgate/cli/__init__.py`
- Modify: `src/flowgate/cli/commands/health.py` (StatusCommand no longer reads state)
- Delete/Modify tests:
  - Delete: `tests/test_profile.py`
  - Delete: `tests/test_profile_errors.py`
  - Delete: `tests/test_integration_profile_switch.py`
  - Modify: `tests/test_cli.py`
  - Modify: `tests/integration/test_concurrent_operations.py` (remove profile sections)

**Step 1: Add failing test: parser rejects profile**

In `tests/test_cli.py` add:

```python
def test_profile_command_removed(self):
    parser = build_parser()
    with self.assertRaises(SystemExit) as ctx:
        parser.parse_args(["profile", "list"])
    assert ctx.exception.code != 0
```

**Step 2: Run test**

Run: `uv run pytest tests/test_cli.py::CLITests::test_profile_command_removed -v`

Expected: FAIL until parser updated

**Step 3: Remove argparse subparser**

Edit `src/flowgate/cli/parser.py`:
- Delete the entire `profile = sub.add_parser("profile") ...` block.

**Step 4: Remove dispatch + imports**

Edit `src/flowgate/cli/__init__.py`:
- Remove imports of `ProfileListCommand`, `ProfileSetCommand`
- Remove `if args.command == "profile": ...` block

**Step 5: Update StatusCommand**

Edit `src/flowgate/cli/commands/health.py`:
- `StatusCommand` should stop reading `state_file`
- New legacy output keys:
  - `services.<name>_running=yes/no`
  - `cliproxyapi_plus_config=<path>` (from `config["cliproxyapi_plus"]["config_file"]` if present)
  - `secret_permission_issues=<n>`
- JSON output should mirror (no `current_profile`)

**Step 6: Delete profile-related tests**

Remove the profile test files listed above; update any imports.

**Step 7: Run focused unit tests**

Run:
- `uv run pytest tests/test_cli.py -v`

Expected: PASS (update assertions that referenced `current_profile`)

**Step 8: Commit**

```bash
git add src/flowgate/cli/parser.py src/flowgate/cli/__init__.py src/flowgate/cli/commands/health.py tests/test_cli.py
git rm src/flowgate/profile.py src/flowgate/cli/commands/profile.py tests/test_profile.py tests/test_profile_errors.py tests/test_integration_profile_switch.py
git commit -m "refactor(cli): remove profile command"
```

---

### Task 5: Remove LiteLLM runner from bootstrap + doctor

**Files:**
- Modify: `src/flowgate/bootstrap.py`
- Modify: `src/flowgate/cli/commands/bootstrap.py`
- Modify: `src/flowgate/cli/commands/health.py` (DoctorCommand)
- Modify tests:
  - `tests/test_bootstrap.py`
  - `tests/test_cli.py` (bootstrap expectations)

**Step 1: Update tests to assert no litellm in bootstrap output**

In `tests/test_cli.py` update bootstrap download (legacy + json) to assert:
- prints `cliproxyapi_plus=...`
- does **not** print `litellm=...`
- json envelope does **not** include `litellm`

**Step 2: Run to see FAIL**

Run: `uv run pytest tests/test_cli.py -k bootstrap_download -v`

Expected: FAIL

**Step 3: Remove runner generation code**

Edit `src/flowgate/bootstrap.py`:
- Delete: `DEFAULT_LITELLM_VERSION`, `prepare_litellm_runner`, `validate_litellm_runner`

**Step 4: Update CLI bootstrap command**

Edit `src/flowgate/cli/commands/bootstrap.py`:
- Remove calls to `prepare_litellm_runner`/`validate_litellm_runner`
- Envelope `data` only contains cliproxy fields

**Step 5: Update DoctorCommand checks**

Edit `src/flowgate/cli/commands/health.py`:
- In required bins, remove `"litellm"`
- Remove `runtime_dependency_available("litellm")` check
- Add doctor check: `cliproxy_config` exists and parseable
  - id: `cliproxy_config`
  - status: pass/fail
  - suggestion: “copy config/examples/cliproxyapi.yaml to config/cliproxyapi.yaml”

**Step 6: Update `tests/test_bootstrap.py`**

- Remove tests `test_prepare_litellm_runner` and `test_validate_litellm_runner_*`
- Keep CLIProxyAPIPlus asset extraction and sha256 tests

**Step 7: Run focused tests**

Run:
- `uv run pytest tests/test_bootstrap.py -v`
- `uv run pytest tests/test_cli.py -k bootstrap -v`

Expected: PASS

**Step 8: Commit**

```bash
git add src/flowgate/bootstrap.py src/flowgate/cli/commands/bootstrap.py src/flowgate/cli/commands/health.py tests/test_bootstrap.py tests/test_cli.py
git commit -m "refactor(bootstrap): remove litellm runner support"
```

---

### Task 6: Switch integration to CLIProxyAPIPlus base URLs

**Files:**
- Modify: `src/flowgate/integration.py`
- Modify: `tests/test_integration.py`
- Modify: `tests/test_cli.py` integration assertions
- Modify: `docs/user-guide/authentication.md`

**Step 1: Update tests for integration base_url**

Update `tests/test_integration.py` expectations:
- codex base_url ends with `:8317/v1`
- claude base_url is `:8317`

**Step 2: Run to see FAIL**

Run: `uv run pytest tests/test_integration.py -v`

Expected: FAIL

**Step 3: Implement**

Edit `src/flowgate/integration.py`:
- Replace `_litellm_base_url()` with `_cliproxy_base_url()` using `services.cliproxyapi_plus`
- `build_integration_specs()` returns:
  - codex.base_url = `<cliproxy_base>/v1`
  - claude_code.base_url = `<cliproxy_base>`
- Keep `integration.default_model/fast_model` but update defaults away from `router-default`:
  - default_model default: `"gpt-5"` (or `"gpt-5-codex"` if you prefer)
  - fast_model default: same as default_model

**Step 4: Update CLI integration print tests**

In `tests/test_cli.py`, replace hard-coded `4000` assertions with `8317`.

**Step 5: Run focused tests**

Run:
- `uv run pytest tests/test_integration.py -v`
- `uv run pytest tests/test_cli.py -k integration_print -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/flowgate/integration.py tests/test_integration.py tests/test_cli.py docs/user-guide/authentication.md
git commit -m "refactor(integration): target cliproxyapi base urls"
```

---

### Task 7: Remove LiteLLM constants + defaults sync updates

**Files:**
- Modify: `src/flowgate/constants.py`
- Modify: `tests/test_defaults_sync.py`
- Modify: `tests/fixtures/config_factory.py`
- Modify: `tests/test_validators.py`

**Step 1: Update defaults sync tests**

Edit `tests/test_defaults_sync.py`:
- Remove flowgate example checks for litellm_base
- Keep checking `config/examples/cliproxyapi.yaml` host/port
- Add check: v3 `config/examples/flowgate.yaml` loads and derives cliproxy port correctly

**Step 2: Run to see FAIL**

Run: `uv run pytest tests/test_defaults_sync.py -v`

Expected: FAIL

**Step 3: Update constants**

Edit `src/flowgate/constants.py`:
- Remove `LITELLM_SERVICE`, ports/readiness paths for litellm
- Keep only `CLIPROXYAPI_PLUS_SERVICE`, defaults host/port/readiness

**Step 4: Update ConfigFactory**

Edit `tests/fixtures/config_factory.py`:
- Replace `minimal()` to generate v3 config + helper to write a minimal cliproxy config file for tests
- Remove `litellm_base_*`, `with_profiles`, `profile()`

**Step 5: Update validator tests**

Edit `tests/test_validators.py`:
- Remove sections that validate litellm_base/profiles/api_key_ref
- Add tests for `cliproxyapi_plus.config_file` required and `paths.runtime_dir/log_file` required

**Step 6: Run focused tests**

Run:
- `uv run pytest tests/test_validators.py -v`
- `uv run pytest tests/test_defaults_sync.py -v`

Expected: PASS

**Step 7: Commit**

```bash
git add src/flowgate/constants.py tests/test_defaults_sync.py tests/fixtures/config_factory.py tests/test_validators.py
git commit -m "refactor(config): drop litellm defaults and validators"
```

---

### Task 8: Update scripts (xgate/smoke) to remove profile and litellm ports

**Files:**
- Modify: `scripts/xgate`
- Modify: `scripts/smoke_local.sh`

**Step 1: Update xgate help + command mapping**

- Remove `profile` from help text
- Ensure examples use `service start all` directly

**Step 2: Update smoke_local flow**

Change steps to:
1) bootstrap download
2) start services
3) wait health readiness
4) verify `/v1/models` on cliproxy
5) probe `/v1/messages/count_tokens` on cliproxy (Claude compatible)
6) stop services

**Step 3: Sanity**

Run: `sh -n scripts/smoke_local.sh`

Expected: exit 0

**Step 4: Commit**

```bash
git add scripts/xgate scripts/smoke_local.sh
git commit -m "docs(scripts): remove profile/litellm from helpers"
```

---

### Task 9: Documentation refresh (remove LiteLLM from “current” docs)

**Files (high priority):**
- Modify: `README.md`
- Modify: `docs/user-guide/quick-start.md`
- Modify: `docs/user-guide/authentication.md`
- Modify: `docs/user-guide/cli-reference.md`
- Modify: `docs/user-guide/configuration.md`
- Modify: `docs/user-guide/profiles.md` (delete or replace)
- Modify/Delete: `docs/router-default-model.md` (delete or replace)
- Modify: `docs/architecture/c4-context.md`
- Modify: `docs/architecture/c4-containers.md`
- Modify: `docs/architecture/c4-deployment.md`
- Modify: `docs/architecture/diagrams.md`
- Modify: `AGENTS.md`
- Modify: `config/examples/flowgate.yaml` (v3 example)

**Step 1: Remove LiteLLM from top-level positioning**

- README tagline: remove “LiteLLM stacks”
- Replace architecture diagrams: only FlowGate CLI + CLIProxyAPIPlus

**Step 2: Update Quick Start**

- Remove profile steps
- Replace port defaults: only `8317`
- Replace test command: `curl http://127.0.0.1:8317/v1/models`

**Step 3: Update Authentication guide**

- State: base URL is CLIProxyAPIPlus (`http://127.0.0.1:8317`)
- Keep Codex/Claude Code integration print/apply instructions
- Ensure sample env vars reference `8317`

**Step 4: Remove profile docs**

- Delete `docs/user-guide/profiles.md`
- Delete `docs/router-default-model.md`
- Update all references

**Step 5: Add migration note**

In `docs/user-guide/configuration.md` add a “v2→v3 migration” section:
- Remove `litellm_base/profiles/credentials`
- Add `cliproxyapi_plus.config_file`
- Mention `profile` command removed
- Mention client base_url changed from `:4000` to `:8317`

**Step 6: Commit docs**

```bash
git add README.md docs AGENTS.md config/examples/flowgate.yaml
git commit -m "docs: remove litellm and profile from documentation"
```

---

### Task 10: Remove LiteLLM dependency + regenerate lockfile

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Step 1: Update `pyproject.toml`**

- `description` remove LiteLLM mention
- `[project].dependencies` remove `litellm[proxy]...` and keep `pyyaml...`

**Step 2: Regenerate lockfile**

Run:
- `uv lock`
- `uv sync --group test --group dev`

**Step 3: Full test run**

Run: `uv run pytest tests/ -v`

Expected: PASS

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): remove litellm dependency"
```
