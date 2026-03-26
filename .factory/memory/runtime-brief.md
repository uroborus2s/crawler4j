# 项目压缩运行卡

- 生成时间：2026-03-26（TASK-005 完成后刷新）
- 负责人：项目协调者
- 项目：crawler4j
- 当前阶段：IMPLEMENTATION
- 当前模式：Default
- 技术画像：自定义技术画像
- 技术栈：Python 3.12 + uv + PyQt6 + Playwright + SQLAlchemy + PyInstaller
- 活跃工作项：0
- 阻塞项：0
- 开放风险：1
- 最近发布包：无
- 最近交接包：无
- 最近快照：无
- 备注：默认质量门已通过；CR-003 已关闭，当前更适合进入真实站点 E2E 或发布收口

## AI 最小读取顺序

1. 先读本文件 `/.factory/memory/runtime-brief.md`
2. 再读 `/.factory/memory/role-charter.project.md`
3. 再读 `/.factory/project.json`
4. 再读 `/.factory/memory/motivation-state.md`、`/.factory/memory/autonomy-rules.md`、`/.factory/memory/evolution-baseline.md`
5. 再读当前阶段核心文档
6. 只有需要背景解释时，才读人类长文档

## 当前阶段核心文档

- `docs/01-discovery/input.md`
- `docs/01-discovery/current-state-analysis.md`
- `docs/04-delivery/task-breakdown.md`
- `docs/05-quality/quality-gates.md`

## 必守规则

- 不跳阶段。
- 代码类工作必须走 PR 闭环后再关单。
- 任何已接受变更都要同步代码、文档、测试、`.factory/memory/`。
- 遇到阻塞、空转或质量漂移时，优先执行 `factory-dispatch recovery`。
- 发现问题时优先做模式级修复，再把有效做法沉淀到 `evolution-baseline.md`。
- 实现前优先读取 `docs/03-solution/technical-selection.md`。
- 任务单位是人天，最小精度 0.5，但不是默认拆分步长。

## 当前推荐动作

- 继续保持 `uv run pytest -q`、`uv run ruff check .` 和 UI smoke 作为默认质量门
- 评估 `ctrip` 真实站点 E2E 回放与发布收口顺序
- 正式发布前按 `docs/06-release/version-governance.md` 执行切版与复验

## 当前关键工作项

- `TASK-012-mms-trust-gate-and-custom-ui-loading` TASK-012 补齐 MMS trust gate 与自定义页面加载 | 状态：DONE | 负责人：未知
- `TASK-011-mms-settings-store-and-module-state-persistence` TASK-011 建立 MMS settings store 与模块状态持久化 | 状态：DONE | 负责人：未知
- `TASK-010-optimize-module-developer-guide-for-external-authors` TASK-010 重做模块开发者指南 | 状态：DONE | 负责人：未知
