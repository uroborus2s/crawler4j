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
