# Architecture Summary

- Root desktop app lives under `src/ui`.
- Core runtime services live under `src/core`.
- External modules are loaded from module directories through `module.yaml` plus root `__init__.py`.
- SDK and Contracts are split into standalone subpackages under `crawler4j_sdk/` and `crawler4j_contracts/`.
- Factory control plane lives in `.factory/` plus numbered `docs/`.

Current architecture facts:

- Builtin business modules have been removed; `modules/` is now a placeholder, while real modules come from installed packages or DevLink source directories.
- Module projects run inside the host runtime, not their own virtualenv.

Current module entry architecture:

- `REQ-006` keeps root `__init__.py` as the host entrypoint, but shrinks it to a stable shim.
- Default task/workflow discovery and module entry assembly now live in `crawler4j_sdk.assembler.ModuleAssembler`.
- Module-specific overrides live in an optional `module_runtime.py` instead of root `__init__.py`.
- Old modules are not a compatibility target for the new contract; upgrades should rebuild the module skeleton from the latest template.
