# 开发者指南

开发者指南按产品版本物理隔离。先确认你要开发的目标版本，再进入对应目录。

## 当前发布版本

[开发者指南 0.3.0](./v0.3.0/index.md) 面向当前稳定模块契约：

- Runtime API：`core-native-v1`
- 运行能力事实源：`module.yaml` 与固定目录导出
- 任务和工作流：`TASK/execute`、`WORKFLOW/run`
- 数据契约：`module.yaml.data`、`data/sql`、`data/seeds`

维护 0.3.x 模块、修复已发布模块、或对接当前稳定宿主时，使用这一版。

## 开发中版本

[开发者指南 0.4.0](./v0.4.0/index.md) 面向开发中的新模块契约：

- Runtime API：`core-native-v2`
- 运行能力事实源：代码装饰器
- 对象装配：`@interface`、`@component`、`@workflow`
- 页面操作：`@page_action`
- 数据契约：`@data_table`、`@data_query`
- 交付门禁：`crawler4j manifest lock` 与装饰器诊断

开发 0.4.0 新模块、验证装饰器对象装配方案、或准备从 0.3.x 迁移时，使用这一版。0.4.0 未发布前只作为开发版预览，不替代当前发布版指南。

## 兼容矩阵

| 指南版本 | 覆盖产品线 | Runtime API | SDK / Contracts 口径 | 状态 | 是否用于生产模块 |
|---|---|---|---|---|---|
| `v0.3.0` | `crawler4j 0.3.x` 稳定契约；当前源码线为 `crawler4j 0.3.2` | `core-native-v1` | 当前 SDK CLI 与 contracts 运行契约 | 当前可执行 | 是 |
| `v0.4.0` | `crawler4j 0.4.0` 目标契约 | `core-native-v2` | 目标 SDK / Contracts / Core 重构 | 设计预览 | 否 |

`crawler4j-contracts` 包版本可能先于宿主产品版本增长。选择指南时以宿主 runtime API 和模块契约为准，不以单个子包版本号判断。

## 版本选择规则

- 不要把 0.4.0 装饰器写法回填到 0.3.0 模块。
- 不要在 0.4.0 新模块里继续维护 `module.yaml.workflows[].parameters[]`、`TASK = TaskSpec(...)`、`WORKFLOW = WorkflowSpec(...)` 或 `module.yaml.data` 数据事实源。
- 根目录只做版本选择；具体开发步骤都在 `v0.3.0/` 或 `v0.4.0/` 下维护。
