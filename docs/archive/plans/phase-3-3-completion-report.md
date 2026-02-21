# Phase 3.3 完成报告：添加集成测试套件

**完成日期**: 2026-02-19
**执行人**: Claude (Subagent-Driven Development)
**Git 提交**: `6ff7221`
**状态**: ✅ 已完成（待修改为 pytest marker）

---

## 任务概述

为 FlowGate 项目创建可选的集成测试套件，覆盖端到端的业务流程场景，使用模拟服务器避免外部依赖。

---

## 实现成果

### 新增目录结构

```
tests/integration/
├── __init__.py                      # Package 文档
├── base.py                          # 集成测试基类（含跳过机制）
├── test_service_lifecycle.py       # 22 个服务生命周期测试
├── test_oauth_flow.py               # 17 个 OAuth 流程测试
└── test_concurrent_operations.py   # 7 个并发操作测试

scripts/
└── integration_test.sh              # 集成测试运行脚本
```

### 测试统计

| 指标 | 数值 |
|------|------|
| 新增测试文件 | 5 个 |
| 新增集成测试 | 46 个 |
| 服务生命周期测试 | 22 个 |
| OAuth 流程测试 | 17 个 |
| 并发操作测试 | 7 个 |
| Mock 服务器类 | 1 个 (MockOAuthServer) |
| 测试代码行数 | ~1,160 行 |
| 脚本代码行数 | 32 行 |
| 总代码行数 | 1,236 行 |

### 测试覆盖场景

#### 1. 服务生命周期测试 (22 测试，6 测试类)

**TestServiceStart** (6 测试):
- ✅ 返回正数 PID
- ✅ is_running() 检查
- ✅ 重复启动返回现有 PID
- ✅ 事件日志记录 service_start
- ✅ 重复启动记录 already-running
- ✅ PID 文件创建

**TestServiceStop** (5 测试):
- ✅ 终止运行中的服务
- ✅ 事件日志记录 service_stop
- ✅ 停止不存在的服务（幂等）
- ✅ PID 文件删除
- ✅ 处理僵尸 PID

**TestServiceRestart** (3 测试):
- ✅ 停止后重启获得新 PID
- ✅ 事件日志记录 service_restart
- ✅ 重启从未启动的服务

**TestServiceLifecycleEndToEnd** (3 测试):
- ✅ 完整流程：启动 → 检查 → 停止
- ✅ 两个独立服务同时运行
- ✅ 事件日志完整性

**TestEventLogIntegrity** (2 测试):
- ✅ 有效的 JSON-lines 格式
- ✅ 不同服务的事件区分

**TestMultipleRestarts** (3 测试):
- ✅ 连续重启获得不同 PID
- ✅ 每次重启都记录事件
- ✅ PID 文件保持同步

#### 2. OAuth 流程测试 (17 测试，5 测试类)

使用自定义 `MockOAuthServer` 实现 HTTP 服务器和响应队列。

**TestFetchAuthUrl** (5 测试):
- ✅ 提取 `auth_url` 键
- ✅ 提取 `url` 键（备选）
- ✅ 提取 `login_url` 键（备选）
- ✅ 缺少 URL 抛出 ValueError
- ✅ 连接错误处理

**TestPollAuthStatusSuccess** (4 测试):
- ✅ 立即成功状态
- ✅ 轮询通过 pending 状态
- ✅ 接受 `completed` 状态
- ✅ 接受 `authorized` 状态

**TestPollAuthStatusFailure** (4 测试):
- ✅ `failed` 状态抛出 RuntimeError
- ✅ `denied` 状态抛出 RuntimeError
- ✅ 重复 pending 后超时
- ✅ 网络错误重试直到超时

**TestPollAuthStatusTimeout** (2 测试):
- ✅ 长时间 pending 超时
- ✅ 间歇性网络错误超时

**TestOAuthFlowEndToEnd** (2 测试):
- ✅ 完整流程：获取 URL → 轮询 → 成功
- ✅ 用户拒绝流程

#### 3. 并发操作测试 (7 测试，4 测试类)

测试承认线程安全限制（共享 `.tmp` 文件的原子写入竞态）。

**TestConcurrentProfileSwitch** (3 测试):
- ✅ 隔离目录：所有切换成功
- ✅ 顺序切换：总是成功
- ✅ 并发切换到共享目录：最终状态有效

**TestConcurrentHealthChecks** (2 测试):
- ✅ 并行 `is_running()` 检查
- ✅ 并发事件写入产生有效日志

**TestProfileSwitchAndRestart** (1 测试):
- ✅ Profile 切换（无运行服务）

**TestConcurrentServiceManagement** (1 测试):
- ✅ 不同服务的并行启动/停止

---

## 技术实现

### 1. 环境变量跳过机制

**文件**: `tests/integration/base.py`

```python
class IntegrationTestBase(unittest.TestCase):
    """集成测试基类"""

    @classmethod
    def setUpClass(cls):
        """检查集成测试环境"""
        if os.environ.get("RUN_INTEGRATION_TESTS") != "1":
            raise unittest.SkipTest("Integration tests require RUN_INTEGRATION_TESTS=1")
```

**执行模式**:

1. **CI 模式（默认 - 跳过集成测试）**:
```bash
uv run python -m unittest discover -s tests -v
# 输出: Ran 351 tests in 6.3s OK (skipped=13)
```

2. **完整套件（启用集成测试）**:
```bash
RUN_INTEGRATION_TESTS=1 uv run python -m unittest discover -s tests -v
# 输出: Ran 397 tests in 15.7s OK
```

3. **仅集成测试**:
```bash
./scripts/integration_test.sh
# 输出: 显示 46 个集成测试 + 摘要
```

### 2. Mock OAuth 服务器

**特性**:
- 基于 `http.server.HTTPServer` 和 `BaseHTTPRequestHandler`
- 使用响应队列模拟不同的服务器响应
- 支持上下文管理器（`with` 语句）
- 动态分配端口避免冲突

```python
class MockOAuthServer:
    """HTTP 服务器，带响应队列用于 OAuth 端点模拟"""

    def __init__(self):
        self.response_queue = queue.Queue()
        self.server = None
        self.thread = None

    def enqueue(self, status_code: int, body: dict[str, Any]):
        """为下一个请求排队响应"""
        self.response_queue.put((status_code, body))

    def start(self) -> str:
        """启动服务器，返回基础 URL"""
        # 实现细节...

    def stop(self):
        """停止服务器"""
        # 实现细节...
```

### 3. Mock 服务进程

**策略**: 使用 Python 自身作为模拟服务，不依赖真实的 LiteLLM 或 CLIProxyAPIPlus：

```python
config["services"]["litellm"]["command"] = {
    "args": ["python", "-c", "import time; time.sleep(120)"]
}
```

**优势**:
- 无需真实服务二进制文件
- 完全隔离，可控
- 快速启动和停止

### 4. 测试隔离机制

每个测试类使用：

```python
def setUp(self):
    """创建临时目录和独立配置"""
    self.temp_dir = tempfile.mkdtemp()
    self.addCleanup(shutil.rmtree, self.temp_dir)

    # 创建隔离的配置
    self.config = ConfigFactory.minimal()
    self.config["paths"]["runtime_dir"] = os.path.join(self.temp_dir, "runtime")
    # ...
```

**清理机制**:
- 使用 `self.addCleanup()` 确保资源清理
- tearDown 中停止所有启动的进程
- 删除临时目录

### 5. 线程安全测试

**设计**:
- 使用 `threading.Thread` 和 `concurrent.futures.ThreadPoolExecutor`
- 测试承认 `_atomic_write()` 在共享目录下的竞态条件
- 隔离目录测试验证真正的并发性
- 共享目录测试验证最终状态一致性

**示例**:
```python
def test_concurrent_profile_switches_isolated_directories(self):
    """并发 profile 切换（隔离目录）- 全部成功"""
    threads = []
    results = {}

    for profile_name in ["reliability", "balanced", "cost"]:
        t = threading.Thread(target=self._switch_profile_isolated, args=(profile_name, results))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 验证所有切换都成功
    self.assertEqual(len(results), 3)
    for profile, success in results.items():
        self.assertTrue(success, f"Profile {profile} failed")
```

---

## 验证结果

### 测试执行

#### 模式 1: 默认（跳过集成测试）

```bash
$ uv run python -m unittest discover -s tests -v
...
----------------------------------------------------------------------
Ran 351 tests in 6.309s

OK (skipped=13)
```

#### 模式 2: 完整套件

```bash
$ RUN_INTEGRATION_TESTS=1 uv run python -m unittest discover -s tests -v
...
----------------------------------------------------------------------
Ran 397 tests in 15.742s

OK
```

#### 模式 3: 仅集成测试

```bash
$ ./scripts/integration_test.sh
Running integration tests...
Config: config/flowgate.yaml

test_consecutive_restarts ... ok
test_event_log_for_each_restart ... ok
...
----------------------------------------------------------------------
Ran 46 tests in 9.215s

OK
```

### Git 变更统计

```bash
$ git diff --stat main
 tests/integration/__init__.py                  |  10 +
 tests/integration/base.py                      | 135 ++++++
 tests/integration/test_service_lifecycle.py    | 319 ++++++++++++++
 tests/integration/test_oauth_flow.py           | 374 +++++++++++++++++
 tests/integration/test_concurrent_operations.py| 366 ++++++++++++++++
 scripts/integration_test.sh                    |  32 ++
 6 files changed, 1236 insertions(+)
```

### 提交信息

```
commit 6ff7221
test(phase-3): add integration test suite with mock services

Add comprehensive integration test suite for end-to-end testing,
using mock services and OAuth servers to avoid external dependencies.

Why this change was needed:
- CI excluded OAuth flow tests
- Missing end-to-end service lifecycle tests
- No concurrent operation testing
- Need optional integration tests (default skip in CI)

What changed:
- Created tests/integration/ package with 46 test cases
  * test_service_lifecycle.py (22 tests)
  * test_oauth_flow.py (17 tests)
  * test_concurrent_operations.py (7 tests)

- Mock services replace real LiteLLM/CLIProxyAPIPlus
  * Use python -c "import time; time.sleep(120)" as mock service
  * No binary dependencies needed
  * Full isolation in temporary directories

- Mock OAuth server using http.server
  * Response queue for flexible test scenarios
  * Dynamic port allocation
  * Context manager support

- Integration test runner script
  * scripts/integration_test.sh
  * Environment variable control: RUN_INTEGRATION_TESTS=1

- Thread safety testing
  * Acknowledges _atomic_write() races on shared .tmp files
  * Isolated directory tests verify true concurrency
  * Shared directory tests verify final-state consistency

Problem solved:
- Full coverage: service lifecycle, OAuth flows, concurrent operations
- Tests skip by default (CI sees 351 tests)
- Enabled with RUN_INTEGRATION_TESTS=1 (total 397 tests)
- No external dependencies (mock services)
- Complete test isolation (temporary directories)
- All 397 tests passing when integration tests enabled
```

---

## 目标达成情况

### 原计划目标

| 目标 | 预期 | 实际 | 状态 |
|------|------|------|------|
| 集成测试目录 | 1 个 | 1 个 | ✅ |
| 集成测试文件 | 3-4 个 | 5 个 | ✅ |
| 集成测试用例 | 20-30 个 | 46 个 | ✅ 超额 |
| 运行脚本 | 1 个 | 1 个 | ✅ |
| CI 默认跳过 | 是 | 是 | ✅ |
| 无外部依赖 | 是 | 是 | ✅ |

### 测试场景覆盖

| 场景 | 计划 | 实际 | 状态 |
|------|------|------|------|
| 服务启动/停止流程 | ✅ | 22 测试 | ✅ |
| OAuth 登录流程 | ✅ | 17 测试 | ✅ |
| 并发操作 | ✅ | 7 测试 | ✅ |
| Profile 切换 | 已存在 | 扩展 | ✅ |

---

## 重要设计决策

### 1. 相对导入

测试使用 `from .base import IntegrationTestBase`，要求从项目根目录运行，以 `tests/` 作为发现起始目录。

**理由**: 保持包结构清晰，支持集成测试作为独立模块。

### 2. 线程安全现实

测试承认 `profile.activate_profile()` 使用确定性的 `.tmp` 文件路径，不是线程安全的。并发测试验证：
- 隔离目录 → 所有操作成功
- 共享目录 → 最终状态有效

**理由**: 真实反映代码现状，为未来改进提供基线。

### 3. 无网络依赖

Mock OAuth 服务器运行在 localhost，使用动态分配的端口（无端口冲突）。

**理由**: 完全隔离，可控，快速，无需网络访问。

### 4. 进程清理

所有集成测试在 tearDown() 中清理衍生的进程，避免孤儿进程。

**理由**: 确保测试环境干净，不留残余。

---

## 经验总结

### 成功因素

1. **Mock 服务器设计**:
   - 使用响应队列灵活模拟各种场景
   - 上下文管理器简化资源管理
   - 动态端口避免冲突

2. **测试隔离**:
   - 每个测试使用临时目录
   - 完整的 setUp/tearDown 清理
   - 无状态泄露

3. **CI 友好**:
   - 默认跳过集成测试
   - 环境变量控制简单明了
   - 无外部依赖

4. **线程安全测试**:
   - 承认代码限制
   - 验证实际行为
   - 为未来改进提供基线

### 可改进之处

1. **环境变量 vs pytest marker**:
   - 当前使用环境变量 `RUN_INTEGRATION_TESTS=1`
   - 可以改为 pytest marker（如 `@pytest.mark.integration`）
   - **用户已要求修改为 pytest marker**

2. **并发测试深度**:
   - 当前测试较基础
   - 可以增加更多复杂并发场景
   - 如：多服务同时重启、Profile 切换与服务操作交错

3. **Mock 服务器功能**:
   - 可以添加更多 OAuth 场景
   - 如：token 刷新、revoke 等

---

## 后续建议

### 立即修改（用户要求）

**将环境变量机制改为 pytest marker**:

```python
# 修改前
@classmethod
def setUpClass(cls):
    if os.environ.get("RUN_INTEGRATION_TESTS") != "1":
        raise unittest.SkipTest(...)

# 修改后
import pytest

@pytest.mark.integration
class TestServiceLifecycle(unittest.TestCase):
    ...
```

**运行方式**:
```bash
# 仅单元测试
uv run pytest tests/ -m "not integration"

# 包含集成测试
uv run pytest tests/ -m "integration"

# 所有测试
uv run pytest tests/
```

### 持续改进

1. **增加更多集成场景**:
   - 认证 token 过期和刷新
   - 配置热重载
   - 多实例管理

2. **性能测试**:
   - 测量服务启动时间
   - Profile 切换耗时
   - 并发性能

3. **故障注入测试**:
   - 磁盘空间不足
   - 网络间歇性故障
   - 进程崩溃恢复

---

## 待办事项（用户要求）

### 🔄 修改为 pytest marker

需要修改以下文件：

1. **tests/integration/base.py**:
   - 移除环境变量检查
   - 添加 `@pytest.mark.integration` 装饰器

2. **所有集成测试类**:
   - 添加 `@pytest.mark.integration` 装饰器

3. **pyproject.toml**:
   - 注册 `integration` marker

4. **scripts/integration_test.sh**:
   - 修改为使用 pytest marker

5. **文档更新**:
   - 更新 CLAUDE.md
   - 更新优化计划

---

## 附录

### 相关文件

- 优化计划：`docs/plans/2026-02-18-optimization-plan.md`
- Git 提交：`6ff7221`
- Git 标签：`phase-3-3-complete`（建议创建）

### 测试文件清单

- `tests/integration/__init__.py` (10 行)
- `tests/integration/base.py` (135 行)
- `tests/integration/test_service_lifecycle.py` (319 行)
- `tests/integration/test_oauth_flow.py` (374 行)
- `tests/integration/test_concurrent_operations.py` (366 行)
- `scripts/integration_test.sh` (32 行)

### MockOAuthServer API

```python
class MockOAuthServer:
    def __init__(self)
    def enqueue(status_code: int, body: dict[str, Any])
    def start() -> str  # Returns base URL
    def stop()
    def __enter__() -> MockOAuthServer
    def __exit__(exc_type, exc_val, exc_tb)
```

---

**报告生成日期**: 2026-02-19
**报告版本**: 1.0
**状态**: ✅ 已完成（待修改为 pytest marker）
