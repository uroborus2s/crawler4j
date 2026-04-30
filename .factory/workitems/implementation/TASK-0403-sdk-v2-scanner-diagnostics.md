# TASK-0403 建立 SDK v2 装饰器扫描与统一诊断

- 状态：DONE
- 负责人：Codex / 测试子团队复核
- 优先级：P0
- 估算：2.0 人/天
- 关联 ID：`TASK-0403`, `TASK-0400`, `REQ-0400`, `API-012`, `TC-0400-002`

## 目标

- SDK 扫描 `core-native-v2` 标准目录下的装饰器声明。
- `check full` 对 v2 模块使用 v2 诊断，不落回 v1 runtime surface。
- 阻断 workflow parameters、旧 manifest 对象图、宿主保留数据字段和对象循环。

## 完成记录

- 已新增 `v2_scanner.py` 并接入 `collect_full_errors()` 的 v2 分支。
- scanner 限定 `__init__.py` 与 `interfaces/objects/workflows/tasks/data`，不扫描根 `runtime.py`。
- 已修复测试团队指出的 interface 注入循环漏诊断。

## 未完成项

- DevLink、module-open、package build 与 manifest lock 复用诊断仍归入 `TASK-0404`。
