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

还要接受一条数据约束：

- `module.yaml.data` 必须存在，即使四段暂时都是空数组
- 表、视图、命名查询和种子统一登记在 `module.yaml.data.resources/views/queries/seeds`
- SQL 文件固定放 `data/sql/views/*.sql`、`data/sql/queries/*.sql`，种子固定放 `data/seeds/*.json`

## 目录扫描规则

Core 固定扫描：

- `tasks/*.py` -> `TASK` / `execute`
- `workflows/*.py` -> `WORKFLOW` / `run`
- `hooks/*.py` -> `handle`
- `env_selectors/*.py` -> `SELECTOR` / `select`
- `pages/*.py`、`pages/<group>/*.py` -> `PAGE` / 页面处理函数

这些导出会被 Core 归一化成宿主侧 descriptor。模块作者只写业务逻辑，不再写运行时装配代码。

另外，模块数据契约虽然不是“固定目录导出扫描”的一部分，但仍是正式加载门禁。Core 会在加载和安装时校验 `module.yaml.data` 并同步 `data/sql` / `data/seeds`；模块运行时代码只通过 `ctx.db` 访问已注册数据对象。`ctx.tools` 只用于非数据库类宿主能力，例如环境、资源池和代理等。
