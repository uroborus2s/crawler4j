# Architecture Summary

- Root desktop app lives under `src/ui`
- Core runtime services live under `src/core`
- Builtin modules live under `modules/`
- SDK and Contracts are split into standalone subpackages
- Factory control plane is now `.factory/` plus numbered `docs/`

Current architecture deviations:

- Release metadata does not match the actual root runtime entrypoint
- `ctrip` module still carries old-path runtime dependencies
