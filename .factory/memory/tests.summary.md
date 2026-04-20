# Tests Summary

- `TC-001`: `uv run pytest -q` currently passes in the validated baseline (`485 passed` on `2026-04-20`).
- `TC-002`: Root package, SDK, and Contracts builds currently pass.
- `TC-003`: Root script import and startup path are aligned.
- `TC-004`: Headless UI smoke currently passes.
- `REQ-006` implemented coverage:
  - `TC-007`: New scaffolded shim `__init__.py` imports and exposes standard entrypoints.
  - `TC-008`: Standard `module_runtime.py` carries lifecycle hooks and `@env_selector(...)` callbacks, and overrides default run / hook behavior when declared.
  - `TC-009`: A module re-initialized from the latest template imports and runs correctly.
- `TC-010`: `core:data_table` now replays `declare_ui` on refresh, routes add/edit to schema-declared sync local handlers, sets `devel_mode` for DevLink page refresh, and still has a reproducible formal rerun command through `test_module_data_table_page.py`.
- `TC-011`: ATM `Job` now persists `RunProfile` snapshots directly, task UI/debug/dispatcher only consume `job.run_profile`, and `TSM` compatibility code has been removed; covered by `test_dispatcher_run_profile.py`, `test_debug/test_service.py`, `test_job_modes.py`, `test_task_create_dialog.py`, `test_run_profile_schema.py`, and `tests/integration/test_task_debug_e2e.py`.
- `TC-012`: ATM “选择环境”已切到模块回调模式，UI 会提示 `return_none` 占位选择器，执行链路会在回调返回 `None` 时直接失败；覆盖见 `test_run_profile_dialog.py`, `test_execution_runner.py`, `test_dispatcher_run_profile.py`, `test_cli_scaffold.py`, `test_assembler.py`.
- `TC-013`: 模块持久配置已迁到 `config.db.module_config_entries`，`ctx.get_config()` 只读模块/工作流配置，ATM/Debug 的 `workflow`、`execution_params`、`job_params`、`devel_mode`、`creation_params` 统一进入 `ctx.runtime`；覆盖见 `test_settings_store.py`, `test_execution_runner.py`, `test_dispatcher_hooks.py`, `test_debug/test_service.py`, `tests/integration/test_task_debug_e2e.py`.
- `TC-014`: 模块详情页真实配置入口现已恢复为可编辑的模块/工作流 YAML 配置页，并显式拒绝 JSON/花括号对象字面量；`core:data_table` 的 schema / records 当前只认 `data.db`，SDK CLI 以 `data-table create` / `page create` 收敛受控入口，scanner 与 `cmd_check` 会拒绝旧声明式文件和未托管 detail menu；覆盖见 `test_module_detail_page.py`, `test_module_data_store.py`, `test_module_data_table_page.py`, `test_settings_store.py`, `test_runtime_capabilities.py`, `test_cli_scaffold.py`.
- `TC-015`: `module.yaml.config_defaults` 现可声明模块/工作流配置初始化模板；宿主首次加载模块时只初始化一次，后续升级不会自动覆盖，详情页“恢复模块默认 / Workflow 默认”按钮会在警告确认后按当前 manifest 模板覆盖对应 scope；覆盖见 `test_mms.py`, `test_settings_store.py`, `test_module_detail_page.py`.
- `TC-016`: `crawler4j check full` 现在会把 `module_runtime.py` 与 `ui/__init__.py` 的导入异常收敛为用户可读的校验失败，而不是直接抛 traceback；覆盖见 `tests/unit/test_sdk/test_cli_scaffold.py`.
- `TC-017`: 模块列表页卸载正式模块时，只有 `registry.uninstall()` 返回 `True` 才会弹成功提示并刷新列表；拒绝卸载或失败时会改为弹警告，避免 UI 误报成功；覆盖见 `tests/unit/test_core/test_mms/test_module_list_widget.py`.
- `TC-018`: 模块在线升级现在会拒绝 `module.yaml.version` 与 GitHub Release 版本不一致的安装包，并在真正应用升级时重新校验运行中任务，避免预览信息与实际安装产物漂移；覆盖见 `tests/unit/test_core/test_mms/test_release_service.py`.
- `TC-019`: 模块级升级维护锁现在会阻断 ATM 的运行时预检、手动批次最终发车、Service 并发补齐与 Cron 触发，防止升级确认后仍有新任务进入；覆盖见 `tests/unit/test_core/test_atm/test_job_modes.py` 与 `tests/unit/test_sdk/test_cli_host_release.py`.
- `TC-020`: 添加开发模块时，如果 GitHub 升级源仓库暂时不可达，宿主现在会保留本地 DevLink 注册能力并把远端失败降级为 warning；同时 GitHub 请求错误路径不再被 `logger.warning(...)` 的参数签名误用打断；覆盖见 `tests/unit/test_core/test_mms/test_release_service.py`.
- `TC-021`: 客户端主导航现已新增 `📘 使用文档` 页面，宿主会把公开 `docs/` 资源打进 PyInstaller 包并直接展示 Markdown；当前文档中心最上面是直接打开 `01-getting-started/index.md` 的顶层文档 `开始前`，其余内容按 `使用指南 / 开发指南` 两组收口；相对 `.md` 跳转、顶层文档与树形目录导航由 `test_help_page.py`、`test_shell.py` 与 `test_packaging_config.py` 覆盖。
- `TC-022`: 私有 GitHub 仓库现在支持双轨鉴权：桌面客户端按 `repo` 维度把 GitHub Token 加密保存到应用内，并通过模块详情页与安装弹窗维护；SDK CLI 仍支持 `--github-token` 和环境变量；宿主 release service 会优先使用显式传入 token，其次使用 repo 维度的已保存凭据，并继续以鉴权请求下载私有 Release 资产；覆盖见 `tests/unit/test_core/test_mms/test_github_credentials.py`、`tests/unit/test_core/test_mms/test_module_install_dialog.py`、`tests/unit/test_core/test_mms/test_module_detail_page.py`、`tests/unit/test_core/test_mms/test_module_list_widget.py`、`tests/unit/test_core/test_mms/test_release_service.py` 与 `tests/unit/test_sdk/test_cli_host_release.py`.
- `TC-023`: 模块安装弹窗的本地 ZIP / GitHub 源页签现在使用左对齐纵向字段布局，且“记住 Token”勾选文案明确区分“绑定到安装包声明仓库”和“绑定到当前输入仓库”；覆盖见 `tests/unit/test_core/test_mms/test_module_install_dialog.py`.
- `TC-024`: 模块快照数据与审计事件已拆成两条正式能力面：`module_audit_events` / `db.append_event` / `db.query_events` 负责 append-only 历史，`module_datasets` 继续承载快照型 records；覆盖见 `test_module_data_store.py`, `test_runtime_capabilities.py`, `test_data_capability.py`.
- `TC-025`: acceptance 套件当前覆盖 SDK CLI 脚手架到 `package verify`、`host devlink`、本地 ZIP `preview/apply` 与验收 gate 命令矩阵，已作为当前 fresh gate 的一部分。
- `TC-026`: 固定环境池 Service Job 的等待队列语义已由 ATM 单测覆盖，包括“运行中 + 等待中”、FIFO 补位与资源池模式下的等待语义。
- `TC-027`: 模块资源池资格卡片已由 runtime capability / SDK helper 单测覆盖，包括资源池隔离、不可接单切换与快照重建。
- `TC-028`: ATM `TaskCreateDialog` 现锁定 `配置运行模板`、`取消`、`创建/保存` 按钮必须使用共享 `StyledButton`，且按钮高度统一为 `40px`；同时覆盖“运行配置”长预览文本不会再向下压到蓝色按钮区域，见 `tests/unit/test_core/test_atm/test_task_create_dialog.py` 与 `tests/unit/test_ui/test_button.py`.
- `TC-029`: REM 环境列表页已切到 UI 主 `qasync` 事件循环中的串行异步环境操作，并在执行期间禁用表格/创建/刷新入口，避免旧版 `QThread + 共享 asyncio loop` 在连续点击时触发跨线程 loop 复用；覆盖见 `tests/unit/test_core/test_rem/test_env_list_widget.py`.
- `TC-030`: `crawler4j-sdk page create` 生成的代码型页面现在在缺少 `PyQt6` 时仍可被 `check full` 安全导入，且 SDK / Contracts / Root app 的 `0.x` 兼容区间已收紧到当前 minor 的 patch 版本；覆盖见 `tests/unit/test_sdk/test_cli_scaffold.py`, `tests/unit/test_sdk/test_packaging_config.py`, `tests/integration/test_sdk_cli_module_mode.py`.
- `TC-031`: 默认环境名占位的 `SELECT max + INSERT` 现已改为同一 SQLite 写事务内完成，避免并发创建时重复发放 `env-YYYYMMDD-N` 名称；覆盖见 `tests/unit/test_core/test_rem/test_atomic_reservation.py`.
- Workspace root `scripts/` now keeps `build_workspace_packages.py`, `db_cli.py`, and `smoke_test_ui.py` as the maintained helper set; legacy local debug and icon-generation helpers are no longer treated as maintained assets.

Current gaps:

- Real-site `ctrip` E2E is still open.
- Windows desktop delivery artifacts are still open.
- `REQ-009` queue semantics are now covered locally by ATM / SDK unit tests: `uv run pytest packages/crawler4j/tests/unit/test_core/test_atm -q packages/crawler4j/tests/unit/test_sdk/test_data_capability.py` => `122 passed`.
- The execution baseline for that closeout now lives in `docs/04-project-development/06-testing-verification/ctrip-real-site-e2e-closeout.md`.
