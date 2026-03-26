# TASK-011 建立 MMS settings store 与模块状态持久化

- 状态：DONE
- 类型：TASK
- 优先级：P1
- 估算：1.0 人/天
- 关联 ID：`TASK-011`, `CR-003`, `REQ-002`, `REQ-005`

## 目标

- 为 MMS 提供正式的模块级/工作流级 settings store
- 将模块启用/禁用状态从内存态补齐为持久化状态
- 为后续 UI trust gate 与自定义页面加载提供稳定配置基础

## 验收标准

- `read_settings/write_settings` 对模块级与工作流级配置可用
- `export_module_settings` 可导出模块级与工作流级配置
- `enable_module/disable_module` 结果在重载后保持一致
- 卸载模块时可按 `keep_settings` 策略清理或保留配置
- 回归测试通过

## 完成说明

- 已新增 `src/core/mms/settings_store.py`
- `ModuleRegistry` 现已持久化模块启停状态，并在 reload/install/uninstall 时应用
- MMS 详情页、Schema 表单与 Core 配置命令已切换到正式 settings store
- 已补充 `tests/unit/test_core/test_mms/test_settings_store.py`
