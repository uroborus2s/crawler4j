# Tests Summary

- `TC-001`: `uv run pytest -q` currently passes in the validated baseline.
- `TC-002`: Root package, SDK, and Contracts builds currently pass.
- `TC-003`: Root script import and startup path are aligned.
- `TC-004`: Headless UI smoke currently passes.
- `REQ-006` implemented coverage:
  - `TC-007`: New scaffolded shim `__init__.py` imports and exposes standard entrypoints.
  - `TC-008`: Optional `module_runtime.py` overrides default run / hook behavior.
  - `TC-009`: A module re-initialized from the latest template imports and runs correctly.

Current gaps:

- Real-site `ctrip` E2E is still open.
