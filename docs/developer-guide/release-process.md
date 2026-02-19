# 发布与回滚指南（flowgate）

本文用于标准化 `flowgate` 的发布（打 tag）与紧急回滚流程，目标是“可照抄执行、并且每一步都有验收标准”。

## TL;DR

- 发布前：`uv sync` + `unittest` + `doctor` 全绿，`git status` 干净
- 发布：改 `pyproject.toml` 版本号 -> 写 release notes -> commit -> tag -> push
- 回滚：切回 last-good tag -> 恢复 config -> `bootstrap/profile/restart` -> `status/health` 验收

## 目录

- 1. 发布流程
- 2. 回滚流程
- 3. 发布 Checklist
- 4. 回滚 Checklist

## 1. 发布流程

### 1.1 发布前检查（必须）

```bash
uv sync --group runtime --group test
uv run python -m unittest discover -s tests -v
uv run flowgate --config config/flowgate.yaml doctor
git status
```

发布前必须满足：
- working tree 干净（`git status` 无未提交改动）
- 单测全绿
- 运行时预检 `doctor` 全绿

### 1.2 版本与变更说明

1. 修改 `pyproject.toml` 的 `project.version`。
2. 在 release notes 里总结：feature/fix/breaking/migration（如有）。
3. 如行为/CLI 输出/配置 schema 有变化，确认相关文档已同步更新（例如 `docs/` 与 `README.md`）。

### 1.3 提交、打 tag、推送

```bash
git add pyproject.toml README.md docs/
git commit -m "chore(release): prepare vX.Y.Z" -m "Why this change was needed:\n...\n\nWhat changed:\n...\n\nProblem solved:\n..."
git tag -a vX.Y.Z -m "flowgate vX.Y.Z"
git push origin main --follow-tags
```

## 2. 回滚流程

当新版本导致 auth/service/bootstrap 等关键流程不可用时，使用回滚。

### 2.1 选择 last known good tag

```bash
git tag --sort=-creatordate | head -n 10
git checkout v<last-good>
```

### 2.2 恢复 config 与运行时状态

- 恢复已验证过的 `config/flowgate.yaml` 与 `config/cliproxyapi.yaml`（以“可运行版本”的配置为准）
- 从该 revision 重新生成运行时产物并重启服务：

```bash
uv run flowgate --config config/flowgate.yaml bootstrap download
uv run flowgate --config config/flowgate.yaml profile set balanced
uv run flowgate --config config/flowgate.yaml service restart all
```

### 2.3 验收恢复

```bash
uv run flowgate --config config/flowgate.yaml status
uv run flowgate --config config/flowgate.yaml health
```

判定标准：
- services 报告 running
- `health` 返回 `liveness=ok` 且 `readiness=ok`

## 3. 发布 Checklist

- [ ] 单测通过（`uv run python -m unittest discover -s tests -v`）
- [ ] `doctor` 通过
- [ ] `pyproject.toml` 版本已更新
- [ ] 兼容性/迁移说明已记录（如有）
- [ ] tag 已创建并 push（含 `--follow-tags`）

## 4. 回滚 Checklist

- [ ] 已选定 last-good tag
- [ ] config 已恢复为可运行版本
- [ ] 运行时产物已从 last-good code 重新生成
- [ ] `status` 与 `health` 回到全绿
