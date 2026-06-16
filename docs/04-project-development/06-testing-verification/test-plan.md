# 测试计划

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** QA | 开发 | 架构 | 发布负责人  
**上游输入：** `docs/04-project-development/03-requirements/prd.md` | `docs/04-project-development/04-design/api-design.md` | `docs/04-project-development/05-development-process/implementation-plan.md`  
**下游输出：** `.factory/process/quality-check-report.md` | 后续测试报告  
**关联 ID：** `TC-001`, `TC-002`, `TC-003`, `TC-004`, `TC-007`, `TC-008`, `TC-009`, `TC-010`, `TC-011`, `TC-012`, `TC-024`, `TC-025`, `TC-026`, `TC-027`, `TC-044`, `TC-045`, `TC-049`, `TC-050`, `TC-052`, `TC-053`, `TC-054`, `TC-055`, `TC-057`, `TC-059`, `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-006`, `REQ-007`, `REQ-008`, `REQ-009`, `API-008`, `API-009`, `API-010`, `BUG-013`, `CR-005`, `CR-008`, `CR-009`, `CR-010`, `CR-011`, `CR-013`, `CR-014`, `CR-015`, `NFR-003`
**最后更新：** 2026-06-16

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
| `TC-001` `uv run pytest -q` | 通过 | 2026-05-18 复验为 `991 passed`，覆盖 0.4.1 发布候选工作区 |
| `TC-002` 根包 / SDK / Contracts build | 通过 | 2026-05-18 `uv run build` 已生成 `crawler4j 0.4.1`、`crawler4j-sdk 0.4.1`、`crawler4j-contracts 0.4.1` wheel/sdist |
| `TC-003` `uv sync --all-packages` + `uv run python -m src.ui.app` | 通过 | workspace 根可直接启动应用包里的真实入口 |
| `TC-004` `uv run python scripts/smoke_test_ui.py` | 通过 | 2026-05-01 headless UI smoke 复验通过，覆盖 Shell 导航/页面数量与 Dashboard 异步刷新 |
| `TC-005` PyInstaller / macOS Sparkle build | 通过 | 2026-05-18 `uv run deploy-macos-internal-release` 产出 `packages/crawler4j/dist/desktop/macos/Crawler4j.app`、`packages/crawler4j/dist/updates/macos/Crawler4j-0.4.1.dmg` 与 `appcast.xml`，并上传 macOS 更新目录 |
| `TC-006` `uv run ruff check .` | 通过 | 2026-05-18 复验通过，已明确排除历史 `manual/debug/verify/analyze` 脚本 |
| `TC-0440` REM 来源代理同步与 IP 表绑定 | 通过 | 2026-06-16 追加覆盖：VirtualBrowser 来源代理解析优先使用结构化 `host/port/protocol/user/pass`，避免 `proxy.url=http://127.0.0.1:本地端口` 被保存为绑定 IP；历史错误保存的本地转发代理可通过“同步来源代理”覆盖修复。本轮定向回归 `51 passed`，目标文件 `ruff check` 通过 |
| `TC-059` 开发模块忽略目录 symlink 回归 | 通过 | 2026-05-30 新增定向覆盖：DevLink/源码预检的 manifest lock 校验会跳过 `.venv/` 内 symlink，非忽略目录 symlink 仍拒绝；SDK `_archive_members()` 会跳过 `.venv/` 内 symlink 且不打入 ZIP |
| `TC-0400-release-review-final` 0.4.0 全面审查回归 | 通过 | 2026-05-01 复验：Full runtime surface 负向拒绝旧 Hosted UI 工具、空 workflow 自动解析、dispatcher env claim/binding 失败路径、UI smoke 与 PyInstaller spec 清理；全量 `886 passed`，打包配置 `62 passed` |
| `TC-010` `uv run pytest packages/crawler4j/tests/unit/test_core/test_mms/test_module_data_table_page.py -q` | 通过 | 2026-04-20 口径已收敛到当前仍存在的正式回归文件，覆盖 `declare_ui` 刷新、`create_handler` / `update_handler` 路由、DevLink 页面上下文与真实模块 UI 链路 |
| `TC-011` `uv run pytest packages/crawler4j/tests/unit/test_core/test_atm/test_execution_runner.py packages/crawler4j/tests/unit/test_core/test_atm/test_dispatcher_lifecycle.py packages/crawler4j/tests/unit/test_core/test_atm/test_job_modes.py packages/crawler4j/tests/unit/test_core/test_atm/test_task_detail_dialog.py -q` | 通过 | 2026-04-30 覆盖等待确认信号持久化、`task.signal` 事件、结构化确认面板、客户端确认回调，以及 0.4.0 不再调用生命周期 hooks 的执行链 |
| `TC-012` `uv run pytest packages/crawler4j/tests/unit/test_core/test_atm/test_dispatcher_lifecycle.py packages/crawler4j/tests/unit/test_core/test_mms/test_module_runtime.py -q` | 通过 | 2026-04-30 覆盖 DevLink 普通执行 reload 注入、同一执行上下文只 reload 一次，以及旧 `ModuleService.call_hook()` 退出运行链 |
| `TC-024` `uv run pytest packages/crawler4j/tests/unit/test_core/test_persistence/test_module_data_store.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py packages/crawler4j/tests/unit/test_sdk/test_data_capability.py -q` | 通过 | 2026-04-24 已升级为 `ctx.db` fluent API 契约基线，覆盖旧数据库工具面不再注册、managed/custom/view/read-only view 边界与 SDK 旧调用扫描 |
| `TC-056` `uv run pytest packages/crawler4j/tests/unit/test_sdk/test_taskcontext.py packages/crawler4j/tests/unit/test_sdk/test_data_capability.py packages/crawler4j/tests/unit/test_sdk/test_cli_scaffold.py packages/crawler4j/tests/unit/test_core/test_persistence/test_module_data_store.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py packages/crawler4j/tests/unit/test_core/test_atm/test_execution_runner.py packages/crawler4j/tests/unit/test_core/test_mms/test_module_ui_runtime.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py packages/crawler4j/tests/unit/test_core/test_mms/test_settings_store.py -q` | 通过 | 2026-04-24 `159 passed`，验证模块数据库接口只保留 `ctx.db` fluent API、Hosted UI readonly 写保护、执行器真实模块夹具与文档口径同步 |
| `TC-057` `uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_destroy_env.py -q` | 通过 | 2026-04-26 `6 passed`，覆盖 REM 环境销毁对 UI 数字字符串 ID 的兼容，锁定真实 `EnvPool` 整数键可被 `"282"` 这类表格值命中并删除数据库记录 |
| `TC-058` `uv run pytest packages/crawler4j/tests/unit/test_core/test_mms/test_config_yaml_validation.py packages/crawler4j/tests/unit/test_core/test_mms/test_module_detail_page.py packages/crawler4j/tests/unit/test_core/test_mms/test_settings_store.py -q` | 通过 | 2026-04-26 `28 passed`，覆盖 QScintilla YAML 编辑器实例化、标准 YAML flow mapping 保存规范化、重复键拒绝、验证层格式错误与顶层映射约束 |
| `TC-025` `uv run pytest packages/crawler4j/tests/acceptance -q` | 通过 | 2026-04-22 已同步到 hosted page V1 口径，覆盖 CLI 脚手架到 `package verify`、`host devlink`、本地 ZIP `preview/apply` 与验收 gate 命令矩阵 |
| `TC-049` `uv run pytest packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py packages/crawler4j/tests/unit/test_core/test_mms/test_module_detail_page.py packages/crawler4j/tests/unit/test_core/test_mms/test_module_data_table_page.py packages/crawler4j/tests/unit/test_core/test_mms/test_mms.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py packages/crawler4j/tests/unit/test_core/test_persistence/test_module_data_store.py packages/crawler4j/tests/unit/test_sdk/test_cli_scaffold.py packages/crawler4j/tests/integration/test_sdk_cli_module_mode.py packages/crawler4j/tests/acceptance/test_sdk_cli_scaffold_package_acceptance.py` | 通过 | 2026-04-22 回归 `105 passed`，覆盖 hosted page renderer、模块详情页入口跳转、runtime capability、声明式 schema 持久化/清理、CLI 脚手架、integration 与 acceptance 的 hosted UI V1 契约 |
| `TC-050` `uv run pytest packages/crawler4j/tests/unit/test_core/test_persistence/test_module_data_store.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py packages/crawler4j/tests/unit/test_core/test_mms/test_module_data_table_page.py packages/crawler4j/tests/unit/test_core/test_mms/test_module_detail_page.py packages/crawler4j/tests/unit/test_sdk/test_cli_scaffold.py -q` | 通过 | 2026-04-23 最终回归 `138 passed`，覆盖 `row_action`、`open_page.params`、缓存页参数替换、目标页面内联表格 `navigation_filters`、过滤详情表默认 CRUD 的全量资源定点写回、隐藏父键保留、显式 `data_resource` metadata 保持，以及 omitted `resource_id` alias 路由兼容 |
| `TC-044` `uv run pytest packages/crawler4j/tests/unit/test_core/test_system/test_update_service.py -q` | 通过 | 2026-04-22 补齐 Windows Velopack / macOS Sparkle 后端分派、状态消息与启动时 bootstrap 分流回归 |
| `TC-045` `uv run pytest packages/crawler4j/tests/unit/test_sdk/test_packaging_config.py -q` | 通过 | 2026-04-22 补齐 `package-windows-release` 命令、Velopack 配置写入、`vpk` 命令形状与 root script 暴露回归 |

## 4. 重点覆盖项

| 需求/风险 | 关键场景 | 验证方式 |
|---|---|---|
| `REQ-001` / `RISK-001` | 根应用入口与打包入口一致 | root script 检查 + UI smoke + PyInstaller smoke |
| `REQ-002` / `RISK-002` | `ctrip labor_workflow` 完整路径 | 模块运行时测试 + 依赖导入验证 |
| `REQ-006` / `RISK-004` | 模块根入口自动托管与重初始化路径 | 新脚手架 shim import + helper 分发测试 + 重初始化产物测试 |
| `REQ-007` / ATM 人工复核闭环 | 等待确认信号持久化、结构化确认面板、确认服务回调 | ATM 单测 + Qt 对话框单测 |
| `REQ-008` / `CR-008` | 模块数据资源与模块自管历史统一通过 `ctx.db` 建模 | 持久层单测 + runtime capability 单测 + SDK fluent API 契约单测 |
| `REQ-009` / `CR-009` | 环境候选 Service Job 的等待队列、候选纯函数、模块环境授权和租约后复核 | ATM 单测/集成测试 + MMS/SDK 候选扫描回归 + 运行模板/UI 单测 |
| `CR-003` / 模块 UI 调试回归 | hosted page 页面声明刷新、页面内联 `DataTable` CRUD hook 与 DevLink 调试重载 | MMS 单测（`test_module_data_table_page.py`） |
| `CR-003` / 模块配置编辑回归 | 模块详情页配置编辑器、YAML 语法校验、顶层映射约束、重复键拒绝与保存后规范化 | MMS 单测（`test_config_yaml_validation.py`、`test_module_detail_page.py`、`test_settings_store.py`） |
| `BUG-013` / `CR-005` | 发现错误可见、DevLink 普通执行热更新 | SDK 单测 + ATM/MMS 单测 |
| `REQ-004` / `RISK-003` | 版本与 release 口径一致 | 元数据对照检查 |
| `CR-010` / Windows 发布闭环 | Windows `PyInstaller onedir + Velopack` 打包、自更新桥接与宿主更新配置一致 | 脚本回归 + `UpdateService` 单测 + 文档同步检查 |
| `API-008` / `CR-011` | hosted page V1、宿主页渲染器、CLI page/data-table 脚手架与旧 `micro_app` 删除路径一致 | Core/SDK/unit/integration/acceptance 定向回归 |
| `API-008` / `CR-013` | Hosted UI 主从表行导航、`open_page.params`、缓存页参数替换与详情表 `navigation_filters` | Core/SDK unit 定向回归 + CLI Hosted UI 契约回归 |
| `API-009` / `CR-014` | 模块实体表视图、受控 SQL 模板、`ctx.db` fluent 查询 | 持久层单测 + runtime capability 单测 + Hosted UI 只读查询回归 |
| `NFR-003` | lint 质量门清晰 | `uv run ruff check .` 达成约定范围 |
| `REQ-003` / `REQ-006` | SDK CLI 与宿主安装链的正式验收夹具 | `packages/crawler4j/tests/acceptance/` + 现有 CLI / host 集成测试 |

## 5. `REQ-009` 当前实现级覆盖

| 测试 ID | 目标 | 当前验证方式 |
|---|---|---|
| `TC-026` | 环境候选 Service Job 在容量不足时进入“运行中 + 等待中”语义，容量扩张与环境释放按 FIFO 补位；若候选环境在租约阶段被其他任务先抢走，当前任务应回到等待席位而不是直接失败；`wait_timeout` 在 RunProfile / UI / Dispatcher / ExecutionRunner 之间正确透传并触发等待席位自动超时收口 | 已由 ATM 单测覆盖：`test_job_modes.py`、`test_dispatcher_run_profile.py`、`test_run_profile_schema.py`、`test_run_profile_dialog.py`、`test_execution_runner_env_candidates_waiting.py` |
| `TC-027` | 宿主只从“当前模块 `@env_candidates` 候选集合 + 已绑定当前模块 + `READY` + 浏览器 + 未租约占用”的环境集合里分配工位；`KEEP_ALIVE` 留下的 `RUNNING` 环境不会自动可分配；黑号通过模块数据表由候选纯函数实时过滤 | 已由 ATM / REM / SDK 单测覆盖：`test_execution_runner_env_candidates_waiting.py`、`test_job_modes.py`、`test_destroy_env.py`、`test_cli_scaffold.py` |

说明：当前覆盖的是队列 / FIFO / 候选函数 / 模块环境授权 / 租约后复核 / `wait_timeout` 透传 / 等待席位自动超时收口。

## 5.1 `API-009` 测试覆盖

| 测试 ID | 目标 | 计划验证方式 |
|---|---|---|
| `TC-052` | `module_db_views`、manifest 视图注册、视图 SQL 模板校验与卸载清理：仅允许单条 `SELECT/WITH SELECT`，只允许 `{{resource:<resource_id>}}` 占位引用当前模块 `custom_table`，并能按 `cleanup_policy` 正确 `DROP VIEW` | 持久层单测 + runtime capability 单测 |
| `TC-053` | `ctx.db.from_(view_or_resource)` 与 hosted page 内联 `DataTable` 只读查询：按受控字段过滤、排序、分页，`query_handler` 正确路由查询参数并保持无 CRUD | MMS 单测 + SDK CLI 契约单测 + integration/acceptance |
| `TC-054` | 新 `SkyDataTable` 组件：搜索、排序、分页、request_id 丢弃过期结果、行点击和 actions 事件统一从查询契约驱动 | `packages/crawler4j/tests/unit/test_ui/test_data_table.py` |
| `TC-055` | 宿主/模块统一接入：宿主页与模块内联 `DataTable` 全部切到新组件与新 schema，旧组件与旧 schema 被移除 | MMS/ATM/REM 定向单测 + SDK CLI 契约回归 + acceptance |

## 6. 当前测试缺口

- 没有覆盖 `ctrip labor_workflow` 真实站点 E2E 验证
- `REQ-009` 当前已完成实现级单测与 SDK 契约回归，但仍缺真实业务模块接入和更高层集成验证
- `CR-010` 当前只完成本地脚本/单元级验证，仍缺 Windows 真机打包、安装、升级与签名验证
- QScintilla 已进入桌面依赖线，macOS PyInstaller 打包态证据已在 2026-05-01 补齐；Windows 打包态仍需真机验证
- `crawler4j-sdk 0.4.1` 与 `crawler4j-contracts 0.4.1` 已记录当前版本 build / publish 证据；后续仍需补齐正式 Git tag / GitHub release 资产
- 真实站点 E2E 的执行口径现已单独收敛到 `ctrip-real-site-e2e-closeout.md`

## 6.1 `REQ-006` 已完成覆盖

| 测试 ID | 目标 | 当前验证方式 |
|---|---|---|
| `TC-007` | 新脚手架根 `__init__.py` 为固定薄壳且可导入 | `packages/crawler4j/tests/unit/test_sdk/test_cli_scaffold.py` + CLI help smoke |
| `TC-008` | 历史 `module_runtime.py` / `@env_selector(...)` / `hooks/*.py` 覆盖项已退出当前协议；当前以 `workflows/`、`candidates/`、`cleanups/`、`pages/` 和 Core runtime descriptor 扫描回归为准 | `test_v2_scanner_diagnostics.py`、`test_mms.py`、`test_cli_scaffold.py`、`test_contracts_exports.py` |
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
| 2026-06-16 | 追加 REM 来源代理解析修复回归：`test_provider.py` 锁定 VirtualBrowser 同时返回结构化代理和本地转发 URL 时优先采用真实 `host/port`；`test_import_existing_env.py` 锁定已保存为 `127.0.0.1:本地端口` 的历史环境可通过同步来源代理覆盖修复并重新绑定正确 IP 条目；组合回归 `51 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-06-16 | 新增 REM 来源代理同步与 IP 表绑定回归：`test_import_existing_env.py` 锁定导入时保存来源代理并自动唯一匹配 IP 条目；`test_provider.py` 锁定 VirtualBrowser 来源环境列表保留代理配置；`test_env_list_widget.py` 锁定环境列表“同步来源代理”预览确认与刷新链路；组合回归 `49 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-06-06 | 补充指纹浏览器生命周期并发串行化回归：`test_provider.py` / `test_bitbrowser_provider.py` 新增并发 `close()` / `destroy()` / `reset()` 用例，锁定同一 provider 的外部管理 API 不会并发冲击本地服务，并覆盖 handle 缺失但 `external_id` 存在时仍删除真实外部环境；provider / client / manager 入口组合回归为 `53 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-06-06 | 补充 VirtualBrowser 并发启动串行化回归：`test_provider.py` 新增并发 `open()` 用例，锁定同一 `VirtualBrowserProvider` 在多个环境同时启动时不会并发调用 `launchBrowser`；组合回归 `test_provider.py` + `test_virtualbrowser_client.py` 为 `25 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-05-18 | 发布候选提升到 `0.4.1` 后完成 fresh gate：`uv lock --check`、全量 `991 passed`、`ruff check .`、三包 `uv run build`、SDK/Contracts PyPI publish 与 macOS Sparkle 客户端升级包发布均通过；正式发布仍缺 `ctrip` 真站 E2E、Windows 真机证据与 Git tag / GitHub release 资产 | Codex |
| 2026-04-27 | 历史记录：当时仅同步文档/记忆/版本事实，未新增全量测试、包构建、PyInstaller 打包或发布证据；该缺口已在 2026-05-01 对 0.4.0 build 与 macOS package-desktop 补证，publish 仍待补 | Codex |
| 2026-04-26 | 补充模块配置 YAML 数组缩进与可读性回归：`test_module_detail_page.py` 锁定 `ModuleConfigPage._dump()` 输出数组时使用父 key 下缩进的 block sequence，锁定 `YamlCodeEditor.setPlainText()` 兜底规范化旧 indentless sequence，并锁定编辑器字号提升；`test_config_yaml_validation.py` 继续覆盖缩进数组的解析契约。定向回归 `21 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-04-26 | 补充模块详情页滚动条与 YAML 编辑器视觉回归：`test_module_detail_page.py` 锁定模块配置/Workflow 配置编辑器隐藏横向和纵向滚动条、使用 plain fold 样式，并锁定左侧菜单与任务链滚动区隐藏滚动条；`test_managed_page_scroll.py` 锁定 Hosted 页面默认隐藏双向滚动条；`test_data_table.py` 锁定 `SkyDataTable` 隐藏双向滚动条。定向回归 `22 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-04-30 | 历史资源池客户端交互回归已被环境候选交互回归替代：当前 `test_run_profile_dialog.py` 锁定候选函数下拉、`candidates/candidate_params` 序列化和旧 `resource_pool/selector_name` 字段退出 | Codex |
| 2026-04-26 | 新增模块配置 YAML 编辑器回归：`test_config_yaml_validation.py` 锁定独立验证层接受标准 YAML 映射、拒绝格式错误、非映射顶层和重复键；`test_module_detail_page.py` 锁定配置页使用 QScintilla 编辑器、flow mapping 保存后规范化为块格式；组合回归 `28 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-04-30 | 资源池声明契约回归已被环境候选契约回归替代：当前 `test_mms.py` 拒绝 `module.yaml.resource_pools[]`，`test_runtime_capabilities.py` 锁定 `env.*resource_pool*` 工具已移除，SDK/Core scanner 只接受 `candidates/` 下 `@env_candidates` | Codex |
| 2026-04-26 | 补充“从已有环境导入”启动进度回归：`ExecutionRunner` 锁定复用环境 `start_env()` 完成前维持 `PENDING/环境启动中`，`test_env_list_widget.py` 锁定导入流程等待关联任务离开 `PENDING` 后再关闭公共进度弹窗；定向 `pytest` 为 `53 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-04-26 | 补充“从已有环境导入”关联任务回归：`test_import_job_service.py` 锁定导入多个已有环境时复用用户选择的手动批次 Job，并按 `concurrency_target` 只启动可用并发槽；`test_import_existing_env_dialog.py` / `test_env_list_widget.py` 锁定弹窗改为选择关联任务和多选环境；`test_data_table.py` 锁定表格 schema 支持 `selection_mode="multi"` | Codex |
| 2026-04-26 | 新增 `TC-057`：`test_destroy_env_accepts_numeric_string_id_from_ui` 锁定环境列表传入数字字符串 ID 时 `destroy_env()` 仍能命中真实 `EnvPool` 整数键并删除数据库记录；REM 目录回归 `119 passed`，全量 `uv run pytest -q` 为 `739 passed` | Codex |
| 2026-04-25 | 新增弹窗标题栏、VirtualBrowser 销毁稳定等待与 ATM 启动进度不阻塞回归：`test_public_ui_boundaries.py` 锁定所有 core QDialog 必须走公共标题栏 helper，`test_provider.py` 锁定删除后等待外部环境消失，`test_dispatcher_lifecycle.py` / `test_task_list_widget.py` 锁定 `TASK_STARTED` 刷新与非 modal 启动进度。全量 `uv run pytest -q` 为 `738 passed` | Codex |
| 2026-04-25 | 新增公共 UI 异步与边界回归：`test_dialog_async.py` 锁定公共弹窗使用非阻塞 `show()` 而非嵌套 `exec()`，`test_public_ui_boundaries.py` 锁定 core UI 不再直接使用 `QMessageBox` / `QDialogButtonBox`；REM/MMS/ATM 目录回归覆盖创建/导入/编辑环境、IP 池、模块安装/卸载、托管页 CRUD 与手动批次中止选择 | Codex |
| 2026-04-25 | 新增公共进度弹窗与标题栏边界回归：`test_progress_dialog.py` 锁定 `ProgressDialog` 使用非阻塞 `show()` 与不定进度条，`test_public_ui_boundaries.py` 锁定 core UI 不再直接使用 `QProgressBar` 或无标题栏弹窗；REM/MMS/ATM 相关 UI 测试覆盖内联进度条改为公共弹窗且完成后关闭。全量 `uv run pytest -q` 为 `731 passed` | Codex |
| 2026-04-25 | 新增公共消息弹窗视觉优化与公共组件收口回归：`test_message_dialog.py` 锁定 `MessageDialog` 对齐“安装模块”面板的原生窗口壳与深色内容区，`test_button.py` 锁定 `StyledButton(success)` 动作按钮色板，`test_module_install_dialog.py` 锁定安装模块弹窗改用公共输入框/按钮/消息弹窗；ATM/MMS/System 相关单测覆盖简单提示和确认改走公共 `MessageDialog` / `ConfirmDialog` | Codex |
| 2026-04-25 | 新增公共 `MessageDialog`、IP 绑定无持久关系表、遗留 `configs` 表退出初始化回归：`test_message_dialog.py` 锁定公共消息弹窗，`test_ip_pool_tab.py` 锁定 IP 测试结果使用公共消息弹窗，`test_ip_pool.py` 锁定绑定/解绑只更新 `ip_entries.bound_count` 且不创建 `env_ip_bindings`，`test_settings_store.py` 锁定不再创建 `configs` 表 | Codex |
| 2026-04-25 | 历史记录：曾新增运行环境列表 `env_metadata` 资源池可用状态与 IP 测试结果深色面板回归；当前正式 UI 已移除资源池可用状态列，仅保留原始 `env_metadata` 行数据与 IP 测试结果深色面板回归 | Codex |
| 2026-04-25 | 补充“从已有环境导入”字段删除与名称唯一性回归：`test_import_existing_env.py` 锁定同 provider 同名会被视为已导入，`test_state_db_migration.py` 锁定状态库删除旧 provider 扩展列并把唯一索引切到 `(provider, name)`，UI 与导入任务服务回归锁定只传 `provider/name/import_mode` | Codex |
| 2026-04-24 | 新增 Hosted UI 页面级滚动配置回归：`test_hosted_ui_card.py` 现锁定 `Page.scroll.vertical = hidden` 的 schema 规范化与非法值拒绝；`test_managed_page_scroll.py` 通过隔离 `ModuleUIRuntimeBridge` 的方式锁定 `ManagedPageRenderer` 会把 Hosted Page 外层 `QScrollArea` 切到 `ScrollBarAlwaysOff/AsNeeded`，避免“今日运营看板”这类页面继续误显示竖向滚动槽 | Codex |
| 2026-04-24 | 新增 `test_confirm_dialog.py`，锁定共享危险确认框 `ConfirmDialog` 的深色背景、标题/正文文案颜色，以及 `confirmCancel` / `confirmDanger` 两个按钮选择器，避免共享表格删除确认面板再次回退到系统默认配色 | Codex |
| 2026-04-24 | 继续补强宿主 UI 生命周期回归：`test_app.py` 新增 `QEvent.Type.Quit` 延后退出路径，并锁定宿主入口会先完成 `TaskService.stop()` / `DebugService.shutdown()` / `PlaywrightManager.force_shutdown()` 再结束 Qt 事件循环，覆盖 Windows 打包态曾复现的 `Event loop stopped before Future completed` | Codex |
| 2026-04-24 | 补充“从已有环境导入”弹窗的 warning UI 回归：`test_import_existing_env_dialog.py` 现同时锁定 warning 区域的实际高度不再低于 `warning_label.heightForWidth(...) + 内边距`，以及 warning 文本层显式为 `background: transparent; border: none;`，避免打包态下多行文案继续被裁掉或出现额外内圈 | Codex |
| 2026-04-24 | 补强宿主 UI 生命周期回归：`test_app.py` 现锁定 debug worker/debugpy adapter/Shell 相关入口改为懒加载，不再因深层循环导入阻塞测试；同时新增“最后一个窗口关闭后仍能完成异步收尾”的回归，固定 `lastWindowClosed -> shutdown cleanup -> loop stop` 顺序，防止桌面包再次弹出 `Event loop stopped before Future completed` | Codex |
| 2026-04-24 | `TC-024` 已升级为 `ctx.db` fluent API 契约回归，新增 `TC-056` 组合覆盖旧数据库工具面退出、managed/custom/view/read-only view 边界、Hosted UI readonly 写保护与执行器真实模块夹具；定向回归 `159 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-04-23 | 开发团队 2 曾补齐 SDK 数据能力契约断言；该批断言已在 2026-04-24 被 `ctx.db` fluent API 契约替换 | Codex |
| 2026-04-22 | 新增 `TC-049`，把 hosted page renderer、模块详情页、runtime capability、CLI / integration / acceptance 的 hosted UI V1 定向回归正式纳入测试计划 | Codex |
| 2026-04-23 | 新增并最终收口 `TC-050`，补 Hosted UI 主从表行导航、`open_page.params`、缓存页参数替换、详情表 `navigation_filters`、过滤详情表默认 CRUD 与 alias 资源路由兼容的定向回归 | Codex |
| 2026-04-23 | 新增 `TC-052` / `TC-053` 计划项，为模块实体表视图、受控 SQL 模板与只读统计表查询建立正式测试覆盖入口 | Codex |
| 2026-04-23 | `TC-052` / `TC-053` 已本地通过；该批次在 2026-04-24 已被 `ctx.db` fluent API 口径替换，视图与只读视图仍保持 manifest 驱动 | Codex |
| 2026-04-23 | 新增 `TC-054` / `TC-055`，为共享表格组件 `SkyDataTable` 重构、宿主/模块统一接入与旧 schema 删除建立正式测试覆盖入口 | Codex |
| 2026-04-23 | 继续收口 `TC-054` / `TC-055`：`hosted_ui.py` 已删除内联 `DataTable` 顶层 `binding` / `rows` 兼容写法，页面 schema 现必须显式声明 `data_source`，与共享表格破坏性重构边界保持一致 | Codex |
| 2026-04-24 | Hosted UI 页面协议修正为 `pages/` 注册可路由页面、`ui_extension.pages[]` 只控制左侧菜单；新增 SDK `--no-menu` 与模块详情页非菜单详情页跳转回归 | Codex |
| 2026-04-22 | SDK CLI / 验收夹具已切到 hosted page V1：`page create` 不再生成 `ui/` 页面类，`data-table create` 与 `check full` 统一改验 `ui_extension.pages[]`、`ui.declare_page` 与页面内联 `DataTable/query_handler` | Codex |
| 2026-04-22 | 新增 `TC-044` / `TC-045`，补齐 Windows Velopack 更新服务与发布脚本回归计划；同时登记 `CR-010` 当前仍缺 Windows 真机安装/升级验证 | Codex |
| 2026-04-21 | 新增宿主打包态 `qasync` 定时器兼容回归：`test_qasync_compat.py` 现锁定 `_SimpleTimer` 已替换为宿主安全实现，覆盖回调触发与 stop 后不再继续执行两条路径；同时补跑 `test_app.py` / `test_log_console.py` / `test_dashboard.py` / `test_shell.py` 作为 UI 生命周期回归 | Codex |
| 2026-04-21 | 新增宿主 `qasync` UI 重入回归：`test_env_list_widget.py` 现锁定 REM 环境页异步链路不再在协程内调用阻塞式 `exec()` / 静态 `QMessageBox.*`，`test_dashboard.py` 现锁定仪表盘刷新会在新一轮开始前取消上一轮 pending load，避免 REM 模态提示与定时刷新交错重入 | Codex |
| 2026-04-20 | `TC-010` 删除对已移除 `test_ctrip_account_ui_smoke.py` 的引用，正式回归命令收口到当前仍存在的 `test_module_data_table_page.py` | Codex |
| 2026-04-19 | 补充宿主模块管理页 `qasync` 非阻塞对话框回归：`test_module_list_widget.py` 现锁定异步链路不再在协程内调用阻塞式 `exec()`，并覆盖 DevLink 添加成功提示的非阻塞消息框路径 | Codex |
| 2026-04-19 | 将 `TC-027` 收口为真实宿主证据：REM 单测直接覆盖 `list_allocatable_envs` 的模块/资源池/资格/READY/未租约筛选，以及 `destroy_env` 后 `env_metadata` 级联清理 | Codex |
| 2026-04-30 | `REQ-009` 正式测试口径切到环境候选方案：`TC-026` / `TC-027` 覆盖 `@env_candidates` 候选纯函数、FIFO 补位、模块环境授权、租约后复核和等待超时收口 | Codex |
| 2026-04-19 | 历史记录：曾新增固定资源池 Service Job 计划测试；该口径已被 2026-04-30 环境候选方案替代 | Codex |
| 2026-04-19 | 历史记录：固定资源池 V1 曾完成本地回归；当前正式回归以环境候选方案为准 | Codex |
| 2026-04-19 | 新增 `TC-025` acceptance 夹具，并把 `TC-001` / `TC-002` / `TC-004` / `TC-006` 的 fresh gate 结果更新到当前口径 | Codex |
| 2026-04-18 | 新增 `TC-024`，最初覆盖模块审计事件工具面；2026-04-24 已升级为 `ctx.db` fluent API 契约基线 | Codex |
| 2026-04-17 | 补充 `ctrip` 真实站点 E2E 收口口径，并删除对历史人工调试脚本继续保留的默认假设 | Codex |
| 2026-04-16 | 新增 `TC-012`，覆盖 `ModuleAssembler` 导入错误可见性与 DevLink 普通执行 reload 语义 | Codex |
| 2026-04-16 | 新增 `TC-011`，覆盖 `TaskSignal.wait_for_confirmation` 的 signal 持久化、结构化确认面板与客户端确认回调 | Codex |
| 2026-04-08 | 新增 `TC-010`，同步 `core:data_table` 的本地 UI hook / DevLink 回归覆盖 | Codex |
| 2026-03-26 | 基于当前仓库事实建立测试计划 | Codex |
| 2026-03-28 | 删除旧测试专题引用，改为当前测试计划单一事实源 | Codex |
| 2026-03-26 | 补充默认 lint gate 规则，并登记 `TASK-005` 完成状态 | Codex |
| 2026-03-31 | 新增 `REQ-006` 的计划测试覆盖项 `TC-007` 至 `TC-009` | Codex |
| 2026-03-31 | 同步 `REQ-006` 的已实现测试覆盖与当前缺口 | Codex |
