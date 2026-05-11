# 装饰器与对象装配

> 版本绑定：本文描述 0.4.x Contracts 装饰器 API 和 Core 0.4.0 对象装配规则。0.4.x 装饰器不是 0.3.x spec 导出的兼容层。

0.4.0 的模块能力用装饰器声明。Core 扫描元数据，运行时按模板装配对象。

## 装饰器列表

| 装饰器 | 用途 |
|---|---|
| `@interface` | 声明能力接口 |
| `@component` | 声明可创建业务对象 |
| `@workflow` | 声明 workflow 类 |
| `@page` | 声明 Hosted UI 页面和 load handler |
| `@page_action` | 声明页面操作纯函数 |
| `@ui_action` | 声明 Hosted UI 用户操作函数 |
| `@data_table` | 声明数据表 |
| `@data_view` | 声明只读数据库视图 |

装饰器只挂元数据。实例创建由 Core 完成。

`@component` / `@workflow` 的对象依赖和 component 对象参数可以继续写在装饰器参数里，也可以写成类属性注解或 `__init__` 参数注解。三种写法最终都会归一成同一份 `InjectSpec` / `ParameterSpec` 元数据，SDK scanner、manifest lock 和 Core 对象容器使用同一条链路。

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

等价的注解写法：

```python
from typing import Annotated

from crawler4j_contracts import component, object_param


@component(name="api_labor", label="API 劳保对象", implements="labor")
class ApiLabor:
    base_url: Annotated[str, object_param(label="Base URL")]

    def __init__(
        self,
        base_url: str,
        timeout: Annotated[int, object_param(min=1, max=120)] = 30,
    ):
        self.base_url = base_url
        self.timeout = timeout
```

未提供默认值的 `object_param()` 默认视为必填；带 Python 默认值、`object_param(default=...)` 或 `Optional[T]` / `T | None` 的参数默认视为可选。

`object_param(...)` 支持的元数据字段：

- `name`、`type`、`label`、`description`、`required`、`default`
- `options`：`enum` 可选项，支持 `{"label": "...", "value": ...}` 或直接写字面量值
- `min`、`max`、`step`：仅用于 `integer` / `number`
- `placeholder`
- `schema`：`object` 的字段 schema，或 `dict[str, T]` 推断出的 `additional_type`
- `item_schema`：`array` 的元素 schema

`object_param` 支持的参数类型为：

| 类型 | Python 注解推断 | 运行时值 |
|---|---|---|
| `string` | `str` | `str` |
| `text` | 显式 `type="text"` | `str` |
| `integer` | `int` | `int`，不接受 `bool` |
| `number` | `float` | `int` / `float`，不接受 `bool` |
| `boolean` | `bool` | `bool` |
| `enum` | `Literal[...]` 或显式 `type="enum"` | 必须命中 `options` |
| `array` | `list[T]` / `tuple[T, ...]` | `list` / `tuple`，会按 `item_schema` 校验并归一为 `list` |
| `object` | `dict[str, T]` | `Mapping`，会按 `schema.fields` 或 `additional_type` 校验并归一为 `dict` |
| `json` | 显式 `type="json"` | JSON-like 值：`None`、字符串、数字、布尔、数组、字符串键对象 |
| `date` | `datetime.date` | `date` 或 ISO date 字符串，运行时归一为 `date` |
| `datetime` | `datetime.datetime` | `datetime` 或 ISO datetime 字符串，运行时归一为 `datetime` |
| `time` | `datetime.time` | `time` 或 ISO time 字符串，运行时归一为 `time` |
| `url` | 显式 `type="url"` | 含 scheme 与 netloc 的 URL 字符串 |
| `path` | `pathlib.Path` | `str` / `Path`，运行时归一为 `Path` |
| `secret` | 显式 `type="secret"` | `str`；用于 UI/模板侧按敏感值处理 |

示例：

```python
from datetime import date, datetime, time
from pathlib import Path
from typing import Annotated, Literal

from crawler4j_contracts import component, object_param


@component(name="api_labor", implements="labor")
class ApiLabor:
    mode: Annotated[Literal["sync", "async"], object_param(default="sync")]
    tags: Annotated[list[str], object_param(default=["default"])]
    limits: Annotated[dict[str, int], object_param(default={"daily": 10})]
    download_dir: Annotated[Path, object_param()]

    def __init__(
        self,
        start_date: Annotated[date, object_param()],
        deadline: Annotated[datetime, object_param()],
        run_at: Annotated[time, object_param()],
    ):
        self.start_date = start_date
        self.deadline = deadline
        self.run_at = run_at
```

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

注入也可以写成类属性注解：

```python
from typing import Annotated

from crawler4j_contracts import component, object_inject


@component(name="quiz_orchestrator", label="做题编排器", implements="orchestrator")
class QuizOrchestrator:
    labor: Annotated[object, object_inject(type="interface", target="labor")]
    client: Annotated[object, object_inject(type="object", target="ctrip_client")]

    def __init__(self, labor, client):
        self.labor = labor
        self.client = client
```

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

workflow 注入也可以写到 `__init__` 参数注解：

```python
from typing import Annotated

from crawler4j_contracts import object_inject, workflow


@workflow(name="quiz_workflow", label="统一做题")
class QuizWorkflow:
    def __init__(
        self,
        orchestrator: Annotated[
            object,
            object_inject(type="interface", target="orchestrator"),
        ],
    ):
        self.orchestrator = orchestrator

    async def run(self, ctx):
        return await self.orchestrator.run(ctx)
```

## Page

```python
from crawler4j_contracts import HostedPageLoadResult, HostedPageParams, TaskContext, page


@page(
    name="dashboard",
    label="Dashboard",
    icon="chart",
    menu=True,
    schema={
        "type": "Page",
        "title": "Dashboard",
        "children": [
            {"type": "Text", "style": "title", "binding": "title"},
        ],
    },
)
def load_dashboard_page(
    context: TaskContext,
    page_id: str,
    params: HostedPageParams | None = None,
) -> HostedPageLoadResult:
    del context, page_id, params
    return {"title": "Dashboard"}
```

page 规则：

- 必须装饰同步函数
- `name` 是唯一扁平 snake_case
- `menu=True` 进入左侧菜单；`menu=False` 只注册可路由页面
- `schema` 顶层必须是 `Page`
- 被装饰函数就是页面 `load_handler`

## Page Action

```python
from crawler4j_contracts import page_action


@page_action(name="open_login_page", label="打开登录页")
async def open_login_page(ctx, url: str):
    await ctx.tools.call("browser.goto", url=url)
    return {"url": url, "title": await ctx.page.title() if ctx.page else None}
```

page action 规则：

- 必须是函数或 async 函数
- 第一个参数是 `ctx`
- 不由 Core 实例化
- 不保存跨任务状态
- 返回 `TaskResult` 或 JSON-like dict
- 只由 workflow 或 component 通过 `ctx.run_page_action(...)` 调用，不作为 Hosted UI 按钮入口

workflow 或编排对象通过 `ctx.run_page_action(...)` 调用：

```python
await ctx.run_page_action("open_login_page", url="https://example.com")
```

标准页面交互优先走 `ctx.tools.call("browser.*", ...)`。`ctx.page` 继续保留给读取类操作和宿主暂未抽象的浏览器能力。

不要在 `@page_action` 函数里再调用另一个 `@page_action` 来拆公共步骤。公共页面操作应抽成普通 helper、browser adapter 或 application use case；多个可观测页面动作的顺序编排应留在 workflow/component。

## UI Action

```python
from crawler4j_contracts import ui_action


@ui_action(name="create_account_from_ui", label="创建账号")
def create_account_from_ui(ctx, payload: dict):
    ctx.db.into("accounts").upsert([payload])
    return {"ok": True}
```

UI action 规则：

- 必须是函数或 async 函数
- 第一个参数是 `ctx`
- 面向 Hosted UI 按钮、CRUD handler 和用户命令
- 不依赖 `ctx.page`，不执行浏览器自动化，不调用 `ctx.run_page_action(...)`
- 可使用 `ctx.db` 读写模块数据
- 返回 JSON-like dict/list/标量

Hosted UI schema 使用 `type: "ui_action"`：

```python
{
    "type": "Button",
    "label": "创建账号",
    "action": {
        "type": "ui_action",
        "name": "create_account_from_ui",
        "params": {"account_id": {"binding": "selected.id"}},
    },
}
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

运行模板 UI 会按 `workflow -> interface 绑定行 -> 子 interface/参数` 展示树形对象图。interface 绑定行左侧显示 interface 的 `label(name)`，右侧下拉框显示可选 component 的 `label(name)`；注入路径只作为绑定 key 与提示信息保留，不再额外显示一行“注入对象”。interface 与 component 都优先显示装饰器 `label`，因此可以写成中文；选择实现时写入 `object_bindings`；在绑定行下填写的 `object_param(...)` 创建参数写入 `object_params`。

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
- 注解 helper 使用了非字面量元数据或非法名称
- 用户输入任意 import path
- page action 不是函数
- 装饰器名称重复
