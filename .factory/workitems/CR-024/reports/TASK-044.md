# TASK-044 实现报告

## 结果

- 新增 `examples/cheese_automation/` 标准 `core-native-v2` 模块。
- 模块 workflow 返回包内 Cheese 脚本的绝对路径和官方插件运行方式。
- 新增 `cheese/settings_smoke.js`：校验屏幕尺寸、打开 Android 系统设置并验证前台包名。
- SDK 集成测试覆盖 full 校验、ZIP 构建/校验、脚本 API 契约、workflow 路径和 ZIP 资源包含关系。

## 边界

- 未修改 Core、Contracts、SDK 公共契约或依赖。
- 未实现或逆向 Cheese 私有设备连接协议。
- 未连接真实设备；设备侧 E2E 仍需用户在已授权 Android 设备运行。

## 证据

- `.factory/workitems/CR-024/evidence/TASK-044.md`
- `.factory/workitems/CR-024/brief.md`
- `packages/crawler4j/tests/integration/test_sdk_cli_module_mode.py`
