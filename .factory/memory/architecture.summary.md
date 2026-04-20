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
- Module-specific runtime logic now lives in standard `module_runtime.py`, including lifecycle hooks and `@env_selector(...)` callbacks for ATM environment selection.
- Old modules are not a compatibility target for the new contract; upgrades should rebuild the module skeleton from the latest template.

Latest implemented design:

- Fixed-pool Service jobs now move from “selector returned none => fail” to host-managed waiting seats when `resource_pool` is configured.
- ATM reconciles service concurrency as `running + waiting = target`, with FIFO refill against current pool capacity.
- REM remains the environment owner, while module-scoped pool eligibility is exposed to ATM through host-readable cards stored in `env_metadata`.
- `REQ-009` / `TASK-023` is implemented locally and validated by ATM/SDK unit tests; PR closure is still pending.
