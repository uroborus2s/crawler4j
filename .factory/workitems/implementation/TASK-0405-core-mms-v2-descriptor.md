# TASK-0405 建立 Core MMS v2 runtime descriptor

- 状态：DONE
- 负责人：Codex
- 优先级：P0
- 估算：2.0 人/天
- 关联 ID：`TASK-0405`, `TASK-0400`, `REQ-0400`, `API-012`, `TC-0400-004`

## 目标

- Core MMS 基于 v2 装饰器生成 `ModuleRuntimeDescriptorV2`。
- descriptor 扫描不实例化业务对象、不读取旧 manifest data/workflows 作为事实源。
- 明确要求 `runtime_api: core-native-v2`。

## 完成记录

- 已新增 `ModuleRuntimeDescriptorV2`、`V2RuntimeEntry` 与 `load_runtime_descriptor_v2()`。
- 已覆盖重复名称、缺失注入目标、循环依赖和不实例化行为。
- Core `ModuleScanner` / DevLink / install preflight 已切到 `core-native-v2` 清单与 v2 descriptor 校验，不再要求 `module.yaml.data/workflows/default_workflow`。
- Acceptance 已覆盖 SDK scaffold -> package verify、host DevLink add/list/remove、local ZIP preview/apply 的 v2 路径。

## 未完成项

- workflow 执行、生命周期清理和 ModuleService v2 执行接入待后续任务继续完成。
