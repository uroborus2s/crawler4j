# 核心概念

## 角色分工

### Core

Core 负责：

- 扫描模块目录
- 生成 `ModuleRuntimeDescriptor`
- 执行任务、工作流、Hook、环境选择器和页面处理函数
- 注入 `TaskContext` 和宿主能力

Core 不再依赖模块根 `run()`，也不再要求模块提供装配器。

### Contracts

`crawler4j-contracts` 是模块运行时代码唯一允许依赖的共享契约包。

稳定导出包括：

- `TaskContext`
- `TaskResult`
- `TaskSignal`
- `EnvAction`
- `EnvCandidate`
- `TaskSpec`
- `WorkflowSpec`
- `EnvSelectorSpec`
- `PageSpec`

### SDK

`crawler4j-sdk` 现在只负责：

- CLI
- 模板生成
- 本地校验
- 打包与发布辅助
- 少量开发 helper

SDK 不再拥有运行时装配职责。

## 统一协议

模块必须在 `module.yaml` 声明：

```yaml
runtime_api: core-native-v1
default_workflow: main_workflow
```

没有这个字段，或值不对，Core 会直接拒绝加载。

## 目录扫描规则

Core 固定扫描：

- `tasks/*.py` -> `TASK` / `execute`
- `workflows/*.py` -> `WORKFLOW` / `run`
- `hooks/*.py` -> `handle`
- `env_selectors/*.py` -> `SELECTOR` / `select`
- `pages/*.py` -> `PAGE` / 页面处理函数

这些导出会被 Core 归一化成宿主侧 descriptor。模块作者只写业务逻辑，不再写运行时装配代码。
