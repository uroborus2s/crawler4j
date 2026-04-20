# 测试计划

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** QA | 开发 | 架构 | 发布负责人  
**上游输入：** `docs/04-project-development/03-requirements/prd.md` | `docs/04-project-development/04-design/api-design.md` | `docs/04-project-development/05-development-process/implementation-plan.md`  
**下游输出：** `.factory/process/quality-check-report.md` | 后续测试报告  
**关联 ID：** `TC-001`, `TC-002`, `TC-003`, `TC-004`, `TC-007`, `TC-008`, `TC-009`, `TC-010`, `TC-011`, `TC-012`, `TC-024`, `TC-025`, `TC-026`, `TC-027`, `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-006`, `REQ-007`, `REQ-008`, `REQ-009`, `BUG-013`, `CR-005`, `CR-008`, `CR-009`, `NFR-003`
**最后更新：** 2026-04-20

## 1. 测试目标

- 验证当前仓库哪些链路已经稳定可用
- 明确首批实施波次需要补强的验证点

## 2. 当前测试策略

| 层次 | 目标 | 责任方 | 当前方式 |
|---|---|---|---|
| 单元测试 | 核心服务、SDK 契约、部分模块运行时 | Dev / QA | `uv run pytest -q` |
| 集成测试 | 调试会话、模块加载、CLI 场景 | Dev / QA | `packages/crawler4j/tests/integration/` |
| 验收夹具 | SDK CLI 脚手架、宿主 DevLink / ZIP 安装链与 Gate 编排 | QA | `packages/crawler4j/tests/acceptance/` |
| 静态检查 | 维护范围代码风格与低级错误 | Dev / QA | `uv run ruff check .`（按 `quality-gates.md` 的维护范围规则执行） |
| 构建验证 | 确认包可以产出 wheel/sdist | Dev / Release | `uv build --package ...` |
| 入口 / 打包 smoke | 确认根应用入口与桌面打包可运行 | Dev / Release | workspace 入口检查 + headless UI smoke + PyInstaller build |

## 3. 当前已知结果

| 测试项 | 结果 | 备注 |
|---|---|---|
| `TC-001` `uv run pytest -q` | 通过 | 2026-04-19 复验为 `426 passed`，已纳入 acceptance 夹具 |
| `TC-002` 根包 / SDK / Contracts build | 通过 | 2026-04-19 复验通过；当前仅证明可构建，不等于可运行 |
| `TC-003` `uv sync --all-packages` + `uv run python -m src.ui.app` | 通过 | workspace 根可直接启动应用包里的真实入口 |
| `TC-004` `uv run python scripts/smoke_test_ui.py` | 通过 | 2026-04-19 headless UI smoke 复验通过 |
| `TC-005` PyInstaller build | 通过 | 修正后的 spec 成功构建到 `/tmp/crawler4j-pyinstaller-dist` |
| `TC-006` `uv run ruff check .` | 通过 | 2026-04-19 复验通过，已明确排除历史 `manual/debug/verify/analyze` 脚本 |
| `TC-010` `uv run pytest packages/crawler4j/tests/unit/test_core/test_mms/test_module_data_table_page.py -q` | 通过 | 2026-04-20 口径已收敛到当前仍存在的正式回归文件，覆盖 `declare_ui` 刷新、`create_handler` / `update_handler` 路由、DevLink 页面上下文与真实模块 UI 链路 |
| `TC-011` `uv run pytest packages/crawler4j/tests/unit/test_core/test_atm/test_execution_runner.py packages/crawler4j/tests/unit/test_core/test_atm/test_dispatcher_hooks.py packages/crawler4j/tests/unit/test_core/test_atm/test_job_modes.py packages/crawler4j/tests/unit/test_core/test_atm/test_task_detail_dialog.py -q` | 通过 | 2026-04-16 覆盖等待确认信号持久化、`task.signal` 事件、结构化确认面板与客户端确认回调 |
| `TC-012` `uv run pytest packages/crawler4j/tests/unit/test_sdk/test_assembler.py packages/crawler4j/tests/unit/test_core/test_atm/test_dispatcher_hooks.py packages/crawler4j/tests/unit/test_core/test_mms/test_module_runtime.py -q` | 通过 | 2026-04-16 覆盖 `ModuleAssembler` 导入错误可见性、DevLink 普通执行 reload 注入，以及同一执行上下文只 reload 一次 |
| `TC-024` `uv run pytest packages/crawler4j/tests/unit/test_core/test_persistence/test_module_data_store.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py packages/crawler4j/tests/unit/test_sdk/test_data_capability.py -q` | 通过 | 2026-04-18 覆盖 `module_audit_events`、`db.append_event` / `db.query_events`、模块级清理与 SDK 工具能力面 |
| `TC-025` `uv run pytest packages/crawler4j/tests/acceptance -q` | 通过 | 2026-04-19 新增 acceptance 夹具，覆盖 CLI 脚手架到 `package verify`、`host devlink`、本地 ZIP `preview/apply` 与验收 gate 命令矩阵 |

## 4. 重点覆盖项

| 需求/风险 | 关键场景 | 验证方式 |
|---|---|---|
| `REQ-001` / `RISK-001` | 根应用入口与打包入口一致 | root script 检查 + UI smoke + PyInstaller smoke |
| `REQ-002` / `RISK-002` | `ctrip labor_workflow` 完整路径 | 模块运行时测试 + 依赖导入验证 |
| `REQ-006` / `RISK-004` | 模块根入口自动托管与重初始化路径 | 新脚手架 shim import + helper 分发测试 + 重初始化产物测试 |
| `REQ-007` / ATM 人工复核闭环 | 等待确认信号持久化、结构化确认面板、确认服务回调 | ATM 单测 + Qt 对话框单测 |
| `REQ-008` / `CR-008` | 模块快照数据与审计事件分层 | 持久层单测 + runtime capability 单测 + SDK 工具契约单测 |
| `REQ-009` / `CR-009` | 固定环境池 Service Job 的等待队列与资源池资格卡片 | ATM 单测/集成测试 + REM metadata 回归 + 运行模板/UI 单测 |
| `CR-003` / 模块 UI 调试回归 | `core:data_table` 页面声明刷新、模块本地 CRUD hook 与 DevLink 调试重载 | MMS 单测（`test_module_data_table_page.py`） |
| `BUG-013` / `CR-005` | 发现错误可见、DevLink 普通执行热更新 | SDK 单测 + ATM/MMS 单测 |
| `REQ-004` / `RISK-003` | 版本与 release 口径一致 | 元数据对照检查 |
| `NFR-003` | lint 质量门清晰 | `uv run ruff check .` 达成约定范围 |
| `REQ-003` / `REQ-006` | SDK CLI 与宿主安装链的正式验收夹具 | `packages/crawler4j/tests/acceptance/` + 现有 CLI / host 集成测试 |

## 5. `REQ-009` 当前实现级覆盖

| 测试 ID | 目标 | 计划验证方式 |
|---|---|---|
| `TC-026` | 固定环境池 Service Job 在容量不足时进入“运行中 + 等待中”语义，容量扩张与环境释放按 FIFO 补位；若候选环境在租约阶段被其他任务先抢走，当前任务应回到等待席位而不是直接失败；`wait_timeout` 在 RunProfile / UI / Dispatcher / ExecutionRunner 之间正确透传并触发等待席位自动超时收口 | 已由 ATM 单测覆盖：`test_job_modes.py`、`test_dispatcher_run_profile.py`、`test_run_profile_schema.py`、`test_run_profile_dialog.py`、`test_execution_runner_fixed_pool_waiting.py` |
| `TC-027` | 宿主只从“当前模块 + 当前资源池 + `eligible=true` + `READY` + 未租约占用”的环境集合里分配工位；`KEEP_ALIVE` 留下的 `RUNNING` 环境不会自动回池，且底层租约也不得再次发放给 `RUNNING`；黑号先停发号，再销毁环境后 `env_metadata` 自动级联清理 | 已由 REM 单测直接覆盖：`test_list_allocatable_envs.py`、`test_destroy_env.py`；ATM / SDK 测试只保留为间接契约补证 |

说明：当前覆盖的是队列 / FIFO / 资源池隔离 / 资格卡片 / `wait_timeout` 透传 / 等待席位自动超时收口。

## 6. 当前测试缺口

- 没有覆盖 `ctrip labor_workflow` 真实站点 E2E 验证
- `REQ-009` 当前已完成 V1 实现级单测与 SDK 契约回归，但仍缺真实业务模块接入和更高层集成验证
- `REQ-009` 当前仍缺真实业务模块接入和更高层集成验证；当前回归主要停留在宿主 / SDK 单测
- 真实站点 E2E 的执行口径现已单独收敛到 `ctrip-real-site-e2e-closeout.md`

## 6.1 `REQ-006` 已完成覆盖

| 测试 ID | 目标 | 当前验证方式 |
|---|---|---|
| `TC-007` | 新脚手架根 `__init__.py` 为固定薄壳且可导入 | `packages/crawler4j/tests/unit/test_sdk/test_cli_scaffold.py` + CLI help smoke |
| `TC-008` | 标准 `module_runtime.py` 可承载 lifecycle hooks 与 `@env_selector(...)` 环境选择器，并覆盖默认运行逻辑 | `packages/crawler4j/tests/unit/test_sdk/test_assembler.py` |
| `TC-009` | 旧模块按最新模板重新初始化后可导入并运行默认入口 | `packages/crawler4j/tests/integration/test_sdk_cli_module_mode.py` |

## 6.2 `ctrip` 真实站点 E2E 收口口径

- 执行入口统一见 [ctrip-real-site-e2e-closeout.md](ctrip-real-site-e2e-closeout.md)。
- 发布前必须同时验证 DevLink 与 ZIP 安装两条真实站点链路，不能只跑本地模块 smoke。
- 真实环境失败时必须按“宿主 / 模块 / 站点 / 环境”四类归因，不接受笼统的 “E2E 失败”。

## 7. 出口条件

- 模块开发者指南已经可按当前真实链路稳定复用
- `TASK-005` 已关闭，release 与质量结论可持续复用
- 默认质量门范围与文档导航规则见 `docs/04-project-development/06-testing-verification/quality-gates.md`

## 8. 说明

当前正式测试结论以本文件为准。旧测试专题文档已删除，避免与当前代码或当前验证结果并存。

## 9. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-20 | `TC-010` 删除对已移除 `test_ctrip_account_ui_smoke.py` 的引用，正式回归命令收口到当前仍存在的 `test_module_data_table_page.py` | Codex |
| 2026-04-19 | 补充宿主模块管理页 `qasync` 非阻塞对话框回归：`test_module_list_widget.py` 现锁定异步链路不再在协程内调用阻塞式 `exec()`，并覆盖 DevLink 添加成功提示的非阻塞消息框路径 | Codex |
| 2026-04-19 | 将 `TC-027` 收口为真实宿主证据：REM 单测直接覆盖 `list_allocatable_envs` 的模块/资源池/资格/READY/未租约筛选，以及 `destroy_env` 后 `env_metadata` 级联清理 | Codex |
| 2026-04-19 | 新增 `REQ-009` 的计划测试覆盖 `TC-026` / `TC-027`，用于固定环境池 Service Job 的等待队列、FIFO 补位、等待超时收口与资源池资格卡片回归 | Codex |
| 2026-04-19 | `REQ-009` V1 已完成本地回归：ATM / SDK 相关单测覆盖等待队列、等待超时收口与资源池契约，目标文件 `ruff` 校验通过 | Codex |
| 2026-04-19 | 新增 `TC-025` acceptance 夹具，并把 `TC-001` / `TC-002` / `TC-004` / `TC-006` 的 fresh gate 结果更新到当前口径 | Codex |
| 2026-04-18 | 新增 `TC-024`，覆盖模块审计事件存储、`db.append_event` / `db.query_events` 与 SDK 工具能力面 | Codex |
| 2026-04-17 | 补充 `ctrip` 真实站点 E2E 收口口径，并删除对历史人工调试脚本继续保留的默认假设 | Codex |
| 2026-04-16 | 新增 `TC-012`，覆盖 `ModuleAssembler` 导入错误可见性与 DevLink 普通执行 reload 语义 | Codex |
| 2026-04-16 | 新增 `TC-011`，覆盖 `TaskSignal.wait_for_confirmation` 的 signal 持久化、结构化确认面板与客户端确认回调 | Codex |
| 2026-04-08 | 新增 `TC-010`，同步 `core:data_table` 的本地 UI hook / DevLink 回归覆盖 | Codex |
| 2026-03-26 | 基于当前仓库事实建立测试计划 | Codex |
| 2026-03-28 | 删除旧测试专题引用，改为当前测试计划单一事实源 | Codex |
| 2026-03-26 | 补充默认 lint gate 规则，并登记 `TASK-005` 完成状态 | Codex |
| 2026-03-31 | 新增 `REQ-006` 的计划测试覆盖项 `TC-007` 至 `TC-009` | Codex |
| 2026-03-31 | 同步 `REQ-006` 的已实现测试覆盖与当前缺口 | Codex |
