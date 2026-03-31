# Requirements Summary

- `REQ-001`: Root desktop app must have a real, release-aligned entrypoint | Priority: P0 | Status: VERIFIED
  Constraint: script entry, runtime entry, and PyInstaller path must stay aligned.
- `REQ-002`: Core must be able to execute module workflows without legacy missing imports | Priority: P0 | Status: PARTIAL
  Constraint: `ctrip` runtime is restored locally, but real-site E2E remains open.
- `REQ-003`: SDK, Contracts, and CLI must remain buildable and usable | Priority: P1 | Status: VERIFIED
  Constraint: local build and CLI help must remain stable.
- `REQ-004`: Release metadata and docs must align to a single version truth | Priority: P0 | Status: VERIFIED
  Constraint: root version, runtime mirror, and release notes must not drift.
- `REQ-005`: Project must operate inside the software-factory lifecycle with tracked workitems | Priority: P0 | Status: VERIFIED
  Constraint: code, docs, tests, and `.factory/memory/` must stay synchronized.
- `REQ-006`: Module root entry should be tool-managed and no longer require manual `__init__.py` maintenance | Priority: P1 | Status: VERIFIED
  Constraint: Core must still load modules through root `__init__.py`; old modules upgrade by re-initializing to the latest template.
