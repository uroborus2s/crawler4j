# Architecture Summary

- Root desktop app package lives under `packages/crawler4j/src/ui`.
- Core runtime services live under `packages/crawler4j/src/core`.
- External modules are loaded from module directories through `module.yaml` plus root `__init__.py`.
- SDK and Contracts are split into standalone subpackages under `packages/crawler4j-sdk/` and `packages/crawler4j-contracts/`.
- Factory control plane lives in `.factory/` plus numbered `docs/`.

Current architecture facts:

- Builtin business modules have been removed; `packages/crawler4j/modules/` is now a placeholder, while real modules come from installed packages or DevLink source directories.
- Module projects run inside the host runtime, not their own virtualenv.
- `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py` 现作为 Hosted UI 唯一页面渲染器，页面 schema 统一来自 `data.db.module_pages`；模块详情页按 `page_id` 打开页面，`DataTable` 只作为页面内组件，通过 `load_handler` / `query_handler` 和 `db.*` 能力获取数据。

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

Latest implemented design:

- Module UI has moved from `micro_app` / `ui:*` / direct `QWidget` injection to host-managed page schemas declared by `declare_ui(context)`.
- The hosted UI contract is intentionally narrow: modules may only declare `Page`, `Section`, `Text`, `Button`, and `DataTable`.
- `DataTable` remains the only composite widget surface in V1, covering both readonly dashboard tables and host-managed CRUD tables.
- Trust gate / allowlist / `trusted` and the old `ui_loader` path have been removed from the formal runtime, because the host no longer executes external UI classes.
