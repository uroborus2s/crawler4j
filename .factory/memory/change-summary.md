# 变更摘要

## 文档演进
- `DOC-module-guide-directory-expansion` 模块开发指南已从单文件重构为目录化章节主指南，并按“小白开发者”视角补齐概念、上手、结构、开发、调试、交付与排错说明 | 状态：DONE | 关联：`TASK-010`

## 需求变更
- `CR-001-version-and-release-governance-alignment` CR-001 统一版本与发布治理 | 状态：DONE | 关联：无
- `CR-002-quality-gate-and-docs-navigation-alignment` CR-002 收敛质量门与文档导航策略 | 状态：DONE | 关联：无
- `CR-003-mms-settings-and-ui-extension-compliance` CR-003 补齐 MMS settings store 与 UI 扩展合规实现 | 状态：DONE | 关联：无 | 追加回归：`core:data_table` 刷新重放 `declare_ui`，并覆盖 create/update handler 与 DevLink 调试回路
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
- BUG-007-rem-manual-create-did-not-run-selected-workflow 手动创建环境后，REM 现在会把 `module.workflows.workflow_name` 解析为模块根入口 + `config.workflow`，并通过 MMS/ModuleAssembler 执行 `init_env`、`before_run`、模块运行、`on_success`、`on_cleanup`，不再走失效的 `modules.*` 直导入链路 | 状态：DONE | 关联：`tests/unit/test_core/test_rem/test_post_create_actions.py`
- 旧版本兼容层清理：已删除 `src.automation.*`、`src.utils.logger`、`src.core.models` 聚合导出、`SignalBridge/get_signal_bridge` 别名，以及 MMS settings store 对旧 `module:{name}:config` KV 的兼容回退；历史手工验证脚本中的旧入口也已移除或切到新路径，当前仓内仅保留“兼容已删除”的负向回归测试 | 状态：DONE | 关联：`tests/unit/test_core/test_mms/test_removed_runtime_surface.py`、`tests/unit/test_core/test_mms/test_settings_store.py`
- 宿主 `src/utils` 第二轮收口：已删除业务重复实现与死代码（`captcha_solver`、`hotel_matcher`、`sms_platform`、`fingerprint_generator`、`network_checker`、`async_utils`），并删除旧本地验证码分析脚本；模块侧由模块仓自带实现独立承载，且相关测试在模块仓验证通过 | 状态：DONE | 关联：`tests/unit/test_core/test_mms/test_removed_runtime_surface.py`
- 宿主源码第三轮收口：已删除 `src/core/models` 业务模型目录、`src/automation`/`src/core/models` 残留缓存目录、业务 smoke/verify 脚本，并把宿主测试中的业务样例统一泛化为 `demo_module`；同时移除 REM 中旧数据/旧字段兼容分支 | 状态：DONE | 关联：`tests/unit/test_core/test_mms/test_removed_runtime_surface.py`、`tests/integration/test_task_debug_e2e.py`
