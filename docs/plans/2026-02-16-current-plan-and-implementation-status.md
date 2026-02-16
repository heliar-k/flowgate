# LLM Router Current Plan and Status Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 固化当前项目实现状态，并给出下一阶段可直接执行的迭代计划。  

**Architecture:** 当前系统采用 `CLIProxyAPIPlus + LiteLLM` 的本地双服务架构，`llm-router` 负责配置解析、策略切换、服务控制与认证流程编排。运行产物统一落在 `.router/`，模板配置保留在 `config/examples/`，通过 CLI 完成 bootstrap、profile、auth 与 service 生命周期管理。  

**Tech Stack:** Python 3.12+, uv, unittest, CLIProxyAPIPlus, LiteLLM

---

## 当前实现状态（截至 2026-02-16）

- 核心能力已落地：配置校验、进程监管、健康检查、OAuth 轮询、headless auth 导入。
- CLI 已覆盖：`profile`、`status`、`health`、`auth codex|copilot`、`service`、`bootstrap`。
- 运行目录已统一：默认使用 `.router/`（runtime/bin/pids/logs/auths）。
- LiteLLM 依赖改为项目管理：`pyproject.toml` 中维护 `runtime` 依赖组（`litellm[proxy]==1.75.8`）。
- `bootstrap download` 已移除 `--litellm-version` 参数，行为与依赖策略一致。
- 提交规范已统一：commit message 使用 `type(scope): ...` + `Why/What/Problem` 三段正文。
- 最新验证：  
  - 命令：`UV_CACHE_DIR=.uv-cache uv run python -m unittest discover -s tests -v`  
  - 结果：`Ran 28 tests ... OK`

## P0/P1 执行进度（更新于 2026-02-16）

- [x] Task 4（P0）配置契约与迁移策略：已增加 `config_version`（默认 v2）与兼容迁移（`secrets`/`cliproxyapi`）。
- [x] Task 5（P0）健康语义标准化：已区分 `liveness`（进程）与 `readiness`（HTTP 2xx）并统一 CLI 输出字段。
- [x] Task 6（P0）可观测性基线：已落地 `.router/runtime/events.log` JSONL 事件日志。
- [x] Task 7（P1）故障排查 Runbook：已新增 `docs/runbook-troubleshooting.md` 并接入 README。
- [x] Task 8（P1）统一环境自检命令：已新增 `doctor` 子命令与 `scripts/doctor.sh`。
- [x] Task 9（P1）测试分层与覆盖目标：已在 README 明确测试分层、命令与验收基线。

## 当前计划（下一阶段）

### Task 1: 健康检查语义统一

**Files:**
- Modify: `config/examples/routertool.yaml`
- Modify: `README.md`
- Test: `tests/test_cli.py`

**Steps:**
1. 确认 `cliproxyapi_plus.health_path` 的可用端点（当前 `/healthz` 与实际行为不一致）。  
2. 更新示例配置与文档。  
3. 补充/调整健康检查测试并全量回归。

### Task 2: 端到端冒烟脚本化

**Files:**
- Create: `scripts/smoke_local.sh`
- Modify: `README.md`

**Steps:**
1. 脚本化 `bootstrap -> profile set -> service start -> /v1/models 检查 -> stop`。  
2. 增加超时与端口占用提示。  
3. README 增加“最小验证路径”。

### Task 3: CI 基线（可选）

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`

**Steps:**
1. 添加 `uv sync --group runtime --group test` 与 `unittest` 执行。  
2. 仅校验单测与静态命令可运行性，不引入外部服务依赖。  
3. 在 README 标注 CI 覆盖范围与限制。

## 建议新增任务（补充）

### Task 4: 配置契约与迁移策略（P0）

**Goal:** 为配置演进建立兼容机制，避免字段变更导致运行中断。  

**Files:**
- Modify: `src/llm_router/config.py`
- Modify: `config/examples/routertool.yaml`
- Modify: `README.md`

**Steps:**
1. 增加 `config_version` 字段校验与默认策略。  
2. 增加最小迁移逻辑（例如字段重命名兼容层）。  
3. 在 README 增加“配置升级说明”。

### Task 5: 健康检查语义标准化（P0）

**Goal:** 统一 `liveness/readiness` 语义与失败处理。  

**Files:**
- Modify: `src/llm_router/health.py`
- Modify: `src/llm_router/cli.py`
- Modify: `config/examples/routertool.yaml`
- Test: `tests/test_cli.py`

**Steps:**
1. 明确定义并实现健康检查策略（服务存活 vs 服务可用）。  
2. 统一 CLI `health` 输出字段和非 200 场景判定。  
3. 覆盖关键分支测试并更新示例配置。

### Task 6: 可观测性基线（P0）

**Goal:** 提供可追踪的运行日志最小集合。  

**Files:**
- Modify: `src/llm_router/process.py`
- Modify: `src/llm_router/cli.py`
- Modify: `README.md`

**Steps:**
1. 增加统一日志字段（service/profile/provider/result）。  
2. 记录关键事件（启动、重启、失败原因）。  
3. 在 README 增加日志排查指引。

### Task 7: 故障排查 Runbook（P1）

**Goal:** 将常见故障处理流程文档化。  

**Files:**
- Create: `docs/runbook-troubleshooting.md`
- Modify: `README.md`

**Steps:**
1. 整理常见场景（端口冲突、OAuth 失败、权限错误、依赖缺失）。  
2. 给出可直接执行的诊断命令与预期现象。  
3. 在 README 添加入口链接。

### Task 8: 统一环境自检命令（P1）

**Goal:** 一条命令完成运行前检查。  

**Files:**
- Create: `scripts/doctor.sh`
- Modify: `README.md`
- Test: `tests/test_cli.py`

**Steps:**
1. 检查配置文件、运行目录、二进制、权限与依赖组。  
2. 输出明确的 pass/fail 与修复建议。  
3. 在 README 增加使用说明。

### Task 9: 测试分层与覆盖目标（P1）

**Goal:** 明确单元/集成/冒烟边界与最低覆盖要求。  

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/2026-02-16-current-plan-and-implementation-status.md`

**Steps:**
1. 定义测试分层及对应命令。  
2. 标注关键路径必须覆盖项（bootstrap/profile/auth/service）。  
3. 作为 PR 验收基线写入文档。

### Task 10: 发布与回滚流程（P2）

**Goal:** 标准化版本发布与异常回退。  

**Files:**
- Create: `docs/release-and-rollback.md`
- Modify: `README.md`

**Steps:**
1. 定义发布流程（版本号、tag、变更说明）。  
2. 定义回滚流程（配置回滚、runtime 回滚、历史注意事项）。  
3. 增加执行 checklist。

### Task 11: 安全基线补充（P2）

**Goal:** 降低凭证泄露与权限配置风险。  

**Files:**
- Modify: `.gitignore`
- Create: `scripts/security_check.sh`
- Modify: `README.md`

**Steps:**
1. 增加敏感文件与权限检查脚本。  
2. 强化文档中的密钥与 auth 文件管理要求。  
3. 将安全检查纳入日常执行建议（本地或 CI）。

## 风险与注意事项

- 历史 commit message 已重写，本地 hash 与旧远端历史不兼容；推送需 `--force-with-lease`。  
- 本地端口冲突（如 `8317`）会影响联调，建议使用可配置备用端口。  
- 认证文件属于敏感信息，仅保留在忽略目录并维持最小权限。
