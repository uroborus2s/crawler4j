# Evolution Baseline

## What To Preserve

- Use `uv` consistently
- Keep numbered `docs/` and `.factory/memory/` as the authoritative baseline
- Validate runtime entrypoints directly instead of trusting build metadata blindly
- When a service job relies on dynamic environment selection, require a declared `@env_candidates` pure function and let the host queue on empty candidates; do not reintroduce selector `None` loops or resource-pool sync snapshots
- Keep real-time log widgets resilient to bursty duplicate warnings by batching UI flushes instead of appending one QTextEdit block per signal
- When PyInstaller bundles third-party single-file modules, explicitly collect their shared resource trees and pass the consumer-expected subdirectory instead of assuming `collect_data_files()` or a generic asset root will line up automatically
- Keep module-facing database access behind `TaskContext.db`; keep non-database Core extensions behind `TaskContext.tools`
- Keep task lifecycle control behind workflow return values plus `TaskSignal`; do not reintroduce module lifecycle hooks, root shims, or run-profile teardown rules
- Keep environment actions host-owned and guarded by `EnvAction`; module code should request keep/recycle/destroy through task results or signals, not through `on_cleanup`
- Keep qasync-driven async UI flows free of blocking dialog `exec()` calls; use async dialog helpers so failure handling cannot re-enter the event loop and spawn `Cannot enter into task` cascades
- Keep QScintilla text surfaces on platform-available fixed-width fonts instead of hardcoding macOS-only families; derive extra line spacing from the chosen font metrics so Windows fallback fonts cannot collapse YAML rows
- Keep GitHub Release asset downloads on dedicated streaming timeouts instead of the shared 30s session total timeout; write to `.part` files, remove partial artifacts on timeout/failure, and reject content-length mismatches before exposing the archive to MMS install flow
- Treat fingerprint-browser CDP attachment as a warm-up phase: normalize host-returned endpoints first, then give Playwright multiple retries before declaring connect failure
- Keep Hosted UI page registration and menu configuration inside `@page(...)`: `pages/` owns routable pages, and `@page(menu=True)` is the only left-menu source

## What To Improve First

- Root entrypoint and packaging alignment
- `ctrip` module migration completion
- Version governance
- Lint scope and quality gate clarity
