# TASK-0406 建立 Core v2 对象容器与执行链

- 状态：IN_PROGRESS
- 负责人：Codex
- 优先级：P0
- 估算：3.0 人/天
- 关联 ID：`TASK-0406`, `TASK-0400`, `REQ-0400`, `API-012`, `TC-0400-005`

## 目标

- 按 task/env/run profile 创建独立对象图。
- workflow 只接收注入对象，不接收普通 parameters。
- component 创建参数来自运行模板对象参数。

## 完成记录

- 已新增 Core v2 最小对象容器 `ObjectContainerV2`，可基于 descriptor、workflow 名称、显式 `object_bindings` 与 `object_params` 创建单次 task/env 的独立对象图。
- 已覆盖 interface 注入实现选择、递归 component 注入、同一对象图内 component 实例共享、不同对象图实例隔离。
- 已明确缺失 interface 实现选择、缺失必填对象参数、component/workflow 构造失败和错误实现选择的 `RuntimeError` 诊断。
- 已补充聚焦单测 `test_object_container_v2.py`，并与 `test_runtime_descriptor_v2.py` 共同回归通过。

## 未完成项

- 尚未接入 ATM / ModuleService 全执行链。
- 尚未实现运行模板 UI 的 `object_bindings` / `object_params` 编辑与保存。
- 尚未实现对象图结束后的 `close()` / `aclose()` 生命周期清理。
