# 变更摘要

## 文档演进
- `DOC-module-guide-directory-expansion` 模块开发指南已从单文件重构为目录化章节主指南，并按“小白开发者”视角补齐概念、上手、结构、开发、调试、交付与排错说明 | 状态：DONE | 关联：`TASK-010`

## 需求变更
- `CR-001-version-and-release-governance-alignment` CR-001 统一版本与发布治理 | 状态：DONE | 关联：无
- `CR-002-quality-gate-and-docs-navigation-alignment` CR-002 收敛质量门与文档导航策略 | 状态：DONE | 关联：无
- `CR-003-mms-settings-and-ui-extension-compliance` CR-003 补齐 MMS settings store 与 UI 扩展合规实现 | 状态：DONE | 关联：无 | 追加回归：`core:data_table` 刷新重放 `declare_ui`，并覆盖 create/update handler 与 DevLink 调试回路
- `CR-004-atm-signal-driven-confirmation-ui` CR-004 为 `TaskSignal.wait_for_confirmation` 建立结构化确认面板与客户端确认闭环 | 状态：DONE | 关联：`TASK-021`
- `CR-005-devlink-run-once-reload` CR-005 为 DevLink 普通执行建立显式 reload 语义，改完源码后下一次 ATM 执行即可吃到最新模块代码 | 状态：DONE | 关联：`BUG-013`
- ATM RunProfile 收敛：ATM 已切换为“任务直接持有 RunProfile”，任务创建页与主导航移除策略概念，`TSM` 包与兼容壳已删除 | 状态：DONE | 关联：ATM / Debug UI 重构

## 缺陷修复
- `BUG-001-root-entrypoint-and-pyinstaller-spec-drift` BUG-001 根入口与 PyInstaller 规格漂移 | 状态：DONE | 关联：无
- `BUG-002-ctrip-labor-workflow-falls-back-to-login` BUG-002 `ctrip labor_workflow` 因旧依赖缺失退化为登录流程 | 状态：DONE | 关联：无
- `BUG-003-pyqt-runtime-blocked-by-system-policy` BUG-003 PyQt6 运行时当前被系统策略阻断，导致 UI 与 `pytest-qt` 不可用 | 状态：DONE | 关联：无
- `BUG-004-zip-upgrade-leaves-stale-files` BUG-004 模块 ZIP 升级会残留旧文件，未满足原子升级/回滚要求 | 状态：DONE | 关联：无
- `BUG-005-hybrid-acquisition-mode-declared-but-rejected` BUG-005 `hybrid` 资源获取模式已暴露给用户，但运行时明确拒绝 | 状态：DONE | 关联：无
- `BUG-006-rem-destroy-keeps-db-only-after-fingerprint-delete-succeeds` BUG-006 REM 销毁指纹浏览器环境时，先确认外部浏览器 API 可用，并且仅在外部环境删除成功后再删除本地数据库记录 | 状态：DONE | 关联：`tests/unit/test_core/test_rem/test_destroy_env.py`
- REM 创建环境对话框现在会预填系统建议名称，并且只在用户实际修改后通过 `env_name` 提交自定义名称；默认显示名不再误写入 `creation_params.name_prefix` | 状态：DONE | 关联：`tests/unit/test_core/test_rem/test_env_list_widget.py`
- Core / SDK 已将宿主扩展能力统一收敛到 `TaskContext.tools`；验证码识别改为通过 `captcha.match_slider` / `captcha.match_click_targets` 工具调用，模块作者不再需要依赖宿主私有 `src.utils.captcha_solver` 或直接 import `sinanz` 私有模块 | 状态：DONE | 关联：`tests/unit/test_sdk/test_taskcontext.py`、`tests/unit/test_sdk/test_data_capability.py`、`tests/unit/test_core/test_atm/test_runtime_capabilities.py`
- REM 手动创建环境边界收敛：REM 现在只负责 create/open/connect 并在成功后保持 `RUNNING`；创建环境页不再配置 `post_action` / `workflow_module`，模块初始化与工作流执行统一留在 ATM / MMS 链路 | 状态：DONE | 关联：`tests/unit/test_core/test_rem/test_post_create_actions.py`、`tests/unit/test_core/test_atm/test_execution_runner.py`
- REM 创建成功反馈收敛：环境创建成功后，运行环境列表页现在只刷新列表与按钮状态，不再弹出成功提示框，避免额外打断用户操作 | 状态：DONE | 关联：`tests/unit/test_core/test_rem/test_env_list_widget.py`
- ATM 生命周期统一：已删除 `TaskScript` / `TaskFlow` 上的私有 lifecycle callbacks，正式生命周期统一收敛到 `module_runtime.py` 的 ATM hooks；模块与 ATM 的流程控制通过新增 `TaskSignal` / `EnvAction` 契约承接，支持 `WAITING_CONFIRMATION`、失败后销毁环境等语义，且 `on_cleanup` 改为在环境动作之后执行，模块可通过 `ctx.runtime["env_action"]` 做删除后的自清理 | 状态：DONE | 关联：`tests/unit/test_core/test_atm/test_execution_runner.py`、`tests/unit/test_core/test_atm/test_dispatcher_hooks.py`、`tests/unit/test_sdk/test_taskcontext.py`、`tests/unit/test_sdk/test_taskresult.py`
- ATM 信号确认 UI：`TaskSignal.wait_for_confirmation` 现会把完整 `signal` 快照持久化到任务记录并发布 `task.signal` 事件；ATM 详情页可按 `payload.confirmation` 弹出结构化确认面板，并在用户确认后回调既有 `confirm_task_success` / `confirm_task_failure` 完成任务收尾 | 状态：DONE | 关联：`tests/unit/test_core/test_atm/test_task_detail_dialog.py`、`tests/unit/test_core/test_atm/test_job_modes.py`
- 模块自定义数据列表滚动条收敛：`ModuleDataTablePage` 现在隐藏底部横向滚动条，但保留触控板/滚轮横向滑动，并以 UI 单测锁定 `ScrollPerPixel + ScrollBarAlwaysOff` 策略 | 状态：DONE | 关联：`tests/unit/test_core/test_mms/test_module_data_table_page.py`
- SDK / Contracts `1.2.0` 版本收口：已将 `crawler4j-sdk`、`crawler4j-contracts`、根应用依赖与脚手架默认 `sdk_version_range` 统一升级到 `1.2.0` 口径，并同步清理开发/发布文档中的旧版本残留 | 状态：DONE | 关联：`packages/crawler4j-sdk/pyproject.toml`、`packages/crawler4j-contracts/pyproject.toml`、`packages/crawler4j/pyproject.toml`、`packages/crawler4j-sdk/src/cli/templates.py`
- ATM Job 手动批次模式：已按方案 A 将“执行一次”落到 `BATCH + MANUAL`，不新增 `JobType`；任务创建页支持 `批次任务` 在“执行一次 / Cron 定时”间切换，任务列表与详情页改为显示手动批次语义，并新增 `TaskService.run_job_once()` 及相关 ATM/UI 单测 | 状态：DONE | 关联：`tests/unit/test_core/test_atm/test_job_modes.py`、`tests/unit/test_core/test_atm/test_task_create_dialog.py`、`tests/unit/test_core/test_atm/test_task_list_widget.py`
- BUG-008-rem-start-env-ensures-fingerprint-runtime 环境列表或 ATM 启动指纹浏览器环境时，REM 现在会先确保 BitBrowser / VirtualBrowser 宿主已启动并等待 API 就绪；未就绪时直接抛出明确错误，避免“无提示且未打开环境”的静默失败 | 状态：DONE | 关联：`tests/unit/test_core/test_rem/test_post_create_actions.py`
- BUG-009-rem-opened-window-should-stay-busy-while-cdp-connects 指纹浏览器窗口已打开但 Playwright/CDP 连接尚未成功时，REM 现在会保留 `BUSY` 状态，并对 `BrowserHandle.safe_connect()` 做短重试，避免 UI 错误回退成“就绪” | 状态：DONE | 关联：`tests/unit/test_core/test_rem/test_post_create_actions.py`、`tests/unit/test_core/test_rem/test_handle.py`
- BUG-010-rem-virtualbrowser-debugging-port-response 新版 VirtualBrowser `launchBrowser` 响应只返回 `debuggingPort` 时，REM 现在会把它自动归一为合法的 CDP 入口，而不是把窗口已打开的启动结果误判为失败；相应回归测试已覆盖 `ws` 与 `debuggingPort` 两种返回格式 | 状态：DONE | 关联：`tests/unit/test_core/test_rem/test_virtualbrowser_client.py`
- BUG-011-rem-cdp-http-endpoint-active-probe 当 VirtualBrowser 只返回 HTTP 调试入口，且 Playwright 对 `/json/version/` 的自动探测被宿主返回 `400` 时，`BrowserHandle.safe_connect()` 现在会主动请求 `/json/version` 与 `/json/list`，解析真实 `webSocketDebuggerUrl` 后再连接，避免卡死在错误的根 `ws://host:port/` 路径 | 状态：DONE | 关联：`tests/unit/test_core/test_rem/test_handle.py`
- BUG-012-rem-cdp-localhost-loopback-compatibility 对只接受 `localhost` 或只接受 `127.0.0.1` 的 VirtualBrowser 调试入口，REM 现在会把 `debuggingPort` 默认归一为 `http://localhost:<port>`，并在每轮连接前补试 `localhost` / `127.0.0.1` 的 HTTP 调试地址，优先使用成功探测到的真实 websocket 端点，降低宿主调试端点的兼容性差异导致的连接失败 | 状态：DONE | 关联：`tests/unit/test_core/test_rem/test_handle.py`、`tests/unit/test_core/test_rem/test_virtualbrowser_client.py`
- `BUG-013-module-assembler-import-errors-hidden` BUG-013 `ModuleAssembler` 在发现 `tasks/` / `workflows/` 时会静默吞掉 import failure，导致开发者只看到泛化的 “Workflow or task not found” | 状态：DONE | 关联：`packages/crawler4j/tests/unit/test_sdk/test_assembler.py`
- 旧版本兼容层清理：已删除 `src.automation.*`、`src.utils.logger`、`src.core.models` 聚合导出、`SignalBridge/get_signal_bridge` 别名，以及 MMS settings store 对旧 `module:{name}:config` KV 的兼容回退；历史手工验证脚本中的旧入口也已移除或切到新路径，当前仓内仅保留“兼容已删除”的负向回归测试 | 状态：DONE | 关联：`tests/unit/test_core/test_mms/test_removed_runtime_surface.py`、`tests/unit/test_core/test_mms/test_settings_store.py`
- 宿主 `src/utils` 第二轮收口：已删除业务重复实现与死代码（`captcha_solver`、`hotel_matcher`、`sms_platform`、`fingerprint_generator`、`network_checker`、`async_utils`），并删除旧本地验证码分析脚本；模块侧由模块仓自带实现独立承载，且相关测试在模块仓验证通过 | 状态：DONE | 关联：`tests/unit/test_core/test_mms/test_removed_runtime_surface.py`
- 宿主源码第三轮收口：已删除 `src/core/models` 业务模型目录、`src/automation`/`src/core/models` 残留缓存目录、业务 smoke/verify 脚本，并把宿主测试中的业务样例统一泛化为 `demo_module`；同时移除 REM 中旧数据/旧字段兼容分支 | 状态：DONE | 关联：`tests/unit/test_core/test_mms/test_removed_runtime_surface.py`、`tests/integration/test_task_debug_e2e.py`
