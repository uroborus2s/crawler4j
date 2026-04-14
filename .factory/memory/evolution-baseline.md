# Evolution Baseline

## What To Preserve

- Use `uv` consistently
- Keep numbered `docs/` and `.factory/memory/` as the authoritative baseline
- Validate runtime entrypoints directly instead of trusting build metadata blindly
- Keep module-facing Core extensions behind one stable entry (`TaskContext.tools`)

## What To Improve First

- Root entrypoint and packaging alignment
- `ctrip` module migration completion
- Version governance
- Lint scope and quality gate clarity
