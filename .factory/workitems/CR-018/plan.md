# Hosted UI DataTable 多选批量编辑实施计划

> **给执行者：** 计划评审通过后，把状态交还 `using-shanforge` 流程总控判断下一步。步骤使用复选框语法便于追踪。

**目标：** 为 Hosted UI `DataTable` 增加当前页多选批量编辑能力，并让 `managed_dataset` 模块通过通用 handler 自行完成字段批量更新。

**架构：** Contracts 定义并规范化公开 schema；SDK scanner 在模块打开阶段校验 handler 引用、签名与类型；Core Renderer 复用 `SkyDataTable` 多选、现有 CRUD 表单和 `@ui_action` 调用链。Core 不直接写模块数据库。

**技术栈：** Python 3.12、PyQt6、crawler4j-contracts、crawler4j-sdk v2 scanner、pytest、ruff、uv。

**工作项：** `CR-018`

**状态：** `approved`

---

## 输入

- 已批准规格：用户指定的 `core-hosted-datatable-multi-select-bulk-update-request.md`。
- 当前工作项简报：`.factory/workitems/CR-018/brief.md`。
- 相关记忆：`.factory/memory/runtime-brief.md`、`requirements.summary.md`、`api.summary.md`。
- 已读取事实：`hosted_ui.py`、`v2_scanner.py`、`managed_page_renderer.py`、`data_table.py` 及其目标测试。

## 范围

### 目标

- 公开并验证 `selection_mode`、`bulk_update_handler`、`toolbar.bulk_update`。
- 实现当前页批量编辑与同步 / 异步一致行为。
- 保持旧模块和既有 CRUD、查询、筛选、排序、分页行为。

### 非目标

- 不新增数据库 API、跨分页选择、批量删除、第二套表单系统或业务字段语义。

## 文件

| 类型 | 路径 | 职责 |
|---|---|---|
| 修改 | `packages/crawler4j-contracts/src/crawler4j_contracts/hosted_ui.py` | 公开 schema、默认值和组合校验 |
| 修改 | `packages/crawler4j-sdk/src/v2_scanner.py` | handler 引用、固定签名和类型诊断 |
| 修改 | `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py` | 透传选择模式、批量 toolbar、表单与调用 |
| 修改 | `packages/crawler4j/src/ui/components/data_table.py` | 在查询 / 翻页 / 手动刷新发起时清除当前页选择 |
| 测试 | `packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py` | Contracts 规范化与非法组合 |
| 测试 | `packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py` | SDK 批量 handler 诊断 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py` | Core 同步 / 异步与选择语义 |
| 测试 | `packages/crawler4j/tests/unit/test_ui/test_data_table.py` | 多选底层回归（仅在现有覆盖不足时补充） |
| 文档 | `docs/04-project-development/03-requirements/prd.md` | `REQ-012` / `NFR-012` 正式需求与版本历史 |
| 文档 | `docs/04-project-development/04-design/hosted-ui-datatable-bulk-update-design.md` | 本仓正式设计事实 |
| 文档 | `docs/04-project-development/04-design/api-design.md` | `API-021` 契约 |
| 文档 | `docs/04-project-development/05-development-process/implementation-plan.md` | `TASK-036` 实施波次与结果 |
| 文档 | `docs/04-project-development/05-development-process/execution-log.md` | 实施与验证事件 |
| 文档 | `docs/04-project-development/06-testing-verification/test-plan.md` | `TC-069` 测试事实 |
| 文档 | `docs/04-project-development/10-traceability/requirements-matrix.md` | REQ -> API -> TASK -> TC 追踪 |
| 文档 | `docs/04-project-development/10-traceability/interface-matrix.md` | `API-021` owner 与验证责任 |
| 文档 | `docs/04-project-development/10-traceability/document-index.md` | 新设计文档索引 |
| 记忆 | `.factory/memory/{requirements,api,tasks,tests,traceability}.summary.md` | 压缩状态与索引 |

## 边界

- 层级：Contracts -> SDK 静态诊断 / Core Renderer 消费。
- 领域：MMS Hosted UI 与模块开发契约。
- 接口归属方：Core / Contracts / SDK 维护者。
- 下游依赖：使用 `@page` / `@ui_action` 和 `managed_dataset` 的模块。
- 禁止耦合：Core 不识别账号、手机号、分组字段，不直接调用 `ctx.db` 写模块数据。

## 任务 1：Contracts 与 SDK 契约

**依赖：** 无。执行简报：`.factory/workitems/CR-018/task-briefs/task-1-contracts-sdk.md`。

**任务切片：**

- 设计方案：在现有 DataTable CRUD schema 和 scanner 分支内最小扩展。
- 接口设计：固定 `bulk_update_handler(context, primary_keys, payload)`。
- UI 或 `N/A`：N/A；本任务只处理序列化契约与静态诊断，UI 在任务 2。
- 测试设计：逐条覆盖默认 / 非法 selection、bulk toolbar 默认显示 / 显式关闭 / 缺 handler 组合、缺 primary key / update columns、scanner 首参名和集合 / payload 类型。
- 开发：仅修改 `hosted_ui.py`、`v2_scanner.py`。
- 单测：两个 SDK 目标测试文件。
- review：独立 reviewer 核对兼容性和诊断路径。
- 集成测试：与 Core 目标测试合并执行。
- 失败断言：缺测试设计、UI N/A 无原因或出现占位语均失败。

- [ ] RED：新增 Contracts / scanner 用例并运行，确认因未知字段或缺失诊断失败。用例必须断言：
  - handler 存在且 `toolbar.bulk_update` 省略时 schema 保留“未显式关闭”语义；显式 `False` 被保留；显式 `True` 但缺 handler 被 Contracts 拒绝并产生精确 scanner 诊断。
  - handler 存在但缺 `crud.primary_key` 或非空 `form.update_columns` 时产生具体字段路径诊断。
  - 只接受严格 `(context, primary_keys, payload)`；把首参写成 `ctx`、错序、默认值、kw-only、`*args` / `**kwargs` 均失败。
  - `primary_keys` 接受 `list[str]` / `list[int]` / `List[T]`，拒绝无注解、裸 `list`、`list[Any]`、`Any`、`Mapping`；payload 拒绝裸 `dict` / `Mapping` / `Any`。
- [ ] GREEN：加入 schema 字段、严格规范化、组合校验和最小类型判断。
- [ ] 验证：`uv run pytest packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py -q -p no:cacheprovider`，期望全部通过。

## 任务 2：Core Renderer 多选批量编辑

**依赖：** 任务 1 的公开 schema 已落地并通过 Contracts / scanner 定向测试。执行简报：`.factory/workitems/CR-018/task-briefs/task-2-core-renderer.md`。

**任务切片：**

- 设计方案：复用 `SkyDataTable.selected_rows()`、现有 CRUD update 表单和 action 调用链。
- 接口设计：Core 只传 `{"primary_keys": [...], "payload": {...}}`。
- UI：新增“批量编辑”按钮；0 行禁用，1+ 行启用，单条编辑 / 删除仅 1 行启用。
- 测试设计：逐条锁定按钮状态、主键保序去重、缺失主键、空值、成功 / 失败、同步 / 异步、行内单条动作，以及翻页 / 刷新清选择。
- 开发：仅修改 `managed_page_renderer.py`；底层表格已有能力时不修改 `data_table.py`。
- 单测：renderer 目标测试，必要时补 data_table 一条底层回归。
- review：独立 reviewer 核对 event loop 与选择清理。
- 集成测试：Contracts + SDK + Renderer 目标集。
- 失败断言：缺测试设计、UI 行为未覆盖或出现占位语均失败。

- [ ] RED：新增 Renderer 用例并运行，确认硬编码单选、缺批量按钮 / handler 路径导致失败。用例必须逐条断言：
  - 未选中时批量按钮禁用，选中 1 / 2 行时启用；单条编辑 / 删除仅 1 行启用。
  - handler 存在且 `toolbar.bulk_update` 省略时显示；显式 `False` 时隐藏；`render="row_actions"` 不隐藏批量 toolbar。
  - 调用参数除 `primary_keys` 与 `payload` 外不含整行或业务字段；`context` 由既有 action runtime 注入，不放入 params。
  - 主键保留原类型并按选择顺序去重；任一行主键为 `None` / `""` 时显示错误且 handler 调用数仍为 0。
  - 批量表单 `row=None`，可空文本留空产生 `None`，payload 不按字段名重写。
  - 成功后立即清选择并触发表格刷新；失败后不刷新、不清选择，警告内容包含原始业务错误。
  - 同步路径使用现有同步对话框，已有 event loop 时只使用 `open_dialog_async()`。
  - 多选状态下行内编辑 / 删除显式使用被点击行，不默取其它已选首行。
  - 翻页或手动刷新会清除旧选择，不跨页保留。
- [ ] GREEN：透传选择模式，新增批量按钮与 handler，同步 / 异步均复用空白 update 表单。
- [ ] 验证：`QT_QPA_PLATFORM=offscreen uv run pytest packages/crawler4j/tests/unit/test_ui/test_data_table.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py -q -p no:cacheprovider`，期望全部通过。

## 任务 3：文档、证据和收口

**依赖：** 任务 1、任务 2 均达到 `ready_for_review` 并提供真实测试输出。执行简报：`.factory/workitems/CR-018/task-briefs/task-3-docs-evidence.md`。

**任务切片：**

- 设计方案：把外部需求压缩为本仓通用契约，不复制业务分组规则。
- 接口设计：登记 `API-021`。
- UI 或 `N/A`：N/A；本任务只同步实现事实，UI 验证已在任务 2。
- 测试设计：登记 `TC-069` 对应真实命令和结果。
- 开发：无业务代码。
- 单测：执行全部目标测试与 unit 回归。
- review：独立代码审查与最终审计。
- 集成测试：全量 unit；若环境导致非本变更失败，记录精确失败，不伪造通过。
- 失败断言：缺验证证据、UI N/A 无原因或出现占位语均失败。

- [ ] 更新正式设计、API、测试计划、追踪矩阵、work item 和 memory。
- [ ] 运行目标 ruff、全量 unit、`git diff --check`、`.factory/project.json` JSON 校验。
- [ ] 写入 `.factory/workitems/CR-018/evidence/verification.md`、`reports/implementation.md`、`reviews/code-review-input.md` 和 ledger；独立 reviewer 另行产出 `reviews/code-review.md`。

## 测试策略

- 红灯：分别运行新增 Contracts / scanner 和 Renderer 用例，确认失败来自缺失新契约。
- 绿灯：同一目标用例全部通过。
- 定向回归：四个目标测试文件。
- 邻近回归：`packages/crawler4j/tests/unit/test_sdk/` 与 MMS Hosted UI 相关测试。
- 全量回归：`QT_QPA_PLATFORM=offscreen uv run pytest packages/crawler4j/tests/unit -q -p no:cacheprovider`。
- 静态检查：`uv run ruff check packages/crawler4j-contracts/src/crawler4j_contracts/hosted_ui.py packages/crawler4j-sdk/src/v2_scanner.py packages/crawler4j/src/core/mms/ui/managed_page_renderer.py packages/crawler4j/src/ui/components/data_table.py packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py packages/crawler4j/tests/unit/test_ui/test_data_table.py`、`git diff --check`、`uv run python -m json.tool .factory/project.json`。
- 未运行项：真实 `ctrip_crawler` 业务模块 E2E 与发布包；原因是本 work item 只交付 Core 通用能力，业务接入由来源模块后续执行。仓库未配置 mypy gate，因此不新增工具链。

## 文档同步

- 正式文档：PRD、bulk update 设计、API、实施计划、测试计划、需求 / 接口追踪矩阵。
- `.factory/memory/`：需求、API、任务、测试、变更、追踪和 runtime brief。
- 流水账：`.factory/workitems/CR-018/ledger.jsonl`。

## 评审门

- 计划评审：`approved`
- 任务评审：`pending`
- 验证：`pending`
- 本地提交：`pending`
- 记忆同步：`pending`

## 计划自审

- 规格覆盖：`REQ-012-001..005` 均映射到任务 1 / 2 / 3。
- 占位符扫描：无占位符或未定义对象。
- 发现占位语则失败：通过。
- 缺测试设计则失败：通过。
- UI 写 `N/A` 但无原因则失败：通过。
- 类型一致性：固定参数名为 `context, primary_keys, payload`；Core payload 与 scanner 一致。
- 可构建性：文件、命令和期望结果均已明确。
- Shanforge 门禁：包含 RED/GREEN、evidence、独立 review、memory、ledger 和本地提交。
