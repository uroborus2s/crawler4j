# Tests Summary

- `TC-001`: `uv run pytest -q` currently passes in the validated baseline.
- `TC-002`: Root package, SDK, and Contracts builds currently pass.
- `TC-003`: Root script import and startup path are aligned.
- `TC-004`: Headless UI smoke currently passes.
- `REQ-006` implemented coverage:
  - `TC-007`: New scaffolded shim `__init__.py` imports and exposes standard entrypoints.
  - `TC-008`: Standard `module_runtime.py` carries lifecycle hooks and `@env_selector(...)` callbacks, and overrides default run / hook behavior when declared.
  - `TC-009`: A module re-initialized from the latest template imports and runs correctly.
- `TC-010`: `core:data_table` now replays `declare_ui` on refresh, routes add/edit to schema-declared sync local handlers, and sets `devel_mode` for DevLink page refresh; covered by `test_module_data_table_page.py` and `test_ctrip_account_ui_smoke.py`.
- `TC-011`: ATM `Job` now persists `RunProfile` snapshots directly, task UI/debug/dispatcher only consume `job.run_profile`, and `TSM` compatibility code has been removed; covered by `test_dispatcher_run_profile.py`, `test_debug/test_service.py`, `test_job_modes.py`, `test_task_create_dialog.py`, `test_run_profile_schema.py`, and `tests/integration/test_task_debug_e2e.py`.
- `TC-012`: ATM “选择环境”已切到模块回调模式，UI 会提示 `return_none` 占位选择器，执行链路会在回调返回 `None` 时直接失败；覆盖见 `test_run_profile_dialog.py`, `test_execution_runner.py`, `test_dispatcher_run_profile.py`, `test_cli_scaffold.py`, `test_assembler.py`.
- `TC-013`: 模块持久配置已迁到 `config.db.module_config_entries`，`ctx.get_config()` 只读模块/工作流配置，ATM/Debug 的 `workflow`、`execution_params`、`job_params`、`devel_mode`、`creation_params` 统一进入 `ctx.runtime`；覆盖见 `test_settings_store.py`, `test_execution_runner.py`, `test_dispatcher_hooks.py`, `test_debug/test_service.py`, `tests/integration/test_task_debug_e2e.py`.

Current gaps:

- Real-site `ctrip` E2E is still open.
