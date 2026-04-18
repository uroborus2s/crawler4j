# 执行记录

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** Tech Lead | 开发 | QA | 发布负责人
**上游输入：** `implementation-plan.md` | 当前任务结论 | 验证结果
**下游输出：** `docs/04-project-development/06-testing-verification/` | `docs/04-project-development/07-release-delivery/` | `.factory/memory/`
**关联 ID：** `TASK-014`, `TASK-015`, `TASK-016`, `TASK-017`, `TASK-018`, `TASK-019`, `TASK-020`, `TASK-021`, `TASK-022`, `CR-004`, `CR-005`, `CR-008`, `BUG-013`
**最后更新：** 2026-04-18

## 1. 用途与记录规则

- 只记录已经开始执行或已经完成的正式事项。
- 每条记录至少说明输入、输出和当前状态。
- 这里记录“发生了什么”，不替代 `implementation-plan.md` 的任务规划职责。

## 2. Wave 11 文档治理整改执行记录

| 日期 | 条目 | 输入 | 输出 | 状态 |
|---|---|---|---|---|
| 2026-04-02 | `TASK-014` 根导航收口 | 文档规范审计、根导航覆盖检查 | `docs/index.md`、`docs/01-getting-started/index.md` | 已完成 |
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
| 2026-04-18 | 完成 `TASK-022` / `CR-008`：为模块新增 `module_audit_events`、`db.append_event`、`db.query_events`，并把快照数据与审计事件契约同步到正式文档、测试计划与 `.factory/memory/` | Codex |
| 2026-04-02 | 新增正式执行记录页并登记 Wave 11 文档治理整改结果 | Codex |
| 2026-04-15 | 修复 VirtualBrowser 创建后 CDP 连接过早失败；补 REM post-create connect 语义与单测 | Codex |
| 2026-04-15 | 收敛 REM 手动创建环境边界；移除 post-create workflow 配置并改为创建后保持 RUNNING | Codex |
| 2026-04-15 | 收敛 REM 创建成功反馈；创建后仅刷新列表，不再弹成功提示框 | Codex |
| 2026-04-15 | 收敛 ATM 生命周期：删除 TaskScript/TaskFlow 私有 hooks，引入 `TaskSignal` 与 `WAITING_CONFIRMATION`，移除运行模板清理策略 UI | Codex |
| 2026-04-17 | 完成 SDK / Contracts `1.2.0` 版本收口；同步 `__version__`、依赖基线、脚手架默认版本范围与开发者文档口径 | Codex |
| 2026-04-15 | 按方案 A 落地 ATM 手动批次任务：新增 `BATCH + MANUAL` 的“执行一次”模式，并补任务创建页/列表页交互与回归测试 | Codex |
| 2026-04-15 | 按方案 A 收敛运行模板资源配置：拆成“创建环境 / 选择环境”，并让 provider / 匹配规则真正进入 REM 选环境链路 | Codex |
| 2026-04-15 | 继续收敛运行模板创建环境页：将执行脚本选择并入基础信息区，按 VirtualBrowser 现有交互重做指纹参数表单，补官方 `addBrowser` 指纹参数透传与 IP 池绑定策略下发，并移除 `retry`；随后补齐浏览器版本下拉、默认 `145`、内核自动匹配，以及 UA 的默认 / 自定义 / 随机交互 | Codex |
| 2026-04-15 | 继续收敛 VirtualBrowser 指纹配置交互：将 `Canvas` / `WebGL 图像` / `WebGL 元数据` / `WebGPU` / `AudioContext` / `ClientRects` / `Speech Voices` 改为按钮式模式切换，并补 `WebGL 厂商` / `渲染` 的选项式输入与 UI 单测 | Codex |
| 2026-04-15 | 修复 VirtualBrowser 长文本下拉框宽度：`WebGL 厂商` / `渲染` 现在会按内容自动扩宽控件本身和弹出列表，并补 UI 单测 | Codex |
| 2026-04-15 | 调整运行模板弹窗宽度：默认宽度从屏幕的 `50%` 提升到 `60%`，即比原来增大 `20%`，并补 UI 单测锁定尺寸口径 | Codex |
| 2026-04-15 | 修复 `Do Not Track` / `硬件加速` 开关 UI：替换成自绘滑动开关，修正深色主题下的滑块缺失问题，并补交互单测 | Codex |
| 2026-04-16 | 修复任务创建页“运行配置”更新按钮被压缩的问题：改为按文案计算最小宽度并左对齐放置，避免“重新编辑运行模板”被挤压，并补 UI 单测 | Codex |
| 2026-04-15 | 微调 VirtualBrowser 创建默认值：新建创建环境时默认开启“创建后随机化指纹”，UA 默认回填为自定义随机值，并加高 UA 编辑框以完整显示内容 | Codex |
| 2026-04-15 | 继续对齐截图交互：将 `设备名称` / `MAC地址` / `SSL` / `端口扫描保护` / `启动参数` 改成分段按钮，将 `Do Not Track` / `硬件加速` 改成开关，并把新建默认值收敛到 `AudioContext` / `ClientRects` / `Speech Voices=随机`、`内存=8GB`、设备名与 MAC 默认自定义随机值 | Codex |
| 2026-04-15 | 修复运行模板执行脚本下拉：界面优先展示工作流 `display_name`，保存与运行仍保持 `workflow.name` 契约，并补 UI 单测 | Codex |
| 2026-04-15 | 修复运行模板执行脚本模块下拉空白项：移除空默认选项，改为 placeholder 未选中态，并补 UI 单测 | Codex |
| 2026-04-16 | 调整应用启动默认宽度与任务监控操作列：主窗口默认宽度改为 `1420px`，任务监控“操作”列放宽到 `240px`，避免按钮文案被截断，并补 UI 单测 | Codex |
| 2026-04-16 | 优化 ATM 手动批次“执行一次”交互：点击后列表立即显示“执行中”并禁用按钮，直到任务终态与环境回收完成后才恢复可执行，并补 UI/服务回归测试 | Codex |
| 2026-04-17 | 继续优化 ATM 手动批次“执行一次”反馈：新增列表级“环境启动中”启动条与行内状态，环境真正启动后自动隐藏；同时把 VirtualBrowser `launchBrowser` 的具体错误透传到顶部 Toast，避免用户误判为点击无响应 | Codex |
| 2026-04-18 | 完成 ATM 手动批次“中止”闭环：手动执行一次在启动中/执行中时主按钮改为 `⏹ 中止`，弹窗支持“保留环境中止 / 删除环境中止”（删除仅限创建环境模式）；同时 `WAITING_CONFIRMATION` 任务也会被 stop 直接收口为 `CANCELLED`，`on_cleanup` 调整为先于环境动作执行，并补 ATM/UI 回归测试与开发者文档 | Codex |
| 2026-04-18 | 修复 ATM 手动批次“中止不了”缺陷：`ExecutionRunner` 现在会主动 cancel 运行中的模块协程，不再只记录 stop request；`TaskContext.wait()` / `run_subtask()` 在 stop 后会尽快抛 `asyncio.CancelledError`，并补 ATM/SDK 回归测试与开发者契约说明 | Codex |
| 2026-04-16 | 收敛 ATM 环境回收语义：任务完成、创建失败与僵尸任务恢复均只关闭并回收环境，不再自动删除；只有模块显式发送 `EnvAction.DESTROY` 时才执行环境销毁，并同步新默认生命周期与回归测试 | Codex |
| 2026-04-16 | 移除运行模板中的“生命周期”兼容控件：前端不再展示任何环境删除策略入口，保存运行模板时固定写入非自动删除语义，并补 UI 回归测试 | Codex |
| 2026-04-16 | 收敛 REM 命名语义：将 `EnvironmentManager.reset()` 更名为 `recycle_env()`，明确其仅执行关窗回收和任务解绑，不表示清空浏览器持久数据，并补 ATM 回归测试 | Codex |
| 2026-04-16 | 完成 `TASK-021` / `CR-004`：为 `TaskSignal.wait_for_confirmation` 增加任务 signal 持久化、`task.signal` 事件和 ATM 详情页结构化确认面板，客户端可按 `payload.confirmation` 展示字段并调用既有确认服务完成任务收尾 | Codex |
| 2026-04-16 | 调整模块自定义数据列表横向滚动表现：隐藏底部横向滚动条，但保留触控板/滚轮横向滑动能力，并补 `ModuleDataTablePage` 回归断言锁定滚动策略 | Codex |
| 2026-04-16 | 完成 `BUG-013` / `CR-005`：`ModuleAssembler` 发现 `tasks/` / `workflows/` import 失败时改为输出异常上下文与 traceback，并在命中失败条目时向运行时回传 discovery hint；ATM 普通执行 `DevLink` 模块时也会显式开启一次性 reload，无需重启主客户端即可吃到最新源码 | Codex |

## 5. 2026-04-15 缺陷修复记录

| 日期 | 条目 | 输入 | 输出 | 状态 |
|---|---|---|---|---|
| 2026-04-15 | VirtualBrowser 创建后连接失败排查 | 用户复现截图、`crawler4j.log` 中 `env-20260415-3` 与多次 `connect_over_cdp` 400 记录 | `packages/crawler4j/src/core/rem/handle.py`、`packages/crawler4j/src/core/rem/manager.py`、对应 REM 单测 | 已完成 |
| 2026-04-15 | REM 手动创建环境边界收敛 | 用户确认 REM 只负责运行环境生命周期；手动创建成功后保持 `RUNNING` | `packages/crawler4j/src/core/rem/manager.py`、`packages/crawler4j/src/core/rem/ui/env_list_widget.py`、`packages/crawler4j/src/core/atm/execution_runner.py`、相关单测与文档/记忆 | 已完成 |
| 2026-04-15 | REM 创建成功反馈收敛 | 用户要求创建成功后不弹窗，只刷新运行环境列表 | `packages/crawler4j/src/core/rem/ui/env_list_widget.py`、对应 UI 单测、执行记录与 `.factory/memory/` 摘要 | 已完成 |
| 2026-04-15 | ATM hooks / 信号系统重构 | 用户要求统一为 ATM hooks，删除脚本/工作流私有 hooks，并用统一信号承接清理环境、等待人工确认等流程动作 | `packages/crawler4j-contracts/src/signal.py`、`packages/crawler4j-sdk/src/{base,workflow,assembler,context,signal}.py`、`packages/crawler4j/src/core/atm/{execution_runner,dispatcher,service,run_profile,ui/run_profile_dialog}.py`、相关单测与开发文档 | 已完成 |
| 2026-04-15 | ATM 手动批次模式落地 | 用户确认采用方案 A：不新增 JobType，而是在 `BATCH` 下增加 `MANUAL` 触发，UI 提供“执行一次”入口 | `packages/crawler4j/src/core/atm/{service.py,ui/task_create_dialog.py,ui/task_list_widget.py,ui/task_detail_dialog.py}`、`packages/crawler4j/tests/unit/test_core/test_atm/{test_job_modes.py,test_task_create_dialog.py,test_task_list_widget.py}`、用户/管理员说明与 `.factory/memory/` | 已完成 |
| 2026-04-15 | 运行模板资源配置收敛 | 用户要求把运行模板资源页简化为“创建环境 / 选择环境”两条路径，并删除无效参数 | `packages/crawler4j/src/core/atm/{dispatcher.py,execution_runner.py,job_runtime.py,ui/run_profile_dialog.py,ui/task_create_dialog.py}`、`packages/crawler4j/src/core/rem/{models.py,pool.py,provider.py}`、相关 ATM/REM 单测、用户说明与 `.factory/memory/` | 已完成 |
| 2026-04-15 | 运行模板创建环境页二次收口 | 用户要求删除失败重试、把基础信息和执行脚本选择合并，并按 VirtualBrowser 现有交互页重做指纹参数配置 | `packages/crawler4j/src/core/atm/{run_profile.py,ui/run_profile_dialog.py,ui/task_create_dialog.py}`、`packages/crawler4j/src/core/atm/execution_runner.py`、`packages/crawler4j/src/core/rem/{models.py,ip_pool.py,manager.py,provider.py}`、相关 ATM/REM 单测、用户说明与 `.factory/memory/` | 已完成 |
| 2026-04-16 | ATM 模块日志可见性修复 | 用户反馈“执行一次”后携程手动登录脚本看起来没有执行；本地 `crawler4j.log` 已确认执行链进入 `ctrip.run(...)` 但模块 `ctx.logger` 日志未进入主日志 | `packages/crawler4j/src/core/atm/execution_runner.py`、`packages/crawler4j/src/core/mms/ui/module_data_table_page.py`、`packages/crawler4j/tests/unit/test_core/test_atm/test_execution_runner.py`、`.factory/memory/current-state.md` | 已完成 |

### 结论

- `env-20260415-3` 在 2026-04-15 14:15:06 至 14:15:09 已完成环境创建和窗口打开，但 `connect_over_cdp` 在约 1 秒内连续 3 次失败，工作流没有进入执行阶段。
- 2026-04-14 的成功日志显示同一路径下 `Opened browser -> Connected Playwright` 最长可超过 2 秒，因此原有重试预算不足，属于真实缺陷而非误操作。
- post-create 链路在 connect 失败后会自动关闭窗口，因此不应再弹出“浏览器窗口已打开”的保留态提示；该提示只保留给手动启动场景。
