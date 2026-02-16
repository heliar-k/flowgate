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

## 风险与注意事项

- 历史 commit message 已重写，本地 hash 与旧远端历史不兼容；推送需 `--force-with-lease`。  
- 本地端口冲突（如 `8317`）会影响联调，建议使用可配置备用端口。  
- 认证文件属于敏感信息，仅保留在忽略目录并维持最小权限。
