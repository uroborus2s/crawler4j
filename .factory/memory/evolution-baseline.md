# Evolution Baseline

## What To Preserve

- Use `uv` consistently
- Keep numbered `docs/` and `.factory/memory/` as the authoritative baseline
- Validate runtime entrypoints directly instead of trusting build metadata blindly
- When PyInstaller bundles third-party single-file modules, explicitly collect their shared resource trees instead of assuming `collect_data_files()` will find them
- Keep module-facing Core extensions behind one stable entry (`TaskContext.tools`)
- Keep task lifecycle control behind one stable path (`module_runtime.py` hooks + `TaskSignal`), not per-class callbacks or run-profile teardown rules
- Treat fingerprint-browser CDP attachment as a warm-up phase: normalize host-returned endpoints first, then give Playwright multiple retries before declaring connect failure

## What To Improve First

- Root entrypoint and packaging alignment
- `ctrip` module migration completion
- Version governance
- Lint scope and quality gate clarity
