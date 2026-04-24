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
- `API-010`: 宿主已有环境导入契约已落地：REM 以 `(provider, provider_env_id)` 作为外部环境唯一键，环境管理页可从 provider 拉取“来源有、本地无”的环境并导入；执行时宿主保证 `ctx.env_id`、`ctx.page` 可用，并在 `ctx.runtime.creation_params` 中写入 `provider`、`provider_env_id`、`provider_env_name`、`provider_group`、`provider_proxy` 与 `import_mode="existing_env"`；`module.yaml.workflows[].host_scenarios` 可选声明 `existing_env_import`，仅用于风险提示，不构成执行门禁。
