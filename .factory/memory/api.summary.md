# API Summary

- `API-001`: Root desktop app entry contract remains `src.ui.app:main`.
- `API-002`: 模块正式运行时契约已切到 `core-native-v1`。Core 只接受 `module.yaml` + 宿主扫描协议：`tasks/*.py -> TASK/execute`、`workflows/*.py -> WORKFLOW/run`、`hooks/*.py -> handle`、`env_selectors/*.py -> SELECTOR/select`、`pages/*.py` / `pages/<group>/*.py -> PAGE/handler`。缺少 `runtime_api: core-native-v1` 或仍依赖旧运行薄壳的模块会被直接拒绝加载。
- `API-003`: `crawler4j-sdk` 现只提供 CLI、脚手架、校验和开发辅助，不再导出运行时 owner 能力；`crawler4j-contracts` 负责共享契约类型与 Hosted UI 归一化 helper。
- `API-004`: Release metadata contract is aligned across app `pyproject.toml`, runtime version service, child package versions, and release docs.
- `API-005`: 模块配置、运行态和数据边界已稳定：`module.yaml` 承载静态清单与 `config_defaults` 模板，当前配置落到 `config.db.module_config_entries`，`ctx.runtime` 承载宿主执行态元数据，`ctx.state` 仅用于单次运行内共享内存。
- `API-006`: 模块审计事件统一通过 `db.append_event` / `db.query_events` 访问 `data.db.module_audit_events`；快照数据通过 `db.get_record` / `db.list_records` / `db.replace_records` 访问已在 `module.yaml.data.resources[]` 注册的资源。
- `API-007`: 固定环境池 Service Job 契约已本地实现：`resource_pool`、环境候选、资格卡片与等待席位都由宿主负责；环境选择器返回 `None` 时，是否等待取决于是否配置了 `resource_pool`。
- `API-008`: Hosted UI 正式契约收口为 `PageSpec` + `ui_extension.pages[]`。页面 schema 顶层必须是 `Page`，公开组件固定为 `Page`、`Section`、`Text`、`Button`、`DataTable`；页面数据与查询通过页面 handler 承接。
- `API-009`: 模块实体表视图与分析查询能力已切到 manifest 驱动：`module.yaml.data.views[]` / `queries[]` 联合 `data/sql/views/*.sql` / `queries/*.sql` 注册视图和命名查询，运行时只暴露 `db.query_view` / `db.run_query`；模块代码禁止执行未注册 SQL。
