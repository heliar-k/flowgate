# LLM Router Current Plan and Implementation Status

**Date:** 2026-02-16  
**Goal:** 固化当前实现状态，并明确下一阶段可直接执行的任务。

## Current Architecture

- 本地双服务：`CLIProxyAPIPlus + LiteLLM`
- 控制入口：`llm-router` CLI（配置、策略切换、服务管理、OAuth）
- 运行产物：统一落在 `.router/`
- 技术栈：Python 3.12+, uv, unittest

## Completed Work (Done)

- 配置契约与迁移：`config_version`、旧字段兼容（`secrets`、`cliproxyapi`）
- 健康语义标准化：`liveness/readiness` 输出与失败判定统一
- 可观测性基线：`.router/runtime/events.log` JSONL 事件日志
- 故障排查 Runbook：`docs/runbook-troubleshooting.md`
- 环境自检命令：`doctor` 子命令 + `scripts/doctor.sh`
- 测试分层文档：README 中补齐 unit/integration/smoke 与验收基线
- 发布与回滚文档：`docs/release-and-rollback.md`
- 安全基线：`scripts/security_check.sh` + `.gitignore` 敏感规则

Latest verification:
- Command: `UV_CACHE_DIR=.uv-cache uv run python -m unittest discover -s tests -v`
- Result: `Ran 35 tests ... OK`

## Open Items (Next)

### Task A: Local Smoke Script (P1)

**Files:**
- Create: `scripts/smoke_local.sh`
- Modify: `README.md`

**Steps:**
1. 脚本化 `bootstrap -> profile set -> service start -> readiness check -> service stop`。
2. 增加超时等待、端口占用提示、失败时保留诊断信息。
3. README 增加“最小验证路径”。

### Task B: CI Baseline (P1)

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`

**Steps:**
1. 在 CI 中执行 `uv sync --group runtime --group test`。
2. 执行 `uv run python -m unittest discover -s tests -v`。
3. 加入轻量 CLI 可运行性检查（不依赖外部服务）。

### Task C: CLI Naming Consistency (P1)

**Files:**
- Modify: `src/llm_router/cli.py`
- Modify: `README.md` (if needed)

**Steps:**
1. 统一 CLI 帮助输出程序名与文档示例（`llm-router`）。
2. 验证 `--help` 与错误输出的一致性。
3. 回归测试确保无行为变化。

## Risks and Notes

- 历史 commit message 已重写，推送历史时需使用 `--force-with-lease`。
- 本地端口冲突（如 `4000`/`8317`）仍是联调常见风险。
- 认证文件必须保留在忽略目录并维持最小权限。
