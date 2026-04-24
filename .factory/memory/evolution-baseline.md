# Evolution Baseline

## What To Preserve

- Use `uv` consistently
- Keep numbered `docs/` and `.factory/memory/` as the authoritative baseline
- Validate runtime entrypoints directly instead of trusting build metadata blindly
- When a service job relies on an env selector that can legally return `None`, require a stable `resource_pool` binding or pause the job at runtime precheck to avoid dispatch storms on startup
- Keep real-time log widgets resilient to bursty duplicate warnings by batching UI flushes instead of appending one QTextEdit block per signal
- When PyInstaller bundles third-party single-file modules, explicitly collect their shared resource trees and pass the consumer-expected subdirectory instead of assuming `collect_data_files()` or a generic asset root will line up automatically
- Keep module-facing database access behind `TaskContext.db`; keep non-database Core extensions behind `TaskContext.tools`
- Keep task lifecycle control behind one stable host-owned path (`hooks/*.py` + `TaskSignal`), not per-class callbacks, root shims, or run-profile teardown rules
- Treat fingerprint-browser CDP attachment as a warm-up phase: normalize host-returned endpoints first, then give Playwright multiple retries before declaring connect failure
- Keep Hosted UI page registration and menu configuration separate: `pages/` owns routable `PAGE` modules, while `module.yaml.ui_extension.pages[]` only owns left-menu entries

## What To Improve First

- Root entrypoint and packaging alignment
- `ctrip` module migration completion
- Version governance
- Lint scope and quality gate clarity
