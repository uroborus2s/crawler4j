# Requirements Summary

- `REQ-001`: Root desktop app must have a real, release-aligned entrypoint | Priority: P0 | Status: VERIFIED
  Constraint: script entry, runtime entry, and PyInstaller path must stay aligned.
- `REQ-002`: Core must be able to execute module workflows without legacy missing imports | Priority: P0 | Status: PARTIAL
  Constraint: `ctrip` runtime is restored locally, but real-site E2E remains open.
- `REQ-003`: SDK, Contracts, and CLI must remain buildable and usable | Priority: P1 | Status: VERIFIED
  Constraint: local build and CLI help must remain stable.
- `REQ-004`: Release metadata and docs must align to a single version truth | Priority: P0 | Status: VERIFIED
  Constraint: app `pyproject.toml`, runtime version service, and release notes must not drift.
- `REQ-005`: Project must operate inside the software-factory lifecycle with tracked workitems | Priority: P0 | Status: VERIFIED
  Constraint: code, docs, tests, and `.factory/memory/` must stay synchronized.
- `REQ-006`: Module root entry should be tool-managed and no longer require manual `__init__.py` maintenance | Priority: P1 | Status: VERIFIED
  Constraint: Core must still load modules through root `__init__.py`; old modules can restore the latest root template with `crawler4j module repair-init`.
- `REQ-007`: ATM lifecycle and environment disposal must stay host-owned | Priority: P1 | Status: VERIFIED
  Constraint: module workflow only returns `TaskResult`, object setup only uses `setup(ctx, workflow)`, object cleanup only uses `cleanup(ctx, outcome)`, task terminal paths always recycle environments, and deletion only runs from the environment management cleanup flow.
- `REQ-008`: Host must keep module history data separate from UI table rendering semantics | Priority: P1 | Status: VERIFIED
  Constraint: module-authored history is now modeled as registered resources and accessed through `ctx.db`; old append/query event tools are no longer module developer interfaces.
- `REQ-009`: Fixed-pool Service jobs must wait for eligible module pool capacity instead of failing immediately | Priority: P1 | Status: VERIFIED
  Constraint: host-owned waiting seats, FIFO refill, pool eligibility cards, and queued waiting-timeout closeout are implemented locally.
- `REQ-010`: Hosted UI must support host-managed batch import | Priority: P1 | Status: DESIGNED
  Constraint: page/table toolbar buttons may open a host import dialog or call module `@ui_action` / workflow; the host reads `.xlsx/.csv` files or clipboard text, enforces file/row limits and redacts sensitive fields, and modules only receive structured import payload rows.
- `REQ-012`: Hosted UI DataTable must support current-page multi-select bulk update | Priority: P1 | Status: CORE_PACKAGES_RELEASED_MODULE_INTEGRATION_PENDING
  Constraint: top-level `selection_mode` accepts `none/single/multi` and defaults to `single`; Core passes only ordered, type-sensitive unique `primary_keys` and form `payload`; module handlers own business validation and `managed_dataset` updates; omitted fields keep legacy single-selection behavior. Independent review, human confirmation, final full unit `1134 passed`, Contracts 0.4.3 / SDK 0.4.4 publish and isolated install verification passed; business-module integration remains separate.
- `REQ-013`: Hosted UI common form fields must support optional module-owned change handling and secure form reset | Priority: P0 | Status: IMPLEMENTED_VALIDATION_PENDING
  Constraint: Form-scoped events carry an opaque short-lived handle and current values; standalone events never receive a usable form handle; modules actively call generic `ui.form.reset`; create forms honor exact column defaults, update forms prefer row values, long forms scroll with visible actions, optional `crud.form.layout` supports strict 1–3 column row-major responsive layout, and Core/renderer enforce scope, lifecycle, exact falsy-value preservation and latest-wins concurrency without business-specific effects.
- `REQ-0400`: 0.4.0 module runtime must switch to decorator-first object assembly | Priority: P0 | Status: DESIGNED
  Constraint: workflow cannot own parameters; decorators are the runtime capability source of truth, object parameters belong to components, Core assembles one object graph per task/env, SDK/Contracts provide decorators, scanning, validation, migration, manifest lock, and opening-phase reserved host DB field diagnostics.
- `REQ-0401`: User and developer guides must be versioned for docs-stratego | Priority: P0 | Status: DESIGNED
  Constraint: website main docs point to the current released guide version; old user/developer guides stay available under versioned paths; unreleased 0.4.0 docs are preview-only until release.
