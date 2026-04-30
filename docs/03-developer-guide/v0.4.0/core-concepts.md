# 核心概念

> 版本绑定：本文只描述 0.4.0 / `core-native-v2` 边界。0.4.x SDK 与 Contracts 是破坏性升级线，不兼容 `core-native-v1` 的 `TaskSpec` / `WorkflowSpec` 开发模式。

0.4.0 的核心变化是：运行能力事实源从 YAML 和顶层 spec 导出切到代码装饰器。

## 三个包的边界

### Core

0.4.0 中，Core 是唯一运行时 owner。

Core 负责：

- 扫描装饰器
- 生成 `ModuleRuntimeDescriptorV2`
- 根据运行模板创建对象图
- 为每个 task/env 创建独立对象容器
- 实例化 workflow
- 注入 `TaskContext`
- 调度 page action、环境和数据库能力
- 按依赖反向顺序调用 `cleanup(ctx, outcome)`

Core 可以缓存元数据、类引用和依赖图，但不能预创建业务对象实例。

### Contracts

`crawler4j-contracts` 是模块运行时代码唯一允许依赖的共享契约包。

0.4.x Contracts 主路径导出：

- `TaskContext`
- `TaskResult`
- `TaskOutcome`
- `EnvCandidate`
- `interface`
- `component`
- `workflow`
- `page_action`
- `data_table`
- `data_query`

装饰器只挂载元数据，不创建实例。

`TaskSignal`、`TaskSignalAction`、`EnvAction` 不再是模块运行时公开入口。模块 workflow 只能用 `TaskResult` 表达成功或失败；任务结束、失败、超时或用户中止后的环境统一由宿主回收。环境删除只走环境管理页的 `清理环境` 链路。

### SDK

`crawler4j-sdk` 只负责开发阶段：

- CLI
- 脚手架
- 装饰器扫描
- 本地校验
- 迁移辅助
- manifest lock
- 打包和发布辅助
- DevLink / host 辅助命令

SDK 不参与模块运行时装配。模块运行时代码不要 `import crawler4j_sdk`。

0.4.x SDK 只服务 Core 0.4.0，不保留 0.3.x CLI 命令、旧模板或旧模块开发模式。需要维护 0.3.x 模块时，切换到 0.3.x SDK / Contracts。

## Runtime API

`module.yaml` 只声明版本和宿主静态配置：

```yaml
runtime_api: core-native-v2
name: hotel_demo
version: 0.1.0
upgrade_source:
  repo: your-org/hotel_demo
```

`module.yaml` 不承载运行能力：

- 接口和对象来自装饰器
- workflow 来自装饰器
- page action 来自装饰器
- 数据表和命名查询来自装饰器
- 扫描快照来自 manifest lock

这些能力来自装饰器和 manifest lock。

## 运行能力模型

| 概念 | 声明方式 | 作用 |
|---|---|---|
| Interface | `@interface` | 可被实现的能力类型 |
| Component | `@component` | 可被宿主实例化的业务对象 |
| Workflow | `@workflow` | 宿主创建的 workflow 对象 |
| Page Action | `@page_action` | 页面操作纯函数 |
| Data Table | `@data_table` | 模块数据表声明 |
| Data Query | `@data_query` | 命名查询声明 |
| Manifest Lock | `crawler4j manifest lock` | SDK 扫描快照 |

## 对象图

workflow 是对象图根节点。Core 根据 workflow 的 `inject` 递归装配依赖：

1. 读取 workflow 注入声明
2. 遇到 interface，按运行模板选择 component 实现
3. 递归创建 component 的依赖
4. 把 component 参数传入对应构造函数
5. 创建 workflow 实例
6. 调用 `workflow.run(ctx)`

`inject` 和 component 对象参数既可以写在装饰器参数里，也可以通过 `Annotated[..., object_inject(...)]` / `Annotated[..., object_param(...)]` 写在类属性或 `__init__` 参数上。SDK 扫描后会归一成同一份对象图元数据。

选择实现的优先级：

1. 运行模板绑定
2. 唯一实现
3. 默认实现
4. 报错

## workflow 没有 parameters

workflow 只接收宿主注入对象：

```python
class HotelSyncWorkflow:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
```

普通参数只属于 component：

```python
class ApiLabor:
    def __init__(self, base_url: str, timeout: int = 30):
        ...
```

不要让 workflow 自己接收普通参数，也不要从 `ctx.runtime` 读取对象选择。

## 并发隔离

默认 scope 是 `task_env`：

- 同一 task/env 内共享同一个对象容器
- 不同 task/env 不共享 component 实例
- 不同 task/env 不共享 workflow 实例
- descriptor 可以缓存，实例不能全局缓存

如果 workflow 或 component 需要释放资源、打印终态日志或写审计事件，只实现 `cleanup(ctx, outcome)`。Core 会在 workflow 返回成功、返回失败、抛错、超时或被用户停止后统一收尾：先清理 workflow 实例，再按 component 依赖构造的反向顺序清理 component；某个对象清理失败只记录日志，不阻断任务终态和环境回收。`outcome.status` 只可能是 `succeeded`、`failed`、`timed_out` 或 `cancelled`。旧 `aclose()` / `close()` 不再是 0.4.0 对象生命周期契约。

```python
from crawler4j_contracts import TaskContext, TaskOutcome


class HotelSyncWorkflow:
    async def cleanup(self, ctx: TaskContext, outcome: TaskOutcome) -> None:
        ctx.logger.info(f"workflow finished: {outcome.status}")
        ctx.db.audit("workflow_events").append(
            event_type=f"workflow.{outcome.status}",
            entity_key=ctx.state.get("task_id"),
            payload={
                "error": outcome.error,
                "duration_seconds": outcome.duration_seconds,
            },
        )
```

## 数据入口

数据契约用装饰器声明，运行时代码仍只通过 `ctx.db` 访问。

```python
rows = ctx.db.from_("hotels").limit(50).execute()
detail = ctx.db.named("ready_hotels").bind(status="ready").execute()
ctx.db.into("hotels").replace(rows)
```

不要用：

- `ctx.tools.call("db.*")`
- `db.declare_data_resource(...)`
- `db.declare_db_view(...)`
- 未注册 SQL

`ctx.tools` 只用于非数据库宿主能力。
