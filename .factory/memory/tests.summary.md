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
- `TC-014`: 模块详情页真实配置入口现已恢复为可编辑的模块/工作流 YAML 配置页，并显式拒绝 JSON/花括号对象字面量；`core:data_table` 的 schema / records 当前只认 `data.db`，SDK CLI 以 `data-table create` / `page create` 收敛受控入口，scanner 与 `cmd_check` 会拒绝旧声明式文件和未托管 detail menu；覆盖见 `test_module_detail_page.py`, `test_module_data_store.py`, `test_module_data_table_page.py`, `test_settings_store.py`, `test_runtime_capabilities.py`, `test_cli_scaffold.py`.
- `TC-015`: `module.yaml.config_defaults` 现可声明模块/工作流配置初始化模板；宿主首次加载模块时只初始化一次，后续升级不会自动覆盖，详情页“恢复模块默认 / Workflow 默认”按钮会在警告确认后按当前 manifest 模板覆盖对应 scope；覆盖见 `test_mms.py`, `test_settings_store.py`, `test_module_detail_page.py`.
- `TC-016`: `crawler4j check full` 现在会把 `module_runtime.py` 与 `ui/__init__.py` 的导入异常收敛为用户可读的校验失败，而不是直接抛 traceback；覆盖见 `tests/unit/test_sdk/test_cli_scaffold.py`.
- `TC-017`: 模块列表页卸载正式模块时，只有 `registry.uninstall()` 返回 `True` 才会弹成功提示并刷新列表；拒绝卸载或失败时会改为弹警告，避免 UI 误报成功；覆盖见 `tests/unit/test_core/test_mms/test_module_list_widget.py`.
- `TC-018`: 模块在线升级现在会拒绝 `module.yaml.version` 与 GitHub Release 版本不一致的安装包，并在真正应用升级时重新校验运行中任务，避免预览信息与实际安装产物漂移；覆盖见 `tests/unit/test_core/test_mms/test_release_service.py`.
- `TC-019`: 模块级升级维护锁现在会阻断 ATM 的运行时预检、手动批次最终发车、Service 并发补齐与 Cron 触发，防止升级确认后仍有新任务进入；覆盖见 `tests/unit/test_core/test_atm/test_job_modes.py` 与 `tests/unit/test_sdk/test_cli_host_release.py`.
- Workspace root `scripts/` is now intentionally reduced to `db_cli.py` and `smoke_test_ui.py`; legacy local debug and icon-generation helpers are no longer treated as maintained assets.

Current gaps:

- Real-site `ctrip` E2E is still open.
- The execution baseline for that closeout now lives in `docs/04-project-development/06-testing-verification/ctrip-real-site-e2e-closeout.md`.
