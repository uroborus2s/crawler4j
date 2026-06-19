# 项目压缩运行卡

- 生成时间：2026-06-16 00:00:00
- 负责人：AI 软件工厂
- 项目：crawler4j
- 当前阶段：IMPLEMENTATION
- 当前模式：Default
- 技术画像：Crawler4j Model 项目画像
- 技术栈：python + crawler4j core + crawler4j-contracts + crawler4j-sdk CLI
- 活跃工作项：21
- 阻塞项：0
- 开放风险：1
- 当前源码版本基线：`crawler4j 0.4.16`、`crawler4j-sdk 0.4.2`、`crawler4j-contracts 0.4.2`；最近正式 Git tag：`v0.2.0`
- 当前 PyPI 发布状态：`crawler4j-contracts 0.4.0` 重发曾被 PyPI 拒绝，因为对应 wheel 文件名曾上传后删除且不可复用；SDK / Contracts 已提升到 `0.4.2`，并已按 `contracts -> sdk` 顺序发布到 PyPI；根应用提升到 `0.4.16`，用于修复来源代理同步匹配规则，绑定 IP 表时只按 `host + port` 唯一命中，不再比较协议、用户名或密码。
- 当前 0.4.x 边界：本分支只支持 Core 0.4.0 / `core-native-v2`，SDK 与 Contracts 已破坏性升级；0.3.x SDK / Contracts / 旧开发方式在 0.3.x 分支维护，不在当前分支兼容。
- 当前 0.4.x SDK 初始化入口：新手优先使用 `uvx --from crawler4j-sdk crawler4j module init` 交互式输入模块名与 `owner/repo`，非必填项走默认值；脚本化/资深开发者仍可完整传参执行。
- 当前 0.4.x 模块根目录固定入口：`module.yaml` 只放静态清单，`.crawler4j/manifest.lock.json` 是 SDK 生成扫描快照；`interfaces/` 放 `@interface`，`objects/` 放 `@component`，`workflows/` 放 `@workflow`，`tasks/` 放 `@page_action` 浏览器页面操作，`data/` 放 `@data_table/@data_view`，`pages/` 放 `@page` 与 `@ui_action` Hosted UI 用户操作，`candidates/` 放 `@env_candidates`，`cleanups/` 放 `@env_cleanup_candidates`。详细目录说明维护在 `docs/03-developer-guide/v0.4.0/module-structure.md`，DDD 与代码边界规则维护在 `docs/03-developer-guide/v0.4.0/architecture-rules.md`。
- 当前 0.4.x ATM 运行模板环境选择：选择已有环境默认使用 `指定环境` 并写入固定 `env_id`；固定环境下拉只展示当前模块可用的 `READY + BROWSER + 无租约` 环境，且环境未归属或 `host.env_claim.owner_module` 等于当前模块。`@env_candidates` 仍用于账号状态、黑名单、等级等业务条件动态筛选，以及 Service Job 的候选等待队列。
- 当前 0.4.x 已有环境导入：导入 workflow 必须通过 `@workflow(..., host_scenarios=["existing_env_import"])` 声明；导入对话框和导入服务只允许选择该场景 workflow。多环境导入会给同批 task 写入 `ctx.runtime["creation_params"]["import_group_id"]`。模块读取当前环境代理统一调用 `await ctx.tools.call("env.get_proxy")`，返回 IP 池条目 ID、host、port、username、password、proxy URL 等只读快照；`ProviderEnvInfo` 表示从外部 provider 拉到的来源环境信息，当前包含 `name/external_id/status/kind/metadata/proxy_config`，不是独立持久表。新导入环境只有在来源代理的 `host + port` 唯一命中 IP 表时才把绑定写入 `Environment.proxy_config.pool_id/ip_entry_id`，不再比较协议、用户名或密码；VirtualBrowser 来源代理解析优先使用结构化 `host/port/protocol/user/pass`，`proxy.url` 只作缺少结构化地址时的兜底，因此不会把 `127.0.0.1:本地端口` 本地转发 URL 作为绑定源。历史已导入环境可在环境管理页点击“同步来源代理”回查指纹浏览器当前代理，按 `host + port` 唯一命中 IP 表时绑定条目，未命中 IP 表时跳过或清除本地错误绑定，不修改外部指纹浏览器代理。环境管理列表“绑定 IP”列只显示已关联 `ip_entry_id` 的 IP 表绑定，密码不在列表中展示。
- 当前 0.4.x 源码目录扫描：manifest lock、DevLink/源码预检和 SDK 打包文件收集先跳过 `.venv/`、`dist/`、`build/`、`.git/`、缓存目录与 `*.egg-info/`，再对真实模块文件执行 symlink 拒绝；ZIP 包内 symlink 和路径穿越仍保持拒绝。
- 当前 0.4.x 对象装配入口：`@component/@workflow` 的 `inject` 与 component 对象参数可继续写在装饰器参数里，也可通过类属性或 `__init__` 参数上的 `Annotated[..., object_inject(...)]` / `Annotated[..., object_param(...)]` 声明；Contracts、SDK scanner、Core descriptor 已统一归一到 `InjectSpec` / `ParameterSpec`。`object_param` 参数类型覆盖 `string/text/integer/number/boolean/enum/array/object/json/date/datetime/time/url/path/secret`，结构化参数通过 `schema` / `item_schema` 描述。ATM 运行模板 UI 使用公共 `ObjectGraphTree`，以 `workflow -> interface 绑定行 -> 子 interface/参数` 树形展示对象图；绑定行左侧显示 interface 中文 `label(name)`，右侧下拉框显示 component 中文 `label(name)`，interface 选择写入 `object_bindings`，component 创建参数写入 `object_params`。
- 当前 0.4.x 数据表/视图入口：`module.yaml.data` 不是正式事实源，模块数据表和只读视图只由 `@data_table` / `@data_view` 进入 manifest lock 后同步；`ctx.db.describe(source)` 以逻辑数据源名读取宿主归一化契约，返回 `columns/system_fields/writable_fields/required_fields/read_only_fields` 等字段；`ctx.db.from_(...).execute()` 没有隐式分页上限，未调用 `limit/offset` 时读取满足条件的全部行；`@data_table` 默认 `custom_table`，主键由 `record_key_field` 指向 schema 字段，integer 主键可声明 `auto_increment=True` 并通过 `ctx.db.into(...).add(...)` 省略 id 新增；旧快照表语义必须显式写 `storage_mode="managed_dataset"` 并继续落到 `data.db.module_datasets`，支持单源 `where` 后 `count(*)` 统计；`@data_view` 只允许引用 `custom_table` 并由宿主创建只读 SQLite view。
- 当前 0.4.x Hosted UI DataTable 交互：`type="select"`、带 `options` 且 `searchable=True` 的列由 Core `SkyDataTable` 渲染为工具栏快速筛选，下拉值写入 `HostedDataTableQuery.params[column.key]`；`不限`、`全部`、`all`、`__all__` 和空值会清除对应筛选。启用排序且存在 `sortable=True` 列时，Core 同时保留表头点击排序，并提供可见排序字段/方向控件，两者同步同一份 `query.sort`。Renderer 调用 query handler 前会合并页面导航参数和表格 params，表格显式筛选同名优先。`actions` 列点击后由 renderer 处理：`__crud_update__` / `__crud_delete__` 保持 CRUD 内置流程；其他 action id 会先读取行内 action spec，若有 `name` 则调用该同名 `@ui_action`，若有 `params` 则按 binding/value 解析当前行生成参数；没有显式 `params` 时才按 `crud.primary_key` 从当前行生成单个命名参数。
- 当前 0.4.x Hosted UI 批量导入：`REQ-010` / `API-019` / `CR-016` 和 `TASK-030` ~ `TASK-034` 已完成本地实现并通过 `TC-060`。页面 / `DataTable` toolbar 可声明导入按钮，宿主读取 `.xlsx/.csv` 文件、剪贴板 CSV/TSV 或手工 JSON 并解析为 import payload，模块只接收结构化行数据；宿主限制文件类型、大小和最大行数，并对 token/cookie/password 等敏感字段脱敏。`@ui_action` 默认接收 `import_payload`，workflow 通过 `ctx.runtime["import_payload"]` 接收，模块返回批次汇总后宿主可跳转 `import_data_records`。对外发布版本与真实业务模块 E2E 仍待后续收口。
- 最近交接包：无
- 最近快照：无
- 备注：当前 0.4.0 正式方案为 `core-native-v2` 装饰器对象装配。运行能力事实源是代码装饰器；workflow 不声明 parameters，只接收宿主装配对象；component 参数只用于对象创建；task 退化为 `@page_action` 浏览器页面操作纯函数，且只由 workflow/component 通过 `ctx.run_page_action(...)` 调用，运行时拒绝 `page_action -> page_action` 嵌套；Hosted UI 页面统一由 `pages/*.py` 或 `pages/<group>/*.py` 中的 `@page(...)` 声明，`@page(menu=True)` 控制左侧菜单，`@page(schema=...)` 可用 `PageSchema` 标注，Hosted UI 按钮、CRUD handler 和表单提交统一调用 `@ui_action` 且 schema 不再接受 `page_action`，CRUD 的 create/update/delete handler 参数由 `crud.form.*` 与 `crud.primary_key` 生成；内联表格查询固定为 `query_handler(context, query: HostedDataTableQuery) -> HostedDataTableQueryResult[RowT]`，`DataTable.table_id` 仅是 UI 组件实例 ID，不传给查询 handler，`query.search_fields` 只由显式 `searchable=True` 的列推导，`query.sort` 只保留显式 `sortable=True` 的列，未声明列默认不可搜索、不可排序，`query.to_query(...)` 使用单字段 `search_transform/sort_transform/filter_transform` 构造 rows/count 查询回调并返回 `(total, rows)`，`query.to_result(...)` 与 `HostedDataTableQueryResult.from_query(...)` 可把仓储记录归一化为 UI 表格结果；`module.yaml.ui_extension` 与 `PageSpec` 已退出正式契约；旧生命周期 hooks、`TaskSignal` 与 `EnvAction` 已退出当前运行链，Core 不再提供 `RunProfile.execution.hooks_module`、`ModuleService.call_hook()`、`prepare_env/init_env/before_run/on_*`、模块信号确认或模块环境处置入口。模块流程控制只通过 workflow 主体返回 `TaskResult`，workflow/component 可选实现 `setup(ctx, workflow)` 做运行前准备，可选实现 `cleanup(ctx, outcome)` 做终态日志、审计或资源释放，且对象 cleanup 不设置宿主固定执行超时；`workflow` 和 `outcome.workflow` 保存当前 workflow 元信息，`outcome.status` 覆盖 `succeeded/failed/timed_out/cancelled`。环境选择统一由 `candidates/*.py` 中的 `@env_candidates` 同步纯函数声明，函数返回 env id 列表或 `EnvCandidates` 链式查询，Core 每次调度实时求值，不维护资源池同步快照；任务终态后的环境统一由宿主回收，创建环境会先写入 `host.env_claim(pending)`，终态按 `@data_table(..., env_binding_field="env_id")` 扫描模块业务表并标记 `claimed/abandoned`，同时宿主会在任务终态按绑定字段把当前 env id 对应且仍为 `占用中` 的托管业务行 `run_status` 兜底释放为 `不占用`。批量环境清理由环境管理页 `清理环境` 统一触发：宿主扫描孤岛、未认领、owner 模块缺失环境，并合并 `cleanups/*.py` 中的 `@env_cleanup_candidates` 声明的同模块、已认领、已绑定且业务上可丢弃候选，预览确认后在 REM 二次安全校验下执行 `destroy_env()`。`TaskContext` 不再提供 `screenshot()` 或 `run_subtask()`；Core 为每个 task/env 创建独立对象图，SDK/Contracts 负责装饰器、扫描、校验、迁移和 manifest lock。`crawler4j-contracts` 承载共享运行时契约、`TaskOutcome` / `WorkflowLifecycleInfo`、`ctx.db` fluent API、`EnvCandidates` DSL 与 Hosted UI schema 归一化 helper；`crawler4j-sdk` 仅保留 CLI、脚手架、校验与开发辅助，不再导出 `ModuleAssembler`、`TaskScript`、`TaskFlow`、`env_selector`、资源池运行时 helper 或任何运行时 owner 身份。模块运行时代码只允许依赖 `crawler4j-contracts`；数据库唯一开发者入口为 `ctx.db`，旧 `ctx.tools.call("db.*")` 会被 SDK AST 扫描拒绝且运行时不注册；非数据库宿主能力仍走 `ctx.tools.call(...)`。docs-stratego 指南版本分流方案只对 `02-user-guide` 与 `03-developer-guide` 建立版本目录，网站主文档指向当前已发布版本，历史版本保留，未发布版本只做预览。

## AI 最小读取顺序

1. 先读本文件 `/.factory/memory/runtime-brief.md`
2. 再读 `/.factory/memory/role-charter.project.md`
3. 再读 `/.factory/project.json`
4. 再读 `/.factory/memory/motivation-state.md`、`/.factory/memory/autonomy-rules.md`、`/.factory/memory/evolution-baseline.md`
5. 再读当前阶段核心文档
6. 只有需要背景解释时，才读人类长文档

## 当前阶段核心文档

- `docs/01-getting-started/index.md`
- `docs/03-developer-guide/index.md`
- `docs/04-project-development/05-development-process/implementation-plan.md`
- `docs/04-project-development/04-design/technical-selection.md`
- `docs/04-project-development/04-design/system-architecture.md`
- `docs/04-project-development/04-design/api-design.md`
- `docs/04-project-development/04-design/module-config-runtime-data-contract.md`

## 必守规则

- 不跳阶段。
- 代码类工作必须走 PR 闭环后再关单。
- 任何已接受变更都要同步代码、文档、测试、`.factory/memory/`。
- 遇到阻塞、空转或质量漂移时，优先执行 `factory-dispatch recovery`。
- 发现问题时优先做模式级修复，再把有效做法沉淀到 `evolution-baseline.md`。
- 实现前优先读取 `docs/04-project-development/04-design/technical-selection.md`。

## 当前推荐动作

- `python3 ../../AiProject/shanforge/scripts/factory-dispatch session --project "." --owner "AI 软件工厂"`
- `python3 ../../AiProject/shanforge/scripts/factory-dispatch board --project "." --owner "AI 软件工厂" --focus "当前协作焦点"`
- `python3 ../../AiProject/shanforge/scripts/factory-dispatch doctor --project "." --owner "AI 软件工厂" --scope full`

## 当前前 5 个活跃工作项

- `TASK-028-implement-module-entity-table-view-query-capability` TASK-028 实现模块实体表视图与分析查询能力 | 状态：DONE | 负责人：Codex
- `TASK-027-implement-hosted-ui-master-detail-row-navigation` TASK-027 Hosted UI 主从表导航 | 状态：DONE | 负责人：Codex
- `TASK-026-implement-module-data-resource-storage-modes` TASK-026 模块数据资源统一登记与存储模式 | 状态：DONE | 负责人：Codex
- `TASK-025-implement-hosted-module-ui-framework` TASK-025 实现模块宿主管理页框架 V1 | 状态：DONE | 负责人：Codex
- `TASK-013-stabilize-module-root-entry-shim-and-sdk-assembler` TASK-013 旧模块入口托管方案历史任务；现已被 `core-native-v1` 宿主扫描协议取代 | 状态：DONE | 负责人：Gemini
