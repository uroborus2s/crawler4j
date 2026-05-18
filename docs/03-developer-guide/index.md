# 开发者指南

开发者指南按产品版本物理隔离。先确认你要开发的目标版本，再进入对应目录。

## 当前 0.4.0 版本

[开发者指南 0.4.0](./v0.4.0/index.md) 面向当前分支的模块契约：

- Runtime API：`core-native-v2`
- 运行能力事实源：代码装饰器
- 对象装配：`@interface`、`@component`、`@workflow`
- 页面操作：`@page_action`
- 数据契约：`@data_table`、`@data_view`
- 交付门禁：`crawler4j manifest lock` 与装饰器诊断

开发 0.4.0 新模块、验证装饰器对象装配方案、或准备从 0.3.x 迁移时，使用这一版。

## 历史稳定版本

[开发者指南 0.3.0](./v0.3.0/index.md) 面向历史稳定模块契约：

- Runtime API：`core-native-v1`
- 运行能力事实源：`module.yaml` 与固定目录导出
- 任务和工作流：`TASK/execute`、`WORKFLOW/run`
- 数据契约：`module.yaml.data`、`data/sql`、`data/seeds`

维护 0.3.x 模块、修复历史已发布模块、或对接 0.3.x 维护分支时，使用这一版。

## 版本绑定矩阵

| 指南版本 | 覆盖产品线 | Runtime API | SDK / Contracts 口径 | 状态 | 是否用于生产模块 |
|---|---|---|---|---|---|
| `v0.4.0` | `crawler4j 0.4.0` 破坏性升级契约 | `core-native-v2` | 只能使用 0.4.x SDK / Contracts 与 v2 CLI | 当前分支 | 是 |
| `v0.3.0` | `crawler4j 0.3.x` 稳定契约 | `core-native-v1` | 只能使用 0.3.x SDK / Contracts 与 v1 CLI | 历史维护 | 仅限 0.3.x 分支 |

SDK、Contracts 和 Core 按产品线绑定，不做跨大版本兼容。0.4.x SDK / Contracts 只面向 `crawler4j 0.4.0` 与 `core-native-v2`，不会保留 0.3.x 的 `task`、`workflow`、`env-selector`、`hook`、`data resource/view/seed` 等开发命令和模板。维护 0.3.x 模块时必须继续使用 0.3.x SDK / Contracts。

## 版本选择规则

- 不要把 0.4.0 装饰器写法回填到 0.3.0 模块。
- 不要用 0.4.x SDK / Contracts 开发或修复 0.3.x 模块；也不要期望 0.4.x CLI 兼容 0.3.x 命令。
- 不要在 0.4.0 新模块里继续维护 `module.yaml.workflows[].parameters[]`、`TASK = TaskSpec(...)`、`WORKFLOW = WorkflowSpec(...)` 或 `module.yaml.data` 数据事实源。
- 根目录只做版本选择；具体开发步骤都在 `v0.3.0/` 或 `v0.4.0/` 下维护。
