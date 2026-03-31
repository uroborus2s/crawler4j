# API Summary

- `API-001`: Root app entry contract is `src.ui.app:main` and is currently aligned with the declared script entry.
- `API-002`: Module runtime contract remains `module.yaml` + root `__init__.py` + `run(context)` / hooks; `REQ-006` plans to shrink root `__init__.py` into a stable shim and require old modules to re-initialize.
- `API-003`: SDK / Contracts / CLI contract is currently buildable and usable; planned extension is a unified module entry assembler helper plus latest-template re-init guidance.
- `API-004`: Release metadata contract is aligned across root version, runtime mirror, child package versions, and release docs.
