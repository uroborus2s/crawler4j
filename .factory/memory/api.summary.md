# API Summary

- `API-001`: Root desktop app entry contract remains `src.ui.app:main`.
- `API-002`: 模块正式运行时契约已切到 `core-native-v1`。Core 只接受 `module.yaml` + 宿主扫描协议：`tasks/*.py -> TASK/execute`、`workflows/*.py -> WORKFLOW/run`、`hooks/*.py -> handle`、`env_selectors/*.py -> SELECTOR/select`、`pages/*.py` / `pages/<group>/*.py -> PAGE/handler`。缺少 `runtime_api: core-native-v1` 或仍依赖旧运行薄壳的模块会被直接拒绝加载。
- `API-003`: `crawler4j-sdk` 现只提供 CLI、脚手架、校验和开发辅助，不再导出运行时 owner 能力；`crawler4j-contracts` 负责共享契约类型与 Hosted UI 归一化 helper。
- `API-004`: Release metadata contract is aligned across app `pyproject.toml`, runtime version service, child package versions, and release docs.
- `API-005`: 模块配置、运行态和数据边界已稳定：`module.yaml` 承载静态清单与 `config_defaults` 模板，当前配置落到 `config.db.module_config_entries`，`ctx.runtime` 承载宿主执行态元数据，`ctx.state` 仅用于单次运行内共享内存。
- `API-006`: 模块数据开发者入口已统一为 `ctx.db` fluent API；快照与实体表必须先登记到 `module.yaml.data.resources[]`，再通过 `ctx.db.from_(...)` / `ctx.db.into(...).replace(...)` 访问；审计历史通过独立 `ctx.db.audit(...).append/query` 访问 `data.db.module_audit_events`，不进入 `module_datasets`。旧 `ctx.tools.call("db.*")` 工具面不再作为模块接口。
- `API-007`: 固定环境池 Service Job 契约已本地实现：`resource_pool`、环境候选、资格卡片与等待席位都由宿主负责；环境选择器返回 `None` 时，是否等待取决于是否配置了 `resource_pool`。
- `API-008`: Hosted UI 正式契约收口为 `PageSpec` + `ui_extension.pages[]`。页面 schema 顶层必须是 `Page`，公开组件固定为 `Page`、`Section`、`Text`、`Button`、`DataTable`；页面数据与查询通过页面 handler 承接。
- `API-009`: 模块实体表视图与分析查询能力已切到 manifest 驱动：`module.yaml.data.views[]` / `queries[]` 联合 `data/sql/views/*.sql` / `queries/*.sql` 注册视图和命名查询，运行时统一通过 `ctx.db.from_(...)` / `ctx.db.named(...).bind(...).execute()`；模块代码禁止执行未注册 SQL。
- `API-010`: 宿主已有环境导入契约已落地：REM 以 `(provider, name)` 判定环境唯一性，环境管理页按来源环境名称拉取“来源有、本地无”的环境并导入；执行时宿主保证 `ctx.env_id`、`ctx.page` 可用，并在 `ctx.runtime.creation_params` 中写入 `provider`、`name` 与 `import_mode="existing_env"`；`module.yaml.workflows[].host_scenarios` 可选声明 `existing_env_import`，仅用于风险提示，不构成执行门禁。
- `API-011`: Workflow 运行参数契约已落地：模块可在 `module.yaml.workflows[].parameters[]` 声明 `string/text/integer/number/boolean/enum` 参数；宿主运行模板页按选中 Workflow 动态渲染控件，并把结果写入 `RunProfile.execution.params`，运行时继续通过 `ctx.runtime.execution_params` / `ctx.runtime.params` 进入模块。
- `API-012`: 0.4.0 `core-native-v2` 目标契约已形成方案：运行能力事实源切到代码装饰器，`@interface/@component/@workflow/@page_action/@data_table/@data_query` 由 Contracts 提供；Core 扫描元数据并按运行模板 `object_bindings/object_params` 为每个 task/env 装配独立对象图；SDK 负责模板、模块打开阶段诊断、`check full`、迁移与 `.crawler4j/manifest.lock.json`，并前置阻断 `created_at` / `updated_at` / `create_at` / `update_at` 等宿主保留或混淆字段。
- `API-013`: docs-stratego 下的使用者指南和开发者指南版本契约已形成方案：`02-user-guide/v*/` 与 `03-developer-guide/v*/` 物理隔离不同版本；站点主文档指向当前已发布版本，旧版本保留为历史入口，未发布版本只作为开发版预览。
