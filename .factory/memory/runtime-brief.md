# 项目压缩运行卡

- 生成时间：2026-03-28 18:01:44
- 负责人：AI 软件工厂
- 项目：crawler4j
- 当前阶段：IMPLEMENTATION
- 当前模式：未知
- 技术画像：Crawler4j Model 项目画像
- 技术栈：python + crawler4j sdk cli + model/module project
- 活跃工作项：20
- 阻塞项：0
- 开放风险：0
- 最近发布包：无
- 最近交接包：无
- 最近快照：无
- 备注：refresh-after-clearing-pinned-version-command；已完成 docs 四大模块结构迁移并刷新 `docs/index.md` 与目录概览页；`docs/project-process/` 与 `docs/model-development/` 已退出正式入口；第三部分开发者指南各级概览页标题已统一为中文

## AI 最小读取顺序

1. 先读本文件 `/.factory/memory/runtime-brief.md`
2. 再读 `/.factory/memory/role-charter.project.md`
3. 再读 `/.factory/project.json`
4. 再读 `/.factory/memory/motivation-state.md`、`/.factory/memory/autonomy-rules.md`、`/.factory/memory/evolution-baseline.md`
5. 再读当前阶段核心文档
6. 只有需要背景解释时，才读人类长文档

## 当前阶段核心文档

- `docs/01-getting-started/document-map.md`
- `docs/03-developer-guide/index.md`
- `docs/04-project-development/08-operations-maintenance/core-maintainer-guide.md`
- `docs/04-project-development/05-development-process/implementation-plan.md`
- `docs/04-project-development/04-design/technical-selection.md`
- `docs/04-project-development/04-design/system-architecture.md`
- `docs/04-project-development/04-design/api-design.md`

## 必守规则

- 不跳阶段。
- 代码类工作必须走 PR 闭环后再关单。
- 任何已接受变更都要同步代码、文档、测试、`.factory/memory/`。
- 遇到阻塞、空转或质量漂移时，优先执行 `factory-dispatch recovery`。
- 发现问题时优先做模式级修复，再把有效做法沉淀到 `evolution-baseline.md`。
- 实现前优先读取 `docs/04-project-development/04-design/technical-selection.md`。
- 任务单位是人天，最小精度 0.5，但不是默认拆分步长。

## 当前推荐动作

- `python3 ../../AiProject/shanforge/scripts/factory-dispatch session --project "." --owner "AI 软件工厂"`
- `python3 ../../AiProject/shanforge/scripts/factory-dispatch board --project "." --owner "AI 软件工厂" --focus "当前协作焦点"`
- `python3 ../../AiProject/shanforge/scripts/factory-dispatch doctor --project "." --owner "AI 软件工厂" --scope full`

## 当前前 5 个活跃工作项

- `TASK-001-factory-baseline-bootstrap` TASK-001 历史项目工厂基线接管 | 状态：DONE | 负责人：未知
- `TASK-002-fix-root-entrypoint-and-packaging-smoke` TASK-002 修复根入口与打包 smoke | 状态：DONE | 负责人：未知
- `TASK-003-restore-ctrip-labor-workflow-runtime` TASK-003 恢复 `ctrip labor_workflow` 的当前运行时实现 | 状态：DONE | 负责人：未知
- `TASK-004-unify-version-and-release-source-of-truth` TASK-004 统一版本与发布事实源 | 状态：DONE | 负责人：未知
- `TASK-005-normalize-lint-and-docs-gates` TASK-005 收敛 lint 与 docs gate | 状态：DONE | 负责人：未知
