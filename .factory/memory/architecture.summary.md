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

- `packages/crawler4j/src/core/mms/runtime_descriptor.py` is the source of truth for `core-native-v1` discovery.
- `packages/crawler4j/src/core/mms/service.py` loads and caches `ModuleRuntimeDescriptor`, executes workflows/tasks, dispatches hooks, and invokes env selectors.
- `packages/crawler4j/src/core/mms/ui/module_ui_runtime.py` reads pages and UI-related hooks from the descriptor instead of asking the module root for UI declarations.
- `packages/crawler4j/src/core/mms/scanner.py` enforces `module.yaml.runtime_api == core-native-v1`, `default_workflow`, and manifest/workflow consistency.
- `module.yaml.workflows[].parameters[]` now declares Workflow run-template input schema; ATM `RunProfileDialog` renders it dynamically and persists values to `execution.params`.
- 0.4.0 architecture direction supersedes workflow parameters with `core-native-v2` decorator-first object assembly: module runtime capabilities come from decorators, workflow receives injected objects only, component parameters are used during object construction, page actions replace stateful task scripts, Core owns per-task/env object graph assembly, and SDK must catch host-owned DB field collisions during module-open/check/build.
- Old modules are not a compatibility target. The host rejects missing or mismatched `runtime_api` instead of bridging.

Current UI architecture:

- `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py` is the Hosted UI renderer.
- Page schemas now come from `pages/*.py` or grouped `pages/<group>/*.py` exported `PAGE: PageSpec`, normalized by `crawler4j_contracts.hosted_ui`.
- `DataTable` remains a page-scoped component. Data comes from page `load_handler` / `query_handler` plus `db.*` tools.

Current pool/data architecture:

- Fixed-pool Service jobs use host-managed waiting semantics when `resource_pool` is configured.
- REM remains the environment owner, while ATM consumes module-provided env selectors and pool eligibility data.
- REM now also owns existing-env import. Provider-side environments are deduplicated by `(provider, name)`, imported into REM, and then executed by ATM through a fixed `env_id` handoff instead of a module-owned sync path.
- Module data resources, database views, and audit events remain Core-owned persistence capabilities exposed to modules only through `ctx.tools`.
