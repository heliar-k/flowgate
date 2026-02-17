# LLM Router Current Plan and Implementation Status

**Date:** 2026-02-16  
**Goal:** 固化当前实现状态，并明确下一阶段可直接执行的任务。

## Current Architecture

- 本地双服务：`CLIProxyAPIPlus + LiteLLM`
- 控制入口：`flowgate` CLI（配置、策略切换、服务管理、OAuth）
- 认证入口：`auth list` / `auth login <provider>` / `auth import-headless <provider>`（兼容旧命令）
- 认证状态：`auth status` 提供 provider 能力、默认认证目录与权限问题摘要
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
- 认证可用性增强：新增 `auth list/login/import-headless` 通用命令，支持从配置动态读取 provider
- 认证安全补盲：`status/doctor` 将默认 `auths` 目录下的 JSON 认证文件纳入权限检查
- 认证配置契约升级：支持 `auth.providers`，并兼容旧 `oauth`
- 认证扩展结构优化：抽取 `auth_methods` 注册表，CLI 通过分发层调用认证导入方法
- OAuth 稳定性增强：轮询支持瞬时网络错误重试，失败提示增加修复建议

Latest verification:
- Command: `UV_CACHE_DIR=.uv-cache uv run python -m unittest discover -s tests -v`
- Result: `Ran 46 tests ... OK`
- Command: `UV_CACHE_DIR=.uv-cache uv run flowgate --help`
- Result: `usage: flowgate ...`

## Next Iteration Items (Completed)

### Task A: Local Smoke Script (P1) ✅

**Implemented:** `scripts/smoke_local.sh` + README 最小验证路径说明。

### Task B: CI Baseline (P1) ✅

**Implemented:** `.github/workflows/ci.yml` + README CI 覆盖范围说明。

### Task C: CLI Naming Consistency (P1) ✅

**Implemented:** `argparse prog` 从 `routerctl` 统一为 `flowgate`，并添加回归测试。

## Auth Scheme Review (Updated)

已识别并处理的缺口：
- `auth` 命令原先对 provider 写死（仅 codex/copilot），扩展新 provider 需要改代码。
- 认证操作发现性弱，用户需要记忆 provider-first 命令路径。
- 通过 headless 导入生成的新认证文件不在默认权限检查范围。
- 配置语义偏 `oauth`，对非 OAuth 认证方式表达能力不足。
- 缺少统一认证状态视图，排障需要多命令拼接。
- OAuth 轮询对瞬时网络异常容错不足。

仍需下一轮完成的缺口（建议）：
- 将 provider 级别的 `method` 元数据用于登录路径分发（目前主要用于声明与可观测）。
- 增加非 OAuth 认证方式（例如 API key import / static token file）的最小实现与回归测试。

执行计划：
- 见 `docs/plans/2026-02-16-auth-usability-and-extensibility-implementation-plan.md`

## Risks and Notes

- 历史 commit message 已重写，推送历史时需使用 `--force-with-lease`。
- 本地端口冲突（如 `4000`/`8317`）仍是联调常见风险。
- 认证文件必须保留在忽略目录并维持最小权限。
