# Architecture Summary

- Root desktop app package lives under `packages/crawler4j/src/ui`.
- Core runtime services live under `packages/crawler4j/src/core`.
- External modules are loaded from module directories through `module.yaml` plus root `__init__.py`.
- SDK and Contracts are split into standalone subpackages under `packages/crawler4j-sdk/` and `packages/crawler4j-contracts/`.
- Factory control plane lives in `.factory/` plus numbered `docs/`.

Current architecture facts:

- Builtin business modules have been removed; `packages/crawler4j/modules/` is now a placeholder, while real modules come from installed packages or DevLink source directories.
- Module projects run inside the host runtime, not their own virtualenv.
- `packages/crawler4j/src/core/mms/ui/module_data_table_page.py` now builds a UI-side `TaskContext` from module settings and reloads DevLink local hooks on refresh, so host data-table pages can replay `declare_ui` and local CRUD handlers during module debugging.

Current module entry architecture:

- `REQ-006` keeps root `__init__.py` as the host entrypoint, but shrinks it to a stable shim.
- Default task/workflow discovery and module entry assembly now live in `crawler4j_sdk.assembler.ModuleAssembler`.
- Module-specific overrides live in an optional `module_runtime.py` instead of root `__init__.py`.
- Old modules are not a compatibility target for the new contract; upgrades should rebuild the module skeleton from the latest template.
