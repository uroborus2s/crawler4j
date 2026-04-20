# API Summary

- `API-001`: Root app entry contract is `src.ui.app:main` and is currently aligned with the declared script entry.
- `API-002`: Module runtime contract remains `module.yaml` + root `__init__.py` + `run(context)` / hooks; `REQ-006` is implemented via a stable shim plus `ModuleAssembler`, `core:data_table` refresh runs local UI hooks with `ctx.runtime["devel_mode"]`, 模块持久配置统一落在 `config.db.module_config_entries`，运行态输入统一经 `ctx.runtime` 注入，模块详情页真实默认配置入口为宿主侧模块/工作流 YAML 编辑器，且 `module.yaml.config_defaults` 现在只作为首次初始化与“恢复默认”的静态模板。
- `API-005`: 模块配置、运行态、共享内存与快照型数据表契约已收口：`module.yaml` 承载静态清单与只读 `config_defaults` 初始化模板，模块当前配置统一落到 `config.db.module_config_entries` 并只经 `ctx.get_config()` / `ctx.config` 读取，`ctx.runtime` 承载宿主执行态元数据，`ctx.state` 仅用于单次运行内共享内存，`core:data_table` schema / snapshot dataset records 只认 `data.db`。
- `API-006`: 模块审计事件已从快照 dataset 中拆出：宿主新增 `data.db.module_audit_events`，模块统一通过 `db.append_event` / `db.query_events` 追加和查询 append-only 事件历史；当前未提供 retention / archive / 通用审计事件 UI。
- `API-007`: 固定环境池 Service Job 契约已在本地实现：`AcquisitionConfig.resource_pool`、宿主等待席位、资源池资格卡片和 SDK helper 已落地；队列模式下“当前轮没命中环境”会回到等待，而不是直接失败。
- `API-003`: SDK / Contracts / CLI contract is buildable and usable; the unified module entry assembler helper is now implemented and the CLI surface now uses grouped V1 commands such as `module init`, `task create`, `workflow create`, `page create`, `data-table create`, `package build`, `release publish`, and `check full`.
- `API-004`: Release metadata contract is aligned across app `pyproject.toml`, runtime version service, child package versions, and release docs.
