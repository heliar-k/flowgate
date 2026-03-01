# FlowGate 项目结构重构计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构 FlowGate 项目结构，采用 `core/` + `cli/` 子包模式，消除冗余代码，删除不需要的集成功能，使项目结构清晰反映其定位：CLIProxyAPIPlus 的轻量包装工具。

**Architecture:** 将所有业务逻辑模块移入 `src/flowgate/core/` 子包，CLI 层保持在 `src/flowgate/cli/`。合并散落的 cliproxyapiplus 相关模块为单一模块，合并 config_utils 到 config，提取重复代码为共享 helper。

**Tech Stack:** Python 3.11+, pytest, argparse, PyYAML

**当前结构 → 目标结构:**

```
# 当前 (32 files, 5036 lines)
src/flowgate/
  __init__.py
  config.py                          # 配置加载
  config_utils/                      # ← 只有一个类，冗余子包
    __init__.py
    path_resolver.py
  constants.py
  process.py                         # 进程管理
  bootstrap.py                       # 下载/验证
  cliproxyapiplus_auto_update.py     # ← 4个文件可合并
  cliproxyapiplus_release.py         # ←
  cliproxyapiplus_update_check.py    # ←
  cliproxyapiplus_version.py         # ←
  oauth.py                           # OAuth 认证
  auth_methods.py                    # 认证方法注册
  headless_import.py                 # 无头导入
  health.py                          # 健康检查
  integration.py                     # ← 删除（集成功能）
  client_apply.py                    # ← 删除（集成功能）
  security.py                        # 权限检查
  observability.py                   # 事件日志
  validators.py                      # 配置验证
  utils.py                           # 杂项工具
  cli/
    __init__.py                      # run_cli + 冗余 re-exports
    base.py
    parser.py
    auth.py
    bootstrap.py
    health.py                        # 568行，含重复代码
    integration.py                   # ← 删除
    service.py                       # 含重复代码
    error_handler.py
    output.py
    utils.py                         # CLI 专用工具

# 目标
src/flowgate/
  __init__.py                        # 仅 main() 入口
  core/
    __init__.py                      # 导出核心公共 API
    config.py                        # 合并 config + PathResolver + validators
    constants.py
    process.py
    bootstrap.py                     # 下载/验证 + 共享 http_get_json
    cliproxyapiplus.py               # 合并4个文件为1个
    auth.py                          # 合并 oauth + auth_methods + headless_import
    health.py
    security.py
    observability.py
  cli/
    __init__.py                      # 仅 run_cli，无冗余 re-exports
    base.py
    parser.py                        # 删除 integration 子命令
    auth.py
    bootstrap.py
    health.py
    service.py
    error_handler.py
    output.py
    helpers.py                       # 合并 cli/utils + 重复的 helper 函数
```

---

## Phase 1: 删除不需要的功能（集成模块）

### Task 1.1: 删除集成模块源码

**Files:**
- Delete: `src/flowgate/integration.py`
- Delete: `src/flowgate/client_apply.py`
- Delete: `src/flowgate/cli/integration.py`

**Step 1: 删除源文件**

删除以下 3 个文件：
- `src/flowgate/integration.py`
- `src/flowgate/client_apply.py`
- `src/flowgate/cli/integration.py`

**Step 2: 从 cli/__init__.py 移除集成命令导入和路由**

在 `src/flowgate/cli/__init__.py` 中：
- 删除 `from .integration import IntegrationApplyCommand, IntegrationPrintCommand`
- 删除 run_cli 中 `args.command == "integration"` 的分支

**Step 3: 从 parser.py 移除集成子命令**

在 `src/flowgate/cli/parser.py` 中：
- 删除 integration 子命令的 argparse 定义（约 lines 53-66）

**Step 4: 删除集成相关测试**

- Delete: `tests/test_integration.py`
- Delete: `tests/test_client_apply.py`
- 检查 `tests/test_cli.py` 是否有 integration 相关测试用例，如有则删除

**Step 5: 运行测试验证**

Run: `uv run pytest tests/ -v`
Expected: 所有剩余测试通过

**Step 6: Commit**

```bash
git add -A && git commit -m "refactor(cli): remove integration module (print/apply)"
```

---

## Phase 2: 合并 cliproxyapiplus_* 模块

### Task 2.1: 创建合并后的 cliproxyapiplus.py

**Files:**
- Create: `src/flowgate/cliproxyapiplus.py`
- Delete: `src/flowgate/cliproxyapiplus_version.py`
- Delete: `src/flowgate/cliproxyapiplus_release.py`
- Delete: `src/flowgate/cliproxyapiplus_update_check.py`
- Delete: `src/flowgate/cliproxyapiplus_auto_update.py`

**Step 1: 创建合并模块**

创建 `src/flowgate/cliproxyapiplus.py`，按以下结构组织：

```python
"""CLIProxyAPIPlus version management, update checking, and auto-update."""

from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .constants import CLIPROXYAPI_PLUS_SERVICE

# ── Version helpers ──────────────────────────────────────────

def parse_version_tuple(version: str) -> tuple[int, ...] | None:
    """Parse 'v1.2.3' or '1.2.3' into (1, 2, 3)."""
    # 从 cliproxyapiplus_version.py 迁移，保持原逻辑

def is_newer_version(latest: str, current: str) -> bool:
    """Return True if latest > current."""
    # 从 cliproxyapiplus_version.py 迁移

def build_update_info(
    *, current_version: str, latest_version: str, release_url: str
) -> dict[str, str] | None:
    """Build update info dict if latest is newer."""
    # 从 cliproxyapiplus_version.py 迁移

# ── Release helpers ──────────────────────────────────────────

def build_latest_release_url(repo: str) -> str:
    # 从 cliproxyapiplus_release.py 迁移

def parse_latest_release_payload(payload: dict[str, Any]) -> tuple[str, str]:
    # 从 cliproxyapiplus_release.py 迁移

def fetch_latest_release(
    *, repo: str, http_get_json: Callable[[str], dict[str, Any]]
) -> tuple[str, str]:
    # 从 cliproxyapiplus_release.py 迁移

# ── HTTP helper (统一实现) ───────────────────────────────────

def http_get_json(url: str, *, timeout: int = 10) -> dict[str, Any]:
    """Shared HTTP GET JSON helper.
    
    Replaces duplicates in bootstrap.py and update_check.py.
    """
    # 统一两个 _http_get_json 实现
    # User-Agent: "flowgate"

# ── Installed version + cache ────────────────────────────────

_CHECK_CACHE_FILE = "cliproxyapiplus_update_cache.json"
_CACHE_TTL_SECONDS = 3600  # 1 hour

def read_installed_version(runtime_dir: str | Path, fallback_version: str) -> str:
    # 从 update_check.read_cliproxyapiplus_installed_version 迁移
    # 注意：重命名为更简短的名称

def write_installed_version(runtime_dir: str | Path, version: str) -> None:
    # 从 update_check.write_cliproxyapiplus_installed_version 迁移

def check_update(
    *, runtime_dir: str | Path, current_version: str, repo: str
) -> dict[str, str] | None:
    """Check for updates with caching."""
    # 从 update_check.check_cliproxyapiplus_update 迁移
    # 使用本模块的 http_get_json

# ── Auto-update orchestration ────────────────────────────────

def check_latest_version(current_version: str, repo: str) -> dict[str, str] | None:
    # 从 auto_update.check_latest_version 迁移
    # 使用本模块的 http_get_json

def perform_update(
    *, config: dict[str, Any], latest_version: str,
    repo: str, require_sha256: bool = False
) -> dict[str, Any]:
    # 从 auto_update.perform_update 迁移
    # 导入 bootstrap.download_cliproxyapi_plus (保持 bootstrap 独立)

# ── Backward-compatibility aliases ───────────────────────────
# 旧名称别名，允许渐进迁移后删除
read_cliproxyapiplus_installed_version = read_installed_version
write_cliproxyapiplus_installed_version = write_installed_version
check_cliproxyapiplus_update = check_update
```

**Step 2: 统一 _http_get_json**

将 `http_get_json` 定义在 `cliproxyapiplus.py` 中，同时更新 `bootstrap.py` 使其也使用此统一实现：

```python
# bootstrap.py 中
from .cliproxyapiplus import http_get_json
```

或者：将 `http_get_json` 放在 `bootstrap.py` 中（因为 bootstrap 是更底层的下载模块），然后 `cliproxyapiplus.py` 从 `bootstrap` 导入。

**推荐方案：** `http_get_json` 放在 `bootstrap.py`（它是底层下载工具），`cliproxyapiplus.py` 导入使用。这样 bootstrap 保持独立，不产生循环依赖。

**Step 3: 删除旧的 4 个文件**

- `src/flowgate/cliproxyapiplus_version.py`
- `src/flowgate/cliproxyapiplus_release.py`
- `src/flowgate/cliproxyapiplus_update_check.py`
- `src/flowgate/cliproxyapiplus_auto_update.py`

**Step 4: 更新所有导入引用**

以下文件需要更新 import 路径：

| 文件 | 旧导入 | 新导入 |
|------|--------|--------|
| `src/flowgate/cli/bootstrap.py` | `from ..cliproxyapiplus_auto_update import check_latest_version, perform_update` | `from ..cliproxyapiplus import check_latest_version, perform_update` |
| `src/flowgate/cli/bootstrap.py` | `from ..cliproxyapiplus_update_check import read_cliproxyapiplus_installed_version, write_cliproxyapiplus_installed_version` | `from ..cliproxyapiplus import read_installed_version, write_installed_version` |
| `src/flowgate/cli/health.py` | `from ..cliproxyapiplus_update_check import check_cliproxyapiplus_update, read_cliproxyapiplus_installed_version` | `from ..cliproxyapiplus import check_update, read_installed_version` |
| `src/flowgate/cli/service.py` | 同上 | 同上 |

**Step 5: 更新测试文件**

- `tests/test_cliproxyapiplus_version.py` → 更新导入为 `from flowgate.cliproxyapiplus import ...`
- `tests/test_cliproxyapiplus_release.py` → 同上
- `tests/test_cliproxyapiplus_auto_update.py` → 同上，更新 mock 路径

可选：将 3 个测试文件合并为 `tests/test_cliproxyapiplus.py`

**Step 6: 运行测试验证**

Run: `uv run pytest tests/ -v`
Expected: 所有测试通过

**Step 7: Commit**

```bash
git add -A && git commit -m "refactor: merge cliproxyapiplus_* modules into single cliproxyapiplus.py"
```

---

## Phase 3: 消除重复代码

### Task 3.1: 提取共享 CLI helpers

**Files:**
- Modify: `src/flowgate/cli/utils.py` → 重命名为 `src/flowgate/cli/helpers.py`
- Modify: `src/flowgate/cli/health.py`
- Modify: `src/flowgate/cli/service.py`
- Modify: `src/flowgate/cli/auth.py`

**Step 1: 将 _effective_secret_files 提取到 cli/helpers.py**

`_effective_secret_files` 在 `cli/auth.py` 和 `cli/health.py` 中完全重复（各 ~15 行）。重命名 `cli/utils.py` 为 `cli/helpers.py` 并将此函数移入：

```python
# src/flowgate/cli/helpers.py
def effective_secret_files(config: dict[str, Any]) -> list[str]:
    """Collect all secret files from config and auth directory."""
    from pathlib import Path
    paths: set[str] = set()
    for value in config.get("secret_files", []):
        if isinstance(value, str) and value.strip():
            paths.add(str(Path(value).resolve()))
    default_auth_dir = Path(default_auth_dir(config))
    if default_auth_dir.exists():
        for item in default_auth_dir.glob("*.json"):
            paths.add(str(item.resolve()))
    return sorted(paths)
```

然后在 `cli/auth.py` 和 `cli/health.py` 中删除各自的 `_effective_secret_files` 并改为：
```python
from .helpers import effective_secret_files
```

**Step 2: 将 _maybe_print_cliproxyapiplus_update 提取到 cli/helpers.py**

`_maybe_print_cliproxyapiplus_update` 在 `cli/service.py`（模块函数, ~51 行）和 `cli/health.py`（实例方法, ~49 行）中完全重复。提取为共享函数：

```python
# src/flowgate/cli/helpers.py
def maybe_print_update_notification(config: dict[str, Any], *, stdout: TextIO) -> None:
    """Print CLIProxyAPIPlus update notification if available (TTY only)."""
    from ..cliproxyapiplus import check_update, read_installed_version
    from ..bootstrap import DEFAULT_CLIPROXY_REPO, DEFAULT_CLIPROXY_VERSION
    
    isatty = getattr(stdout, "isatty", None)
    if callable(isatty) and not isatty():
        return
    runtime_dir = str(config.get("paths", {}).get("runtime_dir", "")).strip()
    if not runtime_dir:
        return
    current_version = read_installed_version(runtime_dir, DEFAULT_CLIPROXY_VERSION)
    update = check_update(
        runtime_dir=runtime_dir, current_version=current_version, repo=DEFAULT_CLIPROXY_REPO
    )
    if not update:
        return
    latest = update["latest_version"]
    release_url = update.get("release_url", "")
    config_path = str(config.get("_meta", {}).get("config_path", "config/flowgate.yaml"))
    print(f"cliproxyapi_plus:update_available current={current_version} latest={latest} "
          f"release={release_url if release_url else 'n/a'}", file=stdout)
    print(f"cliproxyapi_plus:update_suggestion command='uv run flowgate --config {config_path} "
          f"bootstrap update'", file=stdout)
```

在 `cli/service.py` 中删除 `_maybe_print_cliproxyapiplus_update` 函数，改为导入。
在 `cli/health.py` 中删除 `DoctorCommand._maybe_print_cliproxyapiplus_update` 方法，改为调用导入的共享函数。

**Step 3: 运行测试验证**

Run: `uv run pytest tests/ -v`
Expected: 所有测试通过

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor(cli): extract duplicated helpers (secret_files, update_notification)"
```

### Task 3.2: 清理 cli/__init__.py 的冗余 re-exports

**Files:**
- Modify: `src/flowgate/cli/__init__.py`
- Modify: `src/flowgate/cli/health.py`

**Step 1: 移除 cli/__init__.py 中未使用的顶层导入**

以下导入仅用于被 `cli/health.py` 通过 `from .. import cli as cli_module` 间接引用：
- `from ..health import check_http_health`
- `from ..process import ProcessSupervisor`
- `from ..security import check_secret_file_permissions`
- `from ..utils import _is_executable_file`

将这些导入从 `cli/__init__.py` 删除。

**Step 2: 更新 cli/health.py 直接导入**

将 `cli/health.py` 中的:
```python
from .. import cli as cli_module
# 然后使用 cli_module.ProcessSupervisor, cli_module.check_http_health
```
改为直接导入:
```python
from ..process import ProcessSupervisor
from ..health import check_http_health
```

**Step 3: 更新测试中的 mock 路径**

检查测试文件中是否有 mock `flowgate.cli.ProcessSupervisor` 或 `flowgate.cli.check_http_health` 的地方，更新为 mock `flowgate.cli.health.ProcessSupervisor` 等。

**Step 4: 运行测试验证**

Run: `uv run pytest tests/ -v`

**Step 5: Commit**

```bash
git add -A && git commit -m "refactor(cli): remove redundant re-exports from cli/__init__"
```

---

## Phase 4: 建立 core/ 子包结构

### Task 4.1: 创建 core/ 子包并迁移简单模块

**Files:**
- Create: `src/flowgate/core/__init__.py`
- Move: `constants.py` → `core/constants.py`
- Move: `process.py` → `core/process.py`
- Move: `health.py` → `core/health.py`
- Move: `security.py` → `core/security.py`
- Move: `observability.py` → `core/observability.py`
- Move: `bootstrap.py` → `core/bootstrap.py`
- Move: `cliproxyapiplus.py` → `core/cliproxyapiplus.py`

**Step 1: 创建 core/__init__.py**

```python
"""FlowGate core business logic."""

from __future__ import annotations

from .config import ConfigError, load_router_config
from .constants import CLIPROXYAPI_PLUS_SERVICE
from .process import ProcessError, ProcessSupervisor
```

**Step 2: 迁移无需合并的模块**

直接移动以下文件到 `core/`，更新内部的相对导入（`from .observability` 等保持不变，因为同在 core/ 下）：

- `constants.py` → `core/constants.py`（无修改）
- `process.py` → `core/process.py`（`from .observability` 不变）
- `health.py` → `core/health.py`（无内部导入，直接移动）
- `security.py` → `core/security.py`（无内部导入，直接移动）
- `observability.py` → `core/observability.py`（无内部导入，直接移动）
- `bootstrap.py` → `core/bootstrap.py`（内部导入不变）
- `cliproxyapiplus.py` → `core/cliproxyapiplus.py`（内部 `from .constants`、`from .bootstrap` 不变）

**Step 3: Commit（源码迁移，测试暂时会失败）**

```bash
git add -A && git commit -m "refactor: move simple modules into core/ sub-package"
```

### Task 4.2: 合并 config + PathResolver + validators → core/config.py

**Files:**
- Create: `src/flowgate/core/config.py`（基于原 config.py）
- Delete: `src/flowgate/config.py`
- Delete: `src/flowgate/config_utils/__init__.py`
- Delete: `src/flowgate/config_utils/path_resolver.py`
- Delete: `src/flowgate/validators.py`

**Step 1: 创建 core/config.py**

以原 `config.py` 为基础，将以下内容合并进来：
- `PathResolver` 类（来自 `config_utils/path_resolver.py`）
- `ConfigValidator` 类（来自 `validators.py`）

注意：
- 消除 `_resolve_path_relative_to_config` 与 `PathResolver.resolve` 的重复 — 统一为 `PathResolver.resolve`，在 resolve 中加入 `expanduser()` 调用
- `ConfigValidator` 内部导入 `ConfigError` 不再需要延迟导入（同一模块内）
- 用注释清晰分段：Config Loading / Path Resolution / Validation

**Step 2: 删除旧文件**

- `src/flowgate/config.py`
- `src/flowgate/config_utils/` (整个目录)
- `src/flowgate/validators.py`

**Step 3: Commit**

```bash
git add -A && git commit -m "refactor: merge config, PathResolver, validators into core/config.py"
```

### Task 4.3: 合并 oauth + auth_methods + headless_import → core/auth.py

**Files:**
- Create: `src/flowgate/core/auth.py`
- Delete: `src/flowgate/oauth.py`
- Delete: `src/flowgate/auth_methods.py`
- Delete: `src/flowgate/headless_import.py`

**Step 1: 创建 core/auth.py**

```python
"""Authentication: OAuth polling, headless import, provider registry."""

from __future__ import annotations
# ... imports ...

# ── OAuth helpers ────────────────────────────────────────────
def fetch_auth_url(auth_url_endpoint: str, timeout: float = 5.0) -> str: ...
def poll_auth_status(status_endpoint: str, timeout_seconds: int = 120, ...) -> str: ...

# ── Headless import ──────────────────────────────────────────
OUTPUT_FILENAME = "codex_headless_auth.json"
def import_codex_headless_auth(source: str | Path, dest_dir: str | Path) -> Path: ...

# ── Provider registry ────────────────────────────────────────
HeadlessImportHandler = Callable[[str, str], Path]
def headless_import_handlers() -> dict[str, HeadlessImportHandler]: ...
def get_headless_import_handler(provider: str) -> HeadlessImportHandler | None: ...
```

**Step 2: 删除旧文件**

- `src/flowgate/oauth.py`
- `src/flowgate/auth_methods.py`
- `src/flowgate/headless_import.py`

**Step 3: Commit**

```bash
git add -A && git commit -m "refactor: merge oauth, auth_methods, headless_import into core/auth.py"
```

### Task 4.4: 处理 utils.py 并删除

**Files:**
- Modify: `src/flowgate/core/bootstrap.py` — 接收 `_is_executable_file`
- Modify: `src/flowgate/core/process.py` — 接收 `_is_service_port_available`
- Delete: `src/flowgate/utils.py`

**Step 1: 移动函数到对应模块**

- `_is_executable_file(path)` → `core/bootstrap.py`（与二进制验证相关，重命名为 `is_executable_file`）
- `_is_service_port_available(host, port)` → `core/process.py`（与服务管理相关，重命名为 `is_port_available`）

**Step 2: 删除 utils.py**

**Step 3: Commit**

```bash
git add -A && git commit -m "refactor: distribute utils functions to relevant core modules"
```

### Task 4.5: 更新所有 CLI 导入路径

**Files:**
- Modify: `src/flowgate/cli/__init__.py`
- Modify: `src/flowgate/cli/auth.py`
- Modify: `src/flowgate/cli/bootstrap.py`
- Modify: `src/flowgate/cli/health.py`
- Modify: `src/flowgate/cli/service.py`
- Modify: `src/flowgate/cli/error_handler.py`
- Modify: `src/flowgate/cli/helpers.py`
- Modify: `src/flowgate/cli/parser.py`

**导入路径变更规则:**

| 旧导入 | 新导入 |
|--------|--------|
| `from ..config import ...` | `from ..core.config import ...` |
| `from ..constants import ...` | `from ..core.constants import ...` |
| `from ..process import ...` | `from ..core.process import ...` |
| `from ..bootstrap import ...` | `from ..core.bootstrap import ...` |
| `from ..cliproxyapiplus import ...` | `from ..core.cliproxyapiplus import ...` |
| `from ..health import ...` | `from ..core.health import ...` |
| `from ..security import ...` | `from ..core.security import ...` |
| `from ..observability import ...` | `from ..core.observability import ...` |
| `from ..oauth import ...` | `from ..core.auth import ...` |
| `from ..auth_methods import ...` | `from ..core.auth import ...` |
| `from ..utils import _is_executable_file` | `from ..core.bootstrap import is_executable_file` |
| `from ..utils import _is_service_port_available` | `from ..core.process import is_port_available` |

**Step 1: 逐文件更新所有 CLI 文件的导入**

**Step 2: 更新 src/flowgate/__init__.py**

```python
"""FlowGate - CLIProxyAPIPlus wrapper."""
import sys
from .cli import run_cli

def main() -> int:
    return run_cli(sys.argv[1:])
```

**Step 3: 运行测试（预期部分失败，测试路径尚未更新）**

Run: `uv run pytest tests/ -v`

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor(cli): update all CLI imports to use core/ sub-package"
```

### Task 4.6: 更新所有测试导入路径

**Files:**
- Modify: 所有 `tests/test_*.py` 文件
- Modify: `tests/fixtures/config_factory.py`

**导入路径变更规则（测试）:**

| 旧导入/mock路径 | 新导入/mock路径 |
|-----------------|----------------|
| `flowgate.config` | `flowgate.core.config` |
| `flowgate.process` | `flowgate.core.process` |
| `flowgate.bootstrap` | `flowgate.core.bootstrap` |
| `flowgate.cliproxyapiplus_*` | `flowgate.core.cliproxyapiplus` |
| `flowgate.oauth` | `flowgate.core.auth` |
| `flowgate.auth_methods` | `flowgate.core.auth` |
| `flowgate.headless_import` | `flowgate.core.auth` |
| `flowgate.health` | `flowgate.core.health` |
| `flowgate.security` | `flowgate.core.security` |
| `flowgate.observability` | `flowgate.core.observability` |
| `flowgate.validators` | `flowgate.core.config` |
| `flowgate.config_utils.*` | `flowgate.core.config` |
| `flowgate.utils._is_executable_file` | `flowgate.core.bootstrap.is_executable_file` |
| `flowgate.utils._is_service_port_available` | `flowgate.core.process.is_port_available` |

**需要更新的测试文件清单（约 30 个文件）:**

- `tests/test_config.py`
- `tests/test_config_v3.py`
- `tests/test_config_errors.py`
- `tests/test_path_resolver.py`（可合并入 test_config.py）
- `tests/test_validators.py`（可合并入 test_config.py）
- `tests/test_process.py`
- `tests/test_process_errors.py`
- `tests/test_bootstrap.py`
- `tests/test_cliproxyapiplus_version.py`
- `tests/test_cliproxyapiplus_release.py`
- `tests/test_cliproxyapiplus_auto_update.py`
- `tests/test_oauth.py`
- `tests/test_headless_import.py`
- `tests/test_health_enhanced.py`
- `tests/test_security.py`
- `tests/test_observability.py`
- `tests/test_cli.py`
- `tests/test_cli_regression_service.py`
- `tests/test_cli_regression_auth.py`
- `tests/test_cli_regression_misc.py`
- `tests/test_base_command.py`
- `tests/test_error_handler.py`
- `tests/test_auth_errors.py`
- `tests/test_defaults_sync.py`
- `tests/test_config_factory.py`
- `tests/test_precommit_config.py`
- `tests/test_yaml_dependency.py`
- `tests/test_docs_integration.py`
- `tests/test_dev_scripts.py`
- `tests/fixtures/config_factory.py`

**Step 1: 批量更新测试导入路径**

逐文件更新所有测试文件的 import 和 mock 路径。

关键注意：`@patch('flowgate.xxx.func')` 中的路径必须精确匹配**被 mock 的模块中实际导入该符号的路径**。例如，如果 `cli/health.py` 中写了 `from ..core.process import ProcessSupervisor`，那测试中 mock 应该是 `@patch('flowgate.cli.health.ProcessSupervisor')`。

**Step 2: 运行全量测试**

Run: `uv run pytest tests/ -v -m ""`
Expected: 所有测试通过

**Step 3: Commit**

```bash
git add -A && git commit -m "test: update all test imports for core/ sub-package structure"
```

---

## Phase 5: 清理和收尾

### Task 5.1: 删除冗余脚本和残留文件

**Files:**
- Delete: `scripts/cliproxy_auto_update.py`
- 验证并清理所有已删除模块的残留

**Step 1: 删除脚本**

删除 `scripts/cliproxy_auto_update.py`（功能已在 `flowgate bootstrap update` CLI 中）。

**Step 2: 检查 test_dev_scripts.py**

检查是否有针对此脚本的测试，如有则删除相关用例。

**Step 3: 最终检查残留导入**

```bash
grep -r "from flowgate.config_utils\|from flowgate.validators\|from flowgate.utils\b\|from flowgate.oauth\b\|from flowgate.auth_methods\|from flowgate.headless_import\|from flowgate.integration\|from flowgate.client_apply\|cliproxyapiplus_version\|cliproxyapiplus_release\|cliproxyapiplus_update_check\|cliproxyapiplus_auto_update" src/ tests/
```

Expected: 无匹配

**Step 4: Commit**

```bash
git add -A && git commit -m "chore: remove redundant scripts and verify clean imports"
```

### Task 5.2: 更新文档和配置

**Files:**
- Modify: `AGENTS.md` — 更新目录结构说明
- Modify: 文档中对 integration 和旧模块路径的引用

**Step 1: 更新 AGENTS.md**

更新 Directory Layout 部分以反映新的 core/ 结构。
删除对 integration 功能的引用。
更新 Key Components 中的路径引用。

**Step 2: 搜索并更新其他文档**

```bash
grep -r "integration\|client_apply\|config_utils\|cliproxyapiplus_" docs/
```

逐一更新匹配的文档。

**Step 3: Commit**

```bash
git add -A && git commit -m "docs: update documentation for core/ refactor"
```

### Task 5.3: 最终验证

**Step 1: 运行全量测试**

Run: `uv run pytest tests/ -v -m ""`
Expected: 全部通过

**Step 2: 运行 CLI 冒烟测试**

```bash
uv run flowgate --help
uv run flowgate --config config/flowgate.yaml status
uv run flowgate --config config/flowgate.yaml doctor
```

**Step 3: 运行安全检查**

Run: `./scripts/security_check.sh`

**Step 4: 清理 __pycache__**

```bash
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
```

---

## 风险和注意事项

1. **Mock 路径是最大的工作量** — Phase 4.6 中更新测试的 mock 路径需要非常仔细，每个 `@patch('flowgate.xxx.func')` 都需要更新。mock 路径必须匹配**被 mock 的模块中实际导入该符号的位置**。

2. **`from .. import cli as cli_module` 模式** — cli/health.py 使用此模式是为了方便测试 mock。Phase 3.2 中移除此模式后，需要确认所有相关测试的 mock 路径正确。

3. **向后兼容** — 如果有外部工具直接 `import flowgate.config` 等，会受影响。可在 `src/flowgate/__init__.py` 中添加兼容性 re-exports（如 `from .core.config import ConfigError`），但考虑到这是内部项目，建议直接迁移。

4. **合并大文件** — 合并 config + PathResolver + validators 会产生较大的 config.py（估计 ~400 行），需要用注释清晰分段。

5. **执行顺序** — Phase 1 → 2 → 3 → 4 → 5 必须按顺序执行，每个 Phase 结束后运行测试确认。每个 Phase 内的 Task 也按顺序执行。

6. **cliproxyapiplus.py 函数重命名** — `read_cliproxyapiplus_installed_version` → `read_installed_version` 等。提供了 backward-compat 别名以降低迁移风险，所有调用方更新后可删除别名。

## 预计影响

| 指标 | 当前 | 重构后 |
|------|------|--------|
| src/ Python 文件数 | 32 | ~18 |
| 源码总行数 | ~5036 | ~4200 (估) |
| 子包层级 | 3层 (config_utils/) | 2层 (core/, cli/) |
| 重复代码 | ~130 行 | ~0 行 |
| cliproxyapiplus 相关文件 | 4 个 | 1 个 |
| 认证相关文件 | 3 个 | 1 个 (core/auth.py) |
| 配置相关文件 | 4 个 | 1 个 (core/config.py) |
| 已删除功能 | - | integration (print/apply) |
