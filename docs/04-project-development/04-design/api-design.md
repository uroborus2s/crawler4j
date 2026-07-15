# 接口与契约设计

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 模块开发者  
**上游输入：** `system-architecture.md` | `module-boundaries.md` | 现有 SDK / Contracts / module manifests  
**下游输出：** `docs/04-project-development/05-development-process/implementation-plan.md` | `docs/04-project-development/06-testing-verification/test-plan.md`
**关联 ID：** `API-001`, `API-002`, `API-003`, `API-004`, `API-005`, `API-006`, `API-007`, `API-008`, `API-009`, `API-012`, `API-013`, `API-019`, `API-021`, `API-022`, `API-023`, `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-006`, `REQ-007`, `REQ-008`, `REQ-009`, `REQ-010`, `REQ-012`, `REQ-0400`, `REQ-0401`, `BUG-013`, `CR-005`, `CR-008`, `CR-009`, `CR-010`, `CR-011`, `CR-012`, `CR-014`, `CR-016`, `CR-018`, `CR-020`, `CR-022`, `TASK-024`, `TASK-026`, `TASK-028`, `TASK-030`, `TASK-031`, `TASK-032`, `TASK-033`, `TASK-034`, `TASK-036`, `TASK-040`, `TASK-041`, `TASK-0400`, `TASK-0401`
**最后更新：** 2026-07-15

## `API-001` Root App Entry Contract

| 项目 | 内容 |
|---|---|
| 目标 | 启动桌面应用 |
| 当前真实入口 | `src.ui.app:main` |
| 当前开发入口 | workspace 根执行 `uv run python -m src.ui.app` |
| 打包态前置动作 | Windows 打包态在 GUI 初始化前先执行 Velopack `App().run()`；内嵌 debug worker / debugpy adapter 子进程必须先短路，不参与宿主自更新 bootstrap |
| 当前状态 | 已对齐，需持续回归验证 |
| 关联项 | `BUG-001`, `TASK-002` |

## `API-002` Module Runtime Contract

| 项目 | 内容 |
|---|---|
| Manifest 文件 | `module.yaml` 只保留模块元信息、升级源和 `config_defaults.module` |
| 宿主入口文件 | 模块根 `__init__.py` 仅作为 Python 包入口，不承载运行能力 |
| 必需入口 | `runtime_api: core-native-v2` + 装饰器扫描声明 |
| 标准运行时文件 | 无 `module_runtime.py` 主路径 |
| 可选 hooks | 0.4.0 不提供旧 hook 兼容路径 |
| 环境选择器 | 0.4.0 已移除 `selector_name/env_selector/resource_pool`；运行模板只能显式选择 `env_id` 或引用 `candidates/` 下的 `@env_candidates`；ATM UI 默认提供固定环境选择，只展示当前模块可用的 `READY + BROWSER + 无租约` 环境 |
| 当前实现 | Core 通过 `ModuleRuntimeDescriptorV2` 扫描 `@interface/@component/@workflow/@page/@page_action/@ui_action/@data_table/@data_view/@env_candidates`，不依赖模块自有 assembler |
| Core 扩展入口 | `context.tools.call("<namespace>.<action>", **kwargs)` |
| 生命周期规则 | workflow 是 0.4.0 运行入口；旧 `on_success/on_failure/on_timeout/on_cleanup` hook 不再是模块契约。对象图由 Core 在 `workflow.run(ctx)` 前统一执行可选 `setup(ctx, workflow)`，并在终态统一执行可选 `cleanup(ctx, outcome)`；任务结束、失败、超时或用户中止后的环境统一由宿主回收，环境删除只走环境管理页清理链路 |
| 默认工作流解析 | `context.runtime["workflow"]` -> 单 workflow 自动选择 -> `main_workflow` |
| 发现错误可见性 | descriptor 扫描失败必须暴露具体 Python 文件、符号、异常类型与 traceback 摘要，不能降级为泛化 “not found” |
| Hosted UI 契约 | Core 扫描 `pages/*.py` 与 `pages/<group>/*.py` 中的 `@page(...)` 与 `@ui_action(...)`；`@page(menu=True)` 控制左侧菜单，`DataTable` 仅作为页面内组件，页面数据由 `load_handler` / `query_handler` 返回纯结构化对象，按钮和 CRUD handler 通过 `type="ui_action"` 调用 UI action；表格查询固定为 `HostedDataTableQuery -> HostedDataTableQueryResult` |
| 宿主确认契约 | 当前 0.4.0 模块运行时代码不发送 `TaskSignal`；人工确认若后续需要恢复，必须先在宿主状态机内重新设计，不复用模块信号入口 |
| DevLink 调试语义 | 模块来源为 `DevLink` 时，descriptor 可强制 reload；正式安装模块读操作不做非必要 reload |
| DevLink 普通执行语义 | ATM 普通执行 `DevLink` 模块时注入 `devel_mode=true`；`ModuleService` 对同一个 `TaskContext` 只在首次加载时强制 reload 一次 |
| 升级策略 | 旧模块必须迁移到 `core-native-v2`；当前分支不为 0.3.x 运行薄壳、hooks 或 selector 提供兼容承诺 |
| 当前风险 | 真实站点 E2E 仍未覆盖；动态加载的模块扩展点仍需依赖回归测试保持稳定 |
| 关联项 | `TASK-003`, `TASK-013` |

## `API-008` Hosted Module UI Contract（0.4.0 注解模式）

| 项目 | 内容 |
|---|---|
| 目标 | 模块 UI 不再直接导出 `PyQt6` 页面，而是声明宿主管理页 schema，由宿主统一渲染 |
| Manifest 形态 | `module.yaml` 不声明 UI；`ui_extension` 是已移除字段 |
| 模块 UI 声明入口 | `pages/*.py` 或 `pages/<group>/*.py` 使用 `@page(...)` 装饰页面 load handler |
| 页面路由 | `open_page.page_id` 可以打开任意已注册 `@page`，包括 `menu=False` 的详情页或二级页 |
| 宿主公开控件 | `Page`、`Card`、`Section`、`Text`、`Input`、`Select`、`Button`、`DataTable` |
| `Card` V1 范围 | 纯容器卡片；支持 `title`、`title_align`、`content_align`、`content_vertical_align`、`min_height`、`padding` 与子组件布局 |
| `DataTable` V1 范围 | 页面内复合组件；数据源支持 `binding`、`rows`、`query_handler`；`query_handler` 不接收 `table_id`，必须返回 `HostedDataTableQueryResult`；字段类型支持 `text`、`number`、`int`、`bool`、`select`、`badge`、`actions`；`select` 列可由宿主渲染为工具栏快速筛选，sortable 列可通过表头点击或可见排序控件写入 `query.sort`；CRUD 语义仍由宿主 renderer 适配，不进入共享表格组件内部；`actions` 列中非 `__crud_update__` / `__crud_delete__` 的 action id 由 renderer 调用同名 `@ui_action`，参数按 `crud.primary_key` 从当前行取值 |
| 宿主动作范围 | `Button.action` 正式开放 `reload`、`open_page` 和指向 `@ui_action` 的 `ui_action`；Hosted UI schema 不再接受 `page_action`。页面 / 表格 toolbar 批量导入动作由 `API-019` 单独定义 |
| 明确删除 | `micro_app`、代码型页面脚手架、trust gate / allowlist / `trusted`、`entry`、`core:data_table`、`ui.declare_page`、`ui.declare_data_table`、`PageSpec` |
| 设计输入 | `module-hosted-ui-framework.md` |
| 当前验证基线 | Core / SDK / integration / acceptance 已跑通 `@page` 注解模式定向回归；模块详情页、CLI 和 schema gate 已统一到 `pages/` 页面注册 + `@page(menu=True)` 菜单配置的新契约 |
| 当前状态 | 已本地实现并通过定向验证；真实业务模块接入验证待继续推进 |
| 关联项 | `CR-011`, `TASK-025` |

## `API-019` Hosted UI Batch Import Contract

| 项目 | 内容 |
|---|---|
| 目标 | 为 Hosted UI 页面和表格提供宿主托管批量导入能力 |
| schema 入口 | `Page.toolbar.actions[]` 与 `DataTable.toolbar.actions[]` |
| 动作类型 | `ui_action`、`workflow`、`open_import_dialog` |
| 导入来源 | 宿主导入弹窗支持 `.xlsx` / `.csv` 文件和剪贴板批量粘贴；手工 JSON / 表格行录入为可选增强 |
| 宿主职责 | 读取本地文件或剪贴板、解析表头和行数据、预览、限制文件类型 / 大小 / 最大行数、生成 import payload、脱敏敏感字段日志、展示导入结果 |
| 模块职责 | 接收结构化 payload，执行业务校验、去重、暂存、导入业务表和逐条状态记录 |
| 文件边界 | 模块不得接收本地文件路径、文件句柄或原始二进制内容；宿主传递的 `source_name` 只允许是文件名或来源名称 |
| Payload | `source_type`、`source_name`、`target_type`、`rows[]`；每行包含 `source_row_no`、`business_key`、`payload`、`raw_payload` |
| `@ui_action` 分发 | 宿主把 import payload 作为 `import_payload` 参数传入模块 `@ui_action`；schema 可通过 `submit.payload_param` 改名 |
| workflow 分发 | 宿主通过 ATM 调度 workflow，并把 payload 写入 `ctx.runtime["import_payload"]`；workflow 不声明 parameters，也不能在 renderer 内被直接调用 |
| 结果契约 | 模块返回 `batch_id`、`total_rows`、`staged_rows`、`failed_rows`、`target_type`、可选 `records_page_id` |
| 结果展示 | 宿主展示批次汇总，并可带 `batch_id/target_type` 跳转 `import_data_records` 页面 |
| 安全限制 | 仅允许 `.xlsx/.csv`；默认单文件 10 MB、单次 5000 行；`token/cookie/password/secret/authorization/credential/passwd` 等字段不得写入宿主日志明文 |
| 关联文档 | `hosted-ui-batch-import-design.md` |
| 当前状态 | 已本地实现并通过 `TC-060`：Contracts / SDK / Core / UI / ATM 分发链路已落地；对外发布版本与真实业务模块 E2E 仍待后续补齐 |
| 关联项 | `REQ-010`, `NFR-010`, `CR-016`, `TASK-030`, `TASK-031`, `TASK-032`, `TASK-033`, `TASK-034` |

## `API-021` Hosted UI DataTable Current-page Bulk Update Contract

| 项目 | 内容 |
|---|---|
| 目标 | 让 Hosted UI `DataTable` 在当前已加载页内声明多选并复用 CRUD update 表单批量提交相同字段 |
| 选择模式 | 顶层 `selection_mode=none|single|multi`；省略时为 `single`；刷新、搜索、筛选、排序、翻页和页大小变化清选择 |
| CRUD 声明 | `crud.bulk_update_handler` + `crud.toolbar.bulk_update`；复用 `crud.primary_key` 与非空 `crud.form.update_columns` |
| Handler | `handler(context, primary_keys: list[T], payload: ConcretePayload)`；`T` 必须是具体类型，payload 必须是具体 TypedDict / dataclass 风格类型 |
| Core 参数边界 | 只传保序、类型敏感去重后的 `primary_keys` 和表单 `payload`；不传整行，不访问模块数据库 |
| UI 状态 | 0 行禁用批量编辑；1 行及以上启用；toolbar 单条编辑 / 删除仅 1 行启用；行内动作只处理点击行 |
| 成功 / 失败 | 成功清选择并刷新一次；主键缺失或模块失败时不刷新、保留选择并展示明确错误 |
| 异步要求 | 已有 event loop 时只走 `open_dialog_async()` 和 async UI action，不调用阻塞式 `exec()` |
| 数据 owner | 模块 `@ui_action` 负责业务校验、授权和 `ctx.db` 写入；Core 不实现 `managed_dataset` 批量更新 API |
| 当前范围 | 只支持当前页；不含跨页选择、批量删除、任意 toolbar 表单或具体业务分组规则 |
| 设计文档 | `hosted-ui-datatable-bulk-update-design.md` |
| 验证 | `TC-069`；Task 1 Contracts / SDK `82 passed`，Task 2 Core / UI `38 passed`，两项均通过独立 Spec + Quality Review；Task 3 合并目标集 `120 passed`，Ruff / diff / JSON / docs 结构通过；全量 unit 有 2 个不相关版本文档漂移失败 |
| 当前状态 | 通用实现已完成整体 review、人工确认和 Contracts 0.4.3 / SDK 0.4.4 发布；全量 unit `1134 passed`，PyPI 哈希与隔离安装验证通过。真实业务模块接线和 E2E 仍为独立工作 |
| 关联项 | `REQ-012`, `NFR-012`, `CR-018`, `TASK-036`, `TASK-037`, `TC-070` |

## `API-022` Environment Cookie Ensure Contract

| 项目 | 内容 |
|---|---|
| 目标 | 模块只表达当前环境的完整 Cookie 目标状态，由 Core 原子完成持久化、必要重启、CDP 重连和运行态验证 |
| 公开入口 | `await ctx.tools.call("env.cookie.ensure", env_id=<int>, cookies=[...], reload="restart_if_changed", verify="runtime")` |
| Surface | 只注册到 workflow/page action 使用的 full runtime surface；Hosted UI、环境候选和清理候选 surface 不注册 |
| 输入语义 | `cookies` 是替换后的完整集合，不是 patch；未传 Cookie 必须删除，空列表清空全部 Cookie |
| Cookie 字段 | 必需 `name/value/domain/path/expires/secure/httpOnly`；可选 `sameSite`；`expires` 为 Unix seconds float |
| 并发 | Manager 按宿主 `env_id` 提供共享生命周期锁，覆盖 ensure、普通 start/stop、read/write/stop/start/verify 和 TaskContext 回绑；异常或取消后释放 |
| Provider 边界 | REM 暴露供应商无关的持久化读取/全量替换能力；VirtualBrowser adapter 使用实测 `GET /api/getCookie?id=... -> data[]` 与 `POST /api/updateCookie {id,cookies}`，并执行 `expires ↔ expirationDate` |
| 匹配 | 完整集合、Cookie 标识、value、float Unix seconds 有效期和安全属性严格匹配；额外 Cookie 或任何有效期差异均触发替换 |
| 重启 | 集合变化或运行态不一致时停止浏览器；运行列表查询异常、轮询耗尽或旧 CDP 端口仍可达均失败，不得把未知状态视为已关闭；确认关闭后再启动并连接新 Browser/Context |
| 上下文换代 | stop/start 后，ATM 将新 BrowserHandle 的 page/context 回绑当前 TaskContext 并重新 bind tools；模块不得复用旧 Page |
| 返回 | Mapping 至少包含 `persisted/restarted/browser_ready/runtime_matched` 四个 bool；成功固定 `runtime_matched=True` |
| 失败 | 参数、Provider、写入、回读、停止、端口释放、启动、连接或运行态验证任一步失败均抛异常，不返回部分成功 |
| 安全 | API Key、完整 Cookie value 和 Provider endpoint 名称不进入模块可见异常、日志或返回值；模块不接触 VirtualBrowser provider API |
| 实测证据 | `.factory/workitems/CR-020/evidence/virtualbrowser-cookie-api-probe.md`；一次性环境验证了全量替换、字段映射和空列表清空，环境已删除 |
| 关联项 | `CR-020`, `TASK-040` |

## `API-023` Hosted UI Field Change and Form Reset Contract

| 项目 | 内容 |
|---|---|
| 目标 | 公共 `Input` / `Select` 与 CRUD Form 字段用同一可选 `on_change` 事件触发模块 `@ui_action` |
| Schema | `on_change={"type":"ui_action","name":"<handler>"}`；不接受字符串简写、其它 action type、`params` 或 effect |
| Handler | 固定 `(context, event: HostedFieldChangeEvent)`；SDK scanner 校验引用、签名和事件注解 |
| Form scope | `kind/form_id/mode/values`；`form_id` 是 Core 生成的 opaque handle，不包含真实 UI 对象 |
| Standalone scope | 固定 `{"kind":"standalone"}`，不含可用 Form Handle |
| Reset | `context.tools.call("ui.form.reset", form_id=..., initial_values=...)`；成功返回 `{"ok": True}` |
| Reset 语义 | 重建整张 Form 的 current/initial values，清 dirty/validation；不提交、不调用 CRUD handler、不做业务判断；精确保留假值 |
| 初始化 | create 读取字段 `default`，update 优先读取 row 实际值；长 Form 内部滚动且按钮区保持可见 |
| Form 布局 | `crud.form.layout={"columns":1|2|3,"gap":<可选非负整数>}`；默认一列、逐行填充，窄屏自动降列且对话框不超过屏幕 |
| 安全 | handle 绑定 module/page/renderer-session/form/TTL；非法、过期、关闭或越权统一 `FORM_HANDLE_REJECTED` |
| 并发 | change 绑定 Form revision，旧 reset 返回 `FORM_EVENT_STALE` 并被 renderer 丢弃；action 使用隔离 session |
| 错误 | 非 Form reset 返回 `FORM_SCOPE_UNAVAILABLE`；handler 失败保留当前 Form 并走现有错误展示路径 |
| 版本 | Contracts `0.4.3`、SDK `0.4.4` 本轮不变且不发布；本地 workspace 使用 editable source |
| 设计文档 | `hosted-ui-form-field-events.md` |
| 关联项 | `CR-022`, `TASK-041` |

## `API-009` Module Entity Table View Contract

| 项目 | 内容 |
|---|---|
| 目标 | 在模块 `custom_table` 实体表之上提供装饰器驱动的数据库视图和只读视图能力 |
| 新事实源 | `@data_table` / `@data_view` 装饰器声明 + `.crawler4j/manifest.lock.json` |
| 注册入口 | `data/*.py` 中的装饰器声明；0.4.0 不再接受 `module.yaml.data` 作为运行事实源 |
| 查询接口 | `ctx.db.from_(...)`、`ctx.db.from_("view_id").execute()` |
| SQL 契约 | 模块只能执行由 `@data_view` 注册的 `SELECT/WITH SELECT` SQL；源表通过 `{{resource:<resource_id>}}` 占位引用；禁止未注册 SQL |
| UI 接入 | 模块页面通过内联 `DataTable(query_handler)` 调用 `ctx.db` fluent API 并返回 `HostedDataTableQueryResult`；宿主只负责表格交互与渲染，`table_id` 只作为页面内组件 ID |
| 生命周期 | 宿主在模块加载/安装时校验、同步、建表、建视图、导种子，并在卸载时统一清理 |
| 当前状态 | 已切到装饰器驱动契约；旧 `db.declare_db_view` 和 `module.yaml.data` 运行声明口已退出正式协议 |
| 关联文档 | `module-entity-table-view-design.md` |
| 关联项 | `CR-014`, `TASK-028` |

## `API-012` Decorator-first Object Assembly Runtime（V2 方案）

| 项目 | 内容 |
|---|---|
| 目标 | 0.4.0 新模块运行时从 `module.yaml` 对象图切到代码装饰器，降低模块开发者理解成本 |
| Runtime API | `core-native-v2` |
| 事实源 | `@interface`、`@component`、`@workflow`、`@page`、`@page_action`、`@ui_action`、`@data_table`、`@data_view`；对象依赖和 component 参数可通过 `object_inject` / `object_param` 注解 helper 补充 |
| Manifest 边界 | `module.yaml` 不再声明 interfaces、objects、workflows、tasks、data resources、workflow parameters；只保留模块元信息和宿主级静态配置 |
| Workflow 契约 | workflow 只通过构造函数接收宿主注入对象，不接收 `parameters[]` |
| Component 契约 | component 声明 `implements`、`inject` 和对象创建参数；`inject` 与对象参数可写在装饰器参数、类属性注解或 `__init__` 参数注解上，最终归一为 `InjectSpec` / `ParameterSpec`；对象参数只用于宿主创建对象实例 |
| 对象生命周期 | Core 按运行模板为每个 task/env 创建独立对象图，默认不共享业务对象实例；`workflow.run(ctx)` 前按 component 组合顺序再到 workflow 调用可选 `setup(ctx, workflow)`；workflow 返回成功、返回失败、超时、异常、setup 失败或被用户停止后按 component 依赖反向顺序再到 workflow 调用可选 `cleanup(ctx, outcome)`；`workflow` 与 `outcome.workflow` 为当前 workflow 元信息，`outcome.status` 为 `succeeded`、`failed`、`timed_out` 或 `cancelled`，旧 `aclose()` / `close()` 不再是生命周期契约 |
| Page action 契约 | task 退化为 `@page_action` 浏览器页面操作纯函数；只由 workflow / component 通过 `ctx.run_page_action(...)` 调用，不作为 Hosted UI 用户按钮入口，也不允许在 `@page_action` 内再次调用 `ctx.run_page_action(...)` 拆公共步骤 |
| Data 契约 | 数据表和只读视图由 `@data_table` / `@data_view` 声明，并注册到现有 `ctx.db` 能力 |
| 宿主保留字段 | SDK / Core / Contracts 共享宿主保留字段集合；第一版阻断模块自有数据列声明 `created_at`、`updated_at`，并阻断常见混淆字段 `create_at`、`update_at` |
| SDK 质量门 | 模块项目打开、DevLink 注册、`crawler4j check full`、`crawler4j manifest lock` 和 package build 均必须执行装饰器扫描、对象图校验和数据字段保留名诊断 |
| 运行模板 UI | 根据 workflow 根注入对象递归展示实现选择和对象参数表单，保存为 `object_bindings` / `object_params` |
| 关联文档 | `0.4.0-decorator-object-assembly-requirements.md`, `0.4.0-decorator-object-assembly-architecture.md` |
| 当前状态 | Core / SDK / Contracts 首轮已落地，已支持装饰器参数、类属性注解和 `__init__` 参数注解三种对象装配入口 |
| 关联项 | `REQ-0400`, `TASK-0400` |

## `API-013` Versioned User / Developer Guide Contract

| 项目 | 内容 |
|---|---|
| 目标 | docs-stratego 网站主文档默认展示当前已发布版本，同时保留旧版本使用者指南和开发者指南 |
| 范围 | 仅覆盖 `docs/02-user-guide/` 和 `docs/03-developer-guide/` |
| 版本路径 | `docs/02-user-guide/v<version>/`、`docs/03-developer-guide/v<version>/` |
| 根入口 | `docs/02-user-guide/index.md` 与 `docs/03-developer-guide/index.md` 只作为版本选择页，不承载具体操作步骤 |
| 站点主文档 | `docs/index.md` 的 docs-stratego 导航中，“当前发布版本”必须指向 `site_role=main` 的版本 |
| 开发版入口 | 未发布版本使用 `status=development`、`site_role=preview`，只能出现在“开发中版本”导航组 |
| 历史版本 | 旧版本使用 `status=archived`、`site_role=archive`，目录保留，不删除，不覆盖 |
| 版本元数据 | 每个版本目录包含 `version.yaml`，至少记录 `doc_version/product_version/status/site_role/runtime_api/audience` |
| 发布提升动作 | 新版本发布时，只调整 `version.yaml` 和根导航分组；旧版本目录转入历史入口 |
| 设计文档 | `0.4.0-guide-versioning-architecture.md` |
| 当前状态 | 方案已形成，目录迁移待实施 |
| 关联项 | `REQ-0401`, `TASK-0401` |

## `API-005` Module Config / Runtime / Data Contract

| 项目 | 内容 |
|---|---|
| 静态清单 | `module.yaml`，只承载模块发现、升级源和只读初始化模板 `config_defaults.module`；运行能力来自装饰器 |
| 持久配置 | `config.db.module_config_entries`；模块运行时只通过 `ctx.get_config()` / `ctx.config` 读取 |
| 配置编辑格式 | 模块详情页 `配置` 标签统一使用 QScintilla YAML 编辑器；保存前由独立验证层校验 YAML 语法、顶层映射对象与重复键，数据库仍是事实源 |
| 配置初始化规则 | 仅首次加载模块时按 `module.yaml.config_defaults` 初始化一次；后续升级不自动覆盖，手动恢复默认需用户确认 |
| 运行态元数据 | `ctx.runtime`；当前固定承载 `workflow`、`object_bindings`、`object_params`、`devel_mode`、`creation_params`、`candidates`、`candidate_params`、`env_recycle` |
| 运行中共享内存 | `ctx.state`；仅用于当前一次任务 / workflow 运行内共享变量 |
| 页面 schema | 来自运行时 descriptor 中扫描到的 `@page.schema`；`ui.get_page` 只读访问当前已注册 schema |
| 快照型业务数据 | `@data_table` 统一声明 `managed_dataset` / `custom_table`；其中 `managed_dataset` 实际落在 `data.db.module_datasets`（V3：`record_key` / `run_status` / `record_status`），`custom_table` 落在受控实体表 `module_name_resource_id`，并由装饰器 schema/indexes 描述真实列结构；业务数据统一通过 `ctx.db.from_(...)` / `ctx.db.into(...).replace(...)` 访问 |
| 事件型审计数据 | `data.db.module_audit_events` 独立承载 append-only 审计事件；通过 `ctx.db.audit("dataset")` 访问，不进入 `module_datasets` |
| 短期状态与锁 | `state.db.kv_store`；只承载轻量状态与锁，不再作为正式业务表存储 |
| 当前实现说明 | `ctx.db` 已统一要求资源先由 `@data_table` 注册并进入 manifest lock，再按 `storage_mode` 路由；`@data_table` 默认 `custom_table`，需要旧快照语义时显式写 `storage_mode="managed_dataset"`；`managed_dataset` 不再按名称隐式落库，且只允许单源读取；`custom_table` 继续使用 schema 驱动的受控实体表，并可在装饰器显式声明后联表、分组和聚合。`ctx.db.from_(...).execute()` 没有隐式分页上限，未调用 `limit/offset` 时读取满足条件的全部行；表格和可增长数据源必须显式分页。`@data_view` 只允许引用 `custom_table`。卸载时宿主会按 `cleanup_policy` 统一删除托管记录、删除/保留自定义物理表并在客户端列出高风险清理清单 |
| 关联文档 | `module-config-runtime-data-contract.md` |
| 关联项 | `CR-003`, `CR-012`, `TASK-026` |

## `API-006` Module Audit Event Contract

| 项目 | 内容 |
|---|---|
| 存储表 | `data.db.module_audit_events` |
| 写入接口 | `ctx.db.audit("dataset").append(...)` |
| 查询接口 | `ctx.db.audit("dataset").query(...)` |
| 数据语义 | append-only 审计事件，不再按整包 JSON 覆盖历史 |
| 支持字段 | `dataset`, `event_type`, `entity_key`, `run_id`, `previous_status`, `next_status`, `result`, `reason`, `payload`, `created_at` |
| 查询维度 | `dataset / entity_key / event_type / run_id / time range / limit / offset / order` |
| UI 边界 | Hosted UI 只负责渲染页面和表格组件，不承担审计事件编辑语义 |
| 当前范围 | 审计能力融入 `ctx.db`；模块开发者侧不再暴露旧 `ctx.tools.call("db.*")` 工具 |
| 关联文档 | `module-config-runtime-data-contract.md`, `reference-core-capabilities.md` |
| 关联项 | `REQ-008`, `CR-008` |

## `API-003` SDK / Contracts Package Contract

| 项目 | 内容 |
|---|---|
| SDK 包名 | `crawler4j-sdk` |
| Contracts 包名 | `crawler4j-contracts` |
| CLI 入口 | `crawler4j_sdk.cli.commands:main` |
| 当前能力 | `crawler4j-contracts` 提供 `TaskContext`、`TaskResult`、`ctx.db`、v2 装饰器和 Hosted UI schema helper；`crawler4j-sdk` 只提供 CLI、模板、静态扫描、manifest lock、迁移报告、打包与宿主联调辅助 |
| 当前状态 | 0.4.x SDK/Contracts 只服务 Core 0.4.0 / `core-native-v2`；不再导出 `ModuleAssembler`、`TaskScript`、`TaskFlow`、`env_selector` 或运行时 owner helper |
| 关联项 | `REQ-003`, `REQ-006` |

补充运行时协议：

- 数据库唯一入口固定为 `ctx.db`
- 标准浏览器交互固定为 `ctx.tools.call("browser.*", ...)`
- `ctx.page` 保留为浏览器读取和宿主未覆盖能力的直接句柄，不再作为正式拟人化交互主路径

## `API-004` Release Metadata Contract

| 项目 | 内容 |
|---|---|
| 根应用版本事实源 | `packages/crawler4j/pyproject.toml` |
| 运行时版本读取 | `packages/crawler4j/src/core/system/version_service.py` 从包元数据或 `packages/crawler4j/pyproject.toml` 解析 |
| 最近正式发布 | Git tag |
| 子包版本 | `packages/crawler4j-sdk/pyproject.toml`, `packages/crawler4j-contracts/pyproject.toml` |
| Windows 发布元数据 | `scripts/package_windows_release.py` 负责把 `feed_url / pack_id / channel` 收口到 Windows 宿主目录内的 `crawler4j.update.json`，供 Velopack 运行时读取 |
| 桌面更新后端 | macOS 打包态走 Sparkle；Windows 打包安装态走 Velopack；统一对 UI 暴露为 `UpdateService` |
| 发布文档 | `docs/04-project-development/07-release-delivery/version-governance.md`, `docs/04-project-development/07-release-delivery/release-notes.md` |
| 当前状态 | 已收口：当前工作区版本与最近正式发布已被明确区分 |
| 关联项 | `CR-001`, `TASK-004` |

## `API-007` Env Candidates Service Queue Contract（0.4.0）

| 项目 | 内容 |
|---|---|
| 适用场景 | 模块需要按业务账号、状态、等级、注册时间等实时筛选可用环境，并让 Service Job 在候选暂时不可用时等待 |
| 目标语义 | `运行中 + 等待中 = 目标并发`；资源不足属于正常等待，不属于失败 |
| 进入队列前提 | 只有 `JobType.SERVICE + AcquisitionConfig.mode=select + candidates 非空` 时才进入候选等待语义；固定 `env_id` 直接派发，不排队 |
| 固定环境 UI | 运行模板选择已有环境时默认保存固定 `env_id`；候选列表只包含未归属或归属当前模块的 `READY + BROWSER + 无租约` 环境，不展示其他模块环境或非浏览器环境 |
| 候选声明 | 模块在 `candidates/*.py` 中声明 `@env_candidates(name=...)` 同步纯函数，运行模板的 `AcquisitionConfig.candidates` 只能引用已声明函数 |
| 模块开发者职责 | 在候选纯函数中实时读取模块数据，返回 env id 列表或 `EnvCandidates` 链式查询；账号黑名单、注册时间、会员等级等过滤都写在这个函数里 |
| 唯一开发路径 | 不提供 `module.yaml.resource_pools[]`、资源池资格卡片、资源池同步任务或 `env.*resource_pool*` 工具；0.4.0 不兼容 `selector_name/env_selector/resource_pool` |
| 宿主职责 | 在只读 `ctx.db`、无工具面的候选运行面执行纯函数，按返回顺序筛选 `READY + BROWSER + 无租约` 环境，租约成功后再次求值确认候选仍有效，并维护 FIFO 等待与超时收口 |
| 候选组合 | `EnvCandidates` 支持 `filter()`、`exclude()`、`intersect()`、`union()`、`minus()`、`order()`、`limit()`、`list(ctx)` 链式调用；每个函数既能直接返回查询对象，也能被组合复用 |
| 容量变化触发 | 环境释放、新环境可分配、异常/暂停环境恢复、作业激活/更新，以及主 async loop 上的轻量异步巡检都会触发候选容量重算 |
| 黑号规则 | 黑号、封禁、账号状态变化写入模块业务表；候选纯函数实时过滤这些状态，不同步到宿主资源池 |
| 候选竞争语义 | 候选环境如果在租约阶段被其他任务抢走，或租约后重算发现已不在候选集合，当前任务回到等待席位，不直接记失败；真实异常进入失败收口 |
| 等待状态口径 | 候选等待复用底层 `TaskStatus.PENDING`；UI 展示为 `等待环境`，等待中的 `task.message` 为 `等待环境候选可用: <candidates>` |
| 等待超时口径 | `wait_timeout` 同时用于环境租约获取与候选等待席位收口；候选等待从第一次写下 `waiting_since` 开始计时，`wait_timeout=0` 时当前不会自动超时收口；失败文案为 `等待环境候选超时: <candidates> (<seconds>s)`，且与 `execution.timeout` 分离 |
| 环境回收口径 | 任务终态后的环境处置统一为回收；候选队列只从 `READY + BROWSER + 无租约 + 已由同模块声明绑定` 的环境中取数 |
| `env_id` 口径 | 候选函数返回的 `env_id` 是宿主 `environments.id` 主键；候选函数执行时 `TaskContext.env_id` 固定为 `0`，不应用于表达候选关系 |

## `API-016` Env Cleanup Candidates Contract（0.4.0）

| 项目 | 内容 |
|---|---|
| 适用场景 | 宿主需要清理孤岛环境、模块未认领环境、owner 模块缺失环境，或模块根据自己的账号表、黑号状态、过期策略、长期未使用规则声明一批可以清理的环境 |
| 目标语义 | 模块只声明“已绑定但业务上可丢弃”的 env id；宿主负责发现 host 侧候选、预览、确认、二次安全校验、删除和结果反馈 |
| 候选声明 | 模块在 `cleanups/*.py` 中声明 `@env_cleanup_candidates(name=...)` 同步纯函数 |
| 模块开发者职责 | 在清理候选纯函数中实时读取模块数据，返回 env id 列表或 `EnvCandidates` 链式查询；不要在模块内调用删除环境操作；需要被宿主识别为“已认领环境”的业务表必须通过 `@data_table(..., env_binding_field="env_id")` 声明绑定字段 |
| 宿主职责 | 在只读 `ctx.db`、无工具面的清理候选运行面执行纯函数，并只接受 `host.env_claim.owner_module == module`、`state == claimed` 且仍存在于模块 `env_binding_field` 表中的候选；同时扫描没有 owner、owner 模块缺失、`pending/abandoned` 且未被绑定的环境 |
| 安全门 | 删除前必须再次读取 REM 当前状态，只允许删除 `READY/PAUSED`、无租约、无关联任务、无活跃 task 引用、未被运行模板固定引用的环境；`BUSY/RUNNING/CREATING/TERMINATING` 必须跳过 |
| 执行动作 | 删除只通过宿主 REM `EnvironmentManager.destroy_env()` 执行，外部 provider 删除失败时保留数据库记录并返回失败原因 |
| 与 `API-007` 的关系 | 复用 `EnvCandidates` 查询 DSL，但不复用 `@env_candidates` 注册入口；运行候选和清理候选是两个独立 descriptor bucket |

## 设计结论

- 本项目的关键“接口”不是 HTTP API，而是运行入口、模块契约、SDK/Contracts 包接口和发布元数据接口。
- 模块开发时还必须把“配置 / 运行态 / 单次运行内内存 / 业务数据 / 短期状态”视为不同契约，不能混用。
- 当前版本治理规则已经明确：根应用 `pyproject.toml`、运行时版本读取、最新正式 tag 和子包版本线各自职责清晰。

## 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-07-13 | 新增 `API-022`，登记 `env.cookie.ensure` 完整集合全量替换、Provider 实测协议、严格重启、TaskContext 回绑和敏感信息边界 | Codex |
| 2026-07-10 | 新增 `API-021`，登记 Hosted UI DataTable 当前页选择、CRUD 批量 handler、SDK 类型 gate、Core 调用边界与模块数据 owner | Codex |
| 2026-06-19 | 将 `API-019` 更新为已本地实现，记录 Hosted UI toolbar 导入契约、宿主解析弹窗、payload 分发、结果展示和 `TC-060` 验证状态 | Codex |
| 2026-06-19 | 新增 `API-019`，登记 Hosted UI 批量导入的 toolbar schema、宿主导入弹窗、标准 import payload、结果展示和敏感字段脱敏契约 | Codex |
| 2026-05-01 | 收口环境处置为宿主边界：模块运行时代码不再导入或发送 `TaskSignal` / `EnvAction`，任务终态后环境统一回收，环境删除只由环境管理页清理链路执行，并通过 `host.env_claim` + `env_binding_field` 区分孤岛、未认领和模块业务清理候选 | Codex |
| 2026-04-30 | 清理旧生命周期 hook 运行链，`RunProfile.execution.hooks_module`、`ModuleService.call_hook()` 与 `prepare_env/init_env/before_run/on_*` 不再属于 0.4.0 契约 | Codex |
| 2026-04-30 | 新增 `API-016`，提供 `cleanups/` + `@env_cleanup_candidates` 批量环境清理候选契约，复用 `EnvCandidates` DSL 但隔离运行候选和删除语义 | Codex |
| 2026-04-30 | `API-007` 从固定资源池同步方案改为 `candidates/` + `@env_candidates` 纯函数实时候选方案，删除资源池资格卡片和同步工作流口径 | Codex |
| 2026-04-30 | 新增 `API-013`，登记 docs-stratego 下使用者指南和开发者指南按版本分流、主文档指向当前发布版本、历史版本保留的契约 | Codex |
| 2026-04-30 | 收口 `API-002/API-003/API-005/API-007/API-008/API-009` 到当前 0.4.0 破坏性实现：无 `selector_name/env_selector`、无 `PageSpec/ui_extension`、无 `module.yaml.data` 事实源，运行能力只来自装饰器和 manifest lock | Codex |
| 2026-04-30 | 新增 `API-012`，登记 0.4.0 装饰器对象装配运行时、SDK 打开阶段诊断和宿主保留字段校验契约 | Codex |
| 2026-04-30 | 扩展 `API-012`：登记 `object_param` / `object_inject` 注解 helper 与统一元数据归一规则 | Codex |
| 2026-04-24 | 将 Hosted UI 页面契约修正为 `pages/` 注册可路由页面、`ui_extension.pages[]` 只控制左侧菜单，并允许 `open_page` 跳转到非菜单详情页 | Codex |
| 2026-04-22 | 将 `API-008` 从“设计已定未落地”更新为 hosted page V1 已本地实现：`ui_extension.pages[]`、`ui.declare_page`、宿主页渲染器与 SDK CLI 已同步完成 | Codex |
| 2026-04-22 | 新增 `API-008`，登记模块宿主管理页与最小化 UI 框架的目标契约 | Codex |
| 2026-04-22 | 补记 root app 在 Windows 打包态的 Velopack 启动前置动作，并将 Windows `crawler4j.update.json` 与统一 `UpdateService` 后端分派纳入发布元数据契约 | Codex |
| 2026-03-26 | 初始接口与契约设计摘要 | Codex |
| 2026-03-31 | 增补模块根入口自动托管的契约演进设计 | Codex |
| 2026-04-08 | 补记 Hosted UI 本地声明 hook 与 DevLink 刷新调试语义 | Codex |
| 2026-04-15 | 将 Core 扩展能力收敛到 `TaskContext.tools` 统一工具接口 | Codex |
| 2026-04-15 | 历史记录：曾固化 `on_cleanup` 终态规则，并补记 `TaskSignal` 为正式流程信号；当前 0.4.0 已移除生命周期 hook 运行链 | Codex |
| 2026-04-16 | 补记 `TaskSignal.wait_for_confirmation` 的结构化确认面板协议、任务快照持久化与 `task.signal` 事件 | Codex |
| 2026-04-16 | 补记 `ModuleAssembler` 发现错误可见性，以及 DevLink 普通执行的一次性 reload 语义 | Codex |
| 2026-04-17 | 增补 `API-005`，收口模块配置、运行态、共享内存与数据表契约 | Codex |
| 2026-04-18 | 新增 `API-006`，将模块快照数据与审计事件拆成两条正式持久化契约 | Codex |
| 2026-04-19 | 历史记录：曾新增固定环境池 Service Job 的等待队列与资源池资格卡片契约；该方案已在 2026-04-30 被 `@env_candidates` 纯函数候选方案取代 | Codex |
| 2026-04-19 | 历史记录：曾落地 `resource_pool` 与资源池资格能力；该运行契约已在 0.4.0 当前分支移除 | Codex |
| 2026-04-26 | 历史记录：曾要求 `module.yaml.resource_pools[]` 声明资源池；该 manifest 字段已在 0.4.0 当前分支作为已移除字段拒绝 | Codex |
| 2026-04-26 | 刷新 `API-005`：模块配置页切换为 QScintilla YAML 编辑器，并把 YAML 格式校验、顶层映射校验与重复键校验收口到独立验证层 | Codex |
| 2026-04-21 | 刷新 `API-005` 的文档元数据，确认 `module_datasets` 逐行持久化已进入正式契约口径 | Codex |
| 2026-04-23 | 刷新 `API-005`：移除 `module_dataset_manifests`，`managed_dataset` 只保留 `module_datasets` 作为记录事实源 | Codex |
| 2026-04-23 | 刷新 `API-005`：新增 `module_data_resources`、`managed_dataset/custom_table` 两种存储模式、`module_datasets` V3 记录状态字段与 `db.declare_data_resource` 契约，并补记卸载清理策略 | Codex |
| 2026-04-23 | 新增 `API-009`，正式登记模块实体表视图与分析查询能力设计 | Codex |
