# Architecture Summary

- Root desktop app package lives under `packages/crawler4j/src/ui`.
- Core runtime services live under `packages/crawler4j/src/core`.
- Shared contracts live under `packages/crawler4j-contracts/`.
- SDK CLI and scaffolding live under `packages/crawler4j-sdk/`.
- Factory control plane lives in `.factory/` plus numbered `docs/`.

Current architecture facts:

- Builtin business modules have been removed; real modules come from installed packages or DevLink source directories.
- Module projects run inside the host runtime, not their own virtualenv.
- Core is now the sole runtime owner. External modules are loaded from module directories through `module.yaml` plus host-side runtime descriptor scanning, not through a module-owned assembler.
- 0.4.0 documentation architecture direction keeps project-development docs unversioned, but versions user/developer guides for docs-stratego: current released guides become the website main docs, archived guides stay accessible, and unreleased 0.4.0 guides are preview-only.

Current module runtime architecture:

- `packages/crawler4j/src/core/mms/runtime_descriptor.py` is the source of truth for `core-native-v2` descriptor discovery through `ModuleRuntimeDescriptorV2/load_runtime_descriptor_v2`.
- `packages/crawler4j/src/core/mms/service.py` continues to own host runtime execution while the 0.4.0 v2 path moves module capability facts to decorators and manifest lock.
- `packages/crawler4j/src/core/mms/ui/module_ui_runtime.py` reads Hosted UI pages from `ModuleRuntimeDescriptorV2.pages`; pages are part of the same v2 decorator descriptor graph as other module declarations.
- Hosted UI page actions are v2 descriptor `@page_action` entries invoked with kwargs through `ModuleUIRuntimeBridge.call_page_action`; they use the narrowed `hosted_ui_action` runtime surface instead of the full workflow surface.
- `packages/crawler4j-sdk/src/v2_scanner.py` and SDK `check full` enforce `module.yaml.runtime_api == core-native-v2`, reject 0.3.x manifest fields, scan standard v2 declaration directories, and catch host-owned DB field collisions.
- `core-native-v2` is decorator-first object assembly: module runtime capabilities come from decorators, workflow receives injected objects only, component parameters are used during object construction, page actions replace stateful task scripts, Core owns per-task/env object graph assembly, and SDK owns module-open/check/build diagnostics. Object injection and component parameters can be declared either in decorator arguments or as `Annotated[..., object_inject/object_param]` class / `__init__` annotations; both paths normalize to the same descriptor metadata.
- `ObjectContainerV2` validates `object_bindings` against reachable injection paths before object graph construction, so misspelled paths cannot silently fall back to the single implementation.
- Old modules are not a compatibility target. The host rejects missing or mismatched `runtime_api` instead of bridging.

Current UI architecture:

- `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py` is the Hosted UI renderer.
- Page schemas now come from `pages/*.py` or grouped `pages/<group>/*.py` functions decorated with `@page(...)`, normalized by `crawler4j_contracts.hosted_ui`; `@page(menu=True)` is the only source for left-menu entries.
- `DataTable` remains a page-scoped component. Data comes from page `load_handler` / `query_handler` plus `db.*` tools.

Current pool/data architecture:

- Fixed-pool Service jobs use host-managed waiting semantics when `resource_pool` is configured.
- REM remains the environment owner; 0.4.0 no longer treats module-provided `env_selectors/` as the SDK / Contracts public path.
- REM now also owns existing-env import. Provider-side environments are deduplicated by `(provider, name)`, imported into REM, and then executed by ATM through a fixed `env_id` handoff instead of a module-owned sync path.
- Module data tables, named queries, database access, and audit events remain Core-owned persistence capabilities exposed to modules through `ctx.db`; SDK rejects legacy `ctx.tools.call("db.*")` usage.
