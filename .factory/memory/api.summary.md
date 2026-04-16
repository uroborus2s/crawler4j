# API Summary

- `API-001`: Root app entry contract is `src.ui.app:main` and is currently aligned with the declared script entry.
- `API-002`: Module runtime contract remains `module.yaml` + root `__init__.py` + `run(context)` / hooks; `REQ-006` is implemented via a stable shim plus `ModuleAssembler`, `core:data_table` refresh runs local UI hooks with `ctx.runtime["devel_mode"]`, and 模块持久配置现统一落在 `config.db.module_config_entries`，运行态输入统一经 `ctx.runtime` 注入。
- `API-003`: SDK / Contracts / CLI contract is buildable and usable; the unified module entry assembler helper is now implemented and the CLI surface includes `init-model --defaults`, `new`, and `list`.
- `API-004`: Release metadata contract is aligned across app `pyproject.toml`, runtime version service, child package versions, and release docs.
