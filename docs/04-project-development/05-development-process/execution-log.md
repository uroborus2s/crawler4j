# 执行记录

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** Tech Lead | 开发 | QA | 发布负责人
**上游输入：** `implementation-plan.md` | 当前任务结论 | 验证结果
**下游输出：** `docs/04-project-development/06-testing-verification/` | `docs/04-project-development/07-release-delivery/` | `.factory/memory/`
**关联 ID：** `TASK-014`, `TASK-015`, `TASK-016`, `TASK-017`, `TASK-018`, `TASK-019`, `TASK-020`
**最后更新：** 2026-04-15

## 1. 用途与记录规则

- 只记录已经开始执行或已经完成的正式事项。
- 每条记录至少说明输入、输出和当前状态。
- 这里记录“发生了什么”，不替代 `implementation-plan.md` 的任务规划职责。

## 2. Wave 11 文档治理整改执行记录

| 日期 | 条目 | 输入 | 输出 | 状态 |
|---|---|---|---|---|
| 2026-04-02 | `TASK-014` 根导航收口 | 文档规范审计、根导航覆盖检查 | `docs/index.md`、`docs/01-getting-started/document-map.md` | 已完成 |
| 2026-04-02 | `TASK-015` 角色入口重构 | 接手路径审计、四大模块边界 | `docs/02-user-guide/user-guide.md`、`docs/03-developer-guide/index.md`、`docs/04-project-development/08-operations-maintenance/core-maintainer-guide.md` | 已完成 |
| 2026-04-02 | `TASK-016` 过程文档补齐 | 空壳页清理清单 | `software-development-process.md`、`execution-log.md` | 已完成 |
| 2026-04-02 | `TASK-017` 发布文档补齐 | 最小文档包缺口 | `acceptance-checklist.md`、`delivery-package.md` | 已完成 |
| 2026-04-02 | `TASK-018` 运维与管理员文档补齐 | 运维职责边界、用户侧配置说明 | `operations-runbook.md`、`admin-guide.md` | 已完成 |
| 2026-04-02 | `TASK-019` 追踪与索引同步 | 文档索引缺口、接口矩阵缺口 | `interface-matrix.md`、`document-index.md`、`.factory/memory/doc-map.md` | 已完成 |
| 2026-04-02 | `TASK-020` 演进与结构验证收口 | 元数据问题清单、空壳页清理 | `skill-evolution-plan.md`、结构校验记录 | 已完成 |

## 3. 当前未决事项

| 事项 | 当前状态 | 下一步 |
|---|---|---|
| `ctrip` 真实站点 E2E | 未完成 | 回到实现/验证主线继续推进 |
| 根应用正式发布收口 | 未完成 | 在下一次正式发布前执行验收检查清单和交付包清单 |

## 4. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-02 | 新增正式执行记录页并登记 Wave 11 文档治理整改结果 | Codex |
| 2026-04-15 | 修复 VirtualBrowser 创建后 CDP 连接过早失败；补 REM post-create connect 语义与单测 | Codex |
| 2026-04-15 | 收敛 REM 手动创建环境边界；移除 post-create workflow 配置并改为创建后保持 RUNNING | Codex |
| 2026-04-15 | 收敛 REM 创建成功反馈；创建后仅刷新列表，不再弹成功提示框 | Codex |
| 2026-04-15 | 收敛 ATM 生命周期：删除 TaskScript/TaskFlow 私有 hooks，引入 `TaskSignal` 与 `WAITING_CONFIRMATION`，移除运行模板清理策略 UI | Codex |
| 2026-04-15 | 准备 SDK / Contracts `1.1.1` 发布口径；更新脚手架默认版本范围并固化 `on_cleanup` 终态规则 | Codex |
| 2026-04-15 | 按方案 A 落地 ATM 手动批次任务：新增 `BATCH + MANUAL` 的“执行一次”模式，并补任务创建页/列表页交互与回归测试 | Codex |

## 5. 2026-04-15 缺陷修复记录

| 日期 | 条目 | 输入 | 输出 | 状态 |
|---|---|---|---|---|
| 2026-04-15 | VirtualBrowser 创建后连接失败排查 | 用户复现截图、`crawler4j.log` 中 `env-20260415-3` 与多次 `connect_over_cdp` 400 记录 | `packages/crawler4j/src/core/rem/handle.py`、`packages/crawler4j/src/core/rem/manager.py`、对应 REM 单测 | 已完成 |
| 2026-04-15 | REM 手动创建环境边界收敛 | 用户确认 REM 只负责运行环境生命周期；手动创建成功后保持 `RUNNING` | `packages/crawler4j/src/core/rem/manager.py`、`packages/crawler4j/src/core/rem/ui/env_list_widget.py`、`packages/crawler4j/src/core/atm/execution_runner.py`、相关单测与文档/记忆 | 已完成 |
| 2026-04-15 | REM 创建成功反馈收敛 | 用户要求创建成功后不弹窗，只刷新运行环境列表 | `packages/crawler4j/src/core/rem/ui/env_list_widget.py`、对应 UI 单测、执行记录与 `.factory/memory/` 摘要 | 已完成 |
| 2026-04-15 | ATM hooks / 信号系统重构 | 用户要求统一为 ATM hooks，删除脚本/工作流私有 hooks，并用统一信号承接清理环境、等待人工确认等流程动作 | `packages/crawler4j-contracts/src/signal.py`、`packages/crawler4j-sdk/src/{base,workflow,assembler,context,signal}.py`、`packages/crawler4j/src/core/atm/{execution_runner,dispatcher,service,run_profile,ui/run_profile_dialog}.py`、相关单测与开发文档 | 已完成 |
| 2026-04-15 | ATM 手动批次模式落地 | 用户确认采用方案 A：不新增 JobType，而是在 `BATCH` 下增加 `MANUAL` 触发，UI 提供“执行一次”入口 | `packages/crawler4j/src/core/atm/{service.py,ui/task_create_dialog.py,ui/task_list_widget.py,ui/task_detail_dialog.py}`、`packages/crawler4j/tests/unit/test_core/test_atm/{test_job_modes.py,test_task_create_dialog.py,test_task_list_widget.py}`、用户/管理员说明与 `.factory/memory/` | 已完成 |

### 结论

- `env-20260415-3` 在 2026-04-15 14:15:06 至 14:15:09 已完成环境创建和窗口打开，但 `connect_over_cdp` 在约 1 秒内连续 3 次失败，工作流没有进入执行阶段。
- 2026-04-14 的成功日志显示同一路径下 `Opened browser -> Connected Playwright` 最长可超过 2 秒，因此原有重试预算不足，属于真实缺陷而非误操作。
- post-create 链路在 connect 失败后会自动关闭窗口，因此不应再弹出“浏览器窗口已打开”的保留态提示；该提示只保留给手动启动场景。
