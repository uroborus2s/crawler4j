# TASK-004 统一版本与发布事实源

- 状态：DONE
- 类型：TASK
- 优先级：P1
- 估算：1.0 人/天
- 关联 ID：`TASK-004`, `CR-001`, `REQ-004`, `NFR-002`

## 目标

- 明确根项目、运行时、Tag、SDK、Contracts 的版本治理规则
- 更新 release notes 与构建文档口径

## 验收标准

- 有单一版本规则文档
- 根项目版本与运行时版本关系清晰
- 发布说明不再让维护者误判当前版本

## 完成情况

- 已新增 `docs/06-release/version-governance.md`，明确根应用工作区版本、运行时镜像、最近正式 tag、SDK 与 Contracts 的治理规则
- 根 `pyproject.toml` 与 `src/__version__.py` 已统一到 `0.1.2.dev20260326`
- `release-notes.md` 已明确区分“当前工作区版本”与“最近正式发布 tag”
- 已补版本对齐测试，避免根版本与运行时镜像再次漂移
