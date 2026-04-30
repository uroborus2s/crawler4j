# 装饰器与对象装配

> 状态：设计预览。本文描述目标装饰器 API 和对象装配规则；即使 contracts 中已有部分装饰器元数据能力，SDK CLI、DevLink、ZIP 验收和 Core v2 对象装配仍未形成完整可执行闭环。

0.4.0 的模块能力用装饰器声明。Core 扫描元数据，运行时按模板装配对象。

## 装饰器列表

| 装饰器 | 用途 |
|---|---|
| `@interface` | 声明能力接口 |
| `@component` | 声明可创建业务对象 |
| `@workflow` | 声明 workflow 类 |
| `@page_action` | 声明页面操作纯函数 |
| `@data_table` | 声明数据表 |
| `@data_query` | 声明命名查询 |

装饰器只挂元数据。实例创建由 Core 完成。

## Interface

```python
from crawler4j_contracts import interface


@interface(name="labor", label="劳保能力")
class Labor:
    pass
```

接口名使用小写 snake_case。

## Component

```python
from crawler4j_contracts import component


@component(
    name="api_labor",
    label="API 劳保对象",
    implements="labor",
    parameters=[
        {"name": "base_url", "type": "string", "required": True},
        {"name": "timeout", "type": "integer", "default": 30},
    ],
)
class ApiLabor:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
```

`parameters` 只用于创建这个 component。它不是 workflow 参数。

## Component 注入其他对象

```python
@component(
    name="quiz_orchestrator",
    label="做题编排器",
    implements="orchestrator",
    inject=[
        {"name": "labor", "type": "interface", "target": "labor"},
        {"name": "client", "type": "object", "target": "ctrip_client"},
    ],
)
class QuizOrchestrator:
    def __init__(self, labor, client):
        self.labor = labor
        self.client = client
```

`type=interface` 表示由运行模板选择实现。`type=object` 表示固定注入某个 component。

## Workflow

```python
from crawler4j_contracts import workflow


@workflow(
    name="quiz_workflow",
    label="统一做题",
    inject=[
        {"name": "orchestrator", "type": "interface", "target": "orchestrator"},
    ],
)
class QuizWorkflow:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    async def run(self, ctx):
        return await self.orchestrator.run(ctx)
```

workflow 不允许声明 `parameters`。需要普通参数时，把参数放在具体 component 上。

## Page Action

```python
from crawler4j_contracts import page_action


@page_action(name="open_login_page", label="打开登录页")
async def open_login_page(ctx, url: str):
    await ctx.page.goto(url)
    return {"url": url}
```

page action 规则：

- 必须是函数或 async 函数
- 第一个参数是 `ctx`
- 不由 Core 实例化
- 不保存跨任务状态
- 返回 `TaskResult` 或 JSON-like dict

workflow 或编排对象通过 `ctx.run_page_action(...)` 调用：

```python
await ctx.run_page_action("open_login_page", url="https://example.com")
```

## 运行模板保存什么

运行模板保存对象绑定和对象参数：

```yaml
execution:
  module: ctrip_crawler
  workflow: quiz_workflow
  object_bindings:
    orchestrator: quiz_orchestrator
    orchestrator.labor: api_labor
    orchestrator.client: ctrip_client
  object_params:
    api_labor:
      base_url: https://labor.example.com
      timeout: 30
```

运行模板不保存 workflow 普通参数。

## Core 装配流程

1. 读取 workflow 的 `inject`
2. 遇到 interface，按 `object_bindings` 选实现
3. 递归装配 component 的 `inject`
4. 用 `object_params` 创建 component
5. 创建 workflow 实例
6. 调用 `workflow.run(ctx)`
7. 任务结束后反向清理对象

不同 task/env 会创建不同对象实例。不要把业务状态放到模块全局变量里。

## 构造函数规则

component 构造函数可以接收：

- `inject.name` 对应对象
- `parameters[].name` 对应普通值

workflow 构造函数只能接收：

- `inject.name` 对应对象

第一版不自动把 `ctx` 注入构造函数。需要上下文时，在 `run(ctx)` 或业务方法中传入。

## 诊断

`check full` 会阻断：

- workflow 声明 `parameters`
- inject 目标不存在
- interface 没有可选实现
- 对象图有环
- 用户输入任意 import path
- page action 不是函数
- 装饰器名称重复
