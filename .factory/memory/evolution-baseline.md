# Evolution Baseline

## What To Preserve

- Use `uv` consistently
- Keep numbered `docs/` and `.factory/memory/` as the authoritative baseline
- Validate runtime entrypoints directly instead of trusting build metadata blindly
- When a service job relies on dynamic environment selection, require a declared `@env_candidates` pure function and let the host queue on empty candidates; do not reintroduce selector `None` loops or resource-pool sync snapshots
- Keep real-time log widgets resilient to bursty duplicate warnings by batching UI flushes instead of appending one QTextEdit block per signal
- When PyInstaller bundles third-party single-file modules, explicitly collect their shared resource trees and pass the consumer-expected subdirectory instead of assuming `collect_data_files()` or a generic asset root will line up automatically
- Keep module-facing database access behind `TaskContext.db`; keep non-database Core extensions behind `TaskContext.tools`
- Keep module data-source introspection host-owned through `ctx.db.describe(source)`; module repositories should consume the host-normalized descriptor instead of re-deriving writable and read-only field semantics from decorator metadata when a host runtime is available.
- Keep `managed_dataset` field semantics schema-only: only `@data_table.schema` business fields may be persisted in `record_json` or queried through SQLite `json_extract(...)`; schema-external JSON keys must not be selectable/filterable/sortable, and only `run_status` / `record_status` host physical fields may be module-updated as status columns.
- Keep standard browser interaction host-owned behind `ctx.tools.call("browser.*", ...)`; do not push humanized click/type/drag orchestration back into per-module local helpers as the primary protocol
- Keep browser humanization behavior modelled and testable in Core: segmented pauses, idle/navigation scan motion, target-size-aware trajectories, mouse/key dwell, controlled typing correction, sensitive-input no-correction defaults, and inertial scroll traces should stay host-owned.
- Keep task lifecycle control behind workflow `TaskResult` return values, optional object `setup(ctx, workflow)`, and optional object `cleanup(ctx, outcome)`; do not reintroduce module lifecycle hooks, root shims, `TaskSignal`, or run-profile teardown rules
- Keep workflow/component object `cleanup(ctx, outcome)` free of host fixed execution timeouts; business cleanup may need to finish module-owned persistence, audit, or release work, while environment recycle timeouts remain host-owned and separate.
- Keep environment disposal host-owned: task terminal paths always recycle, environment deletion only runs from the environment management cleanup flow, and module code must not request keep/recycle/destroy through task results, signals, or cleanup methods
- Keep qasync-driven async UI flows free of blocking dialog `exec()` calls; use async dialog helpers so failure handling cannot re-enter the event loop and spawn `Cannot enter into task` cascades
- When a modal Qt form rebuilds dependent widgets from a `QComboBox` selection, defer the rebuild to the next event-loop tick instead of destroying and recreating the widget tree inline from `currentIndexChanged`; this avoids macOS accessibility-triggered crashes inside `QComboBox` popup handling
- Keep QScintilla text surfaces on platform-available fixed-width fonts instead of hardcoding macOS-only families; derive extra line spacing from the chosen font metrics so Windows fallback fonts cannot collapse YAML rows
- Keep GitHub Release asset downloads on dedicated streaming timeouts instead of the shared 30s session total timeout; write to `.part` files, remove partial artifacts on timeout/failure, and reject content-length mismatches before exposing the archive to MMS install flow
- Keep module source scanners strict only for files that enter the module file set: skip `.venv/`, `dist/`, `build/`, cache directories, `.git/`, and `*.egg-info/` before symlink checks, while continuing to reject symlinks in real module files and inside ZIP archives.
- Treat fingerprint-browser CDP attachment as a warm-up phase: normalize host-returned endpoints first, then give Playwright multiple retries before declaring connect failure
- Treat external fingerprint-browser management APIs as a deeper readiness surface than an open TCP port: VirtualBrowser must pass `/api/getBrowserList` with `success=true`, local management calls should use direct loopback without system proxy, and startup-window `addBrowser` relay failures should retry with sanitized payload diagnostics
- Keep fingerprint-browser lifecycle operations serialized at the provider boundary: VirtualBrowser and BitBrowser management calls, Playwright/CDP `connect`, status probes, source listing and config updates should not run concurrently for the same provider instance, because external management APIs and CDP warm-up paths can otherwise stall the shared desktop qasync loop during multi-env startup, recycle or cleanup
- Keep Hosted UI page registration and menu configuration inside `@page(...)`: `pages/` owns routable pages, and `@page(menu=True)` is the only left-menu source
- Keep Hosted UI user commands behind `@ui_action` and browser automation behind workflow/component-called `@page_action`; do not use nested `page_action -> page_action` calls as a decomposition mechanism
- Keep Hosted UI DataTable `actions` columns host-adapted in `ManagedPageRenderer`: `SkyDataTable` should only emit `row_action_requested`, CRUD built-ins stay renderer-owned, custom row actions should dispatch to the action spec `name` or action id as a same-named `@ui_action`, explicit action `params` should bind against the current row first, and `crud.primary_key` is only the no-params fallback.

## What To Improve First

- Root entrypoint and packaging alignment
- `ctrip` module migration completion
- Version governance
- Lint scope and quality gate clarity
