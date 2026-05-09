# 构建模块

> 版本绑定：本文只适用于 0.4.x SDK / Contracts 与 Core 0.4.0。0.4.x SDK 是破坏性升级线，不兼容 0.3.x 的 CLI 命令、模板或模块开发模式。

## 1. 初始化

```bash
uvx --from crawler4j-sdk crawler4j module init
```

按提示输入模块名和升级源仓库；其他参数保持 0.4.x 默认值。需要脚本化时仍可完整传参：

```bash
uvx --from crawler4j-sdk crawler4j module init demo_module \
  --repo example/demo_module \
  --runtime-api core-native-v2

cd demo_module
uv sync
```

## 2. 创建装饰器骨架

```bash
uv run crawler4j interface create labor
uv run crawler4j component create api_labor --implements labor
uv run crawler4j workflow create main_workflow
uv run crawler4j page-action create open_login_page
uv run crawler4j data table create accounts
uv run crawler4j data table create account_snapshots --storage-mode managed_dataset
uv run crawler4j data view create account_overview --source accounts
```

这些命令写 Python 装饰器模板，不再把运行能力写入 `module.yaml`。

## 3. 写对象依赖

对象依赖可以写在 `inject` 里，也可以写成类属性注解。推荐新模块优先用类属性注解，构造函数参数名保持一致：

```python
from typing import Annotated

from crawler4j_contracts import component, object_inject


@component(
    name="account_orchestrator",
    implements="orchestrator",
)
class AccountOrchestrator:
    labor: Annotated[object, object_inject(type="interface", target="labor")]

    def __init__(self, labor):
        self.labor = labor
```

对象参数可以写在 `parameters` 里，也可以写到类属性或 `__init__` 参数注解里。未提供默认值的 `object_param()` 默认是必填参数：

```python
from typing import Annotated

from crawler4j_contracts import component, object_param


@component(
    name="api_labor",
    implements="labor",
)
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

## 4. 写 workflow

```python
from typing import Annotated

from crawler4j_contracts import object_inject, workflow


@workflow(name="main_workflow")
class MainWorkflow:
    def __init__(
        self,
        orchestrator: Annotated[object, object_inject(type="interface", target="orchestrator")],
    ):
        self.orchestrator = orchestrator

    async def run(self, ctx):
        return await self.orchestrator.run(ctx)
```

workflow 不接收普通参数。运行模板只保存对象实现选择和对象参数。

## 5. 写 page action

```python
@page_action(name="open_login_page")
async def open_login_page(ctx, url: str):
    await ctx.tools.call("browser.goto", url=url)
    return {"status": "opened", "title": await ctx.page.title() if ctx.page else None}
```

page action 是页面操作纯函数。不要在这里保存账号状态、缓存或跨任务对象。标准页面交互优先使用 `ctx.tools.call("browser.*", ...)`，`ctx.page` 主要保留给读取和宿主未覆盖能力。

## 6. 写数据契约

```python
@data_table(
    name="accounts",
    storage_mode="custom_table",
    schema=[
        {"name": "account_id", "type": "string", "required": True},
        {"name": "status", "type": "string"},
    ],
)
class Accounts:
    pass
```

`custom_table` 主键由 `record_key_field` 指定，未指定时取 schema 第一列。需要自增 id 时，把 `{"name": "id", "type": "integer", "auto_increment": True}` 声明为 `record_key_field` 对应列，并使用 `ctx.db.into("...").add(...)` 新增记录。

字段名不要使用宿主保留字段：

- `created_at`
- `updated_at`
- `create_at`
- `update_at`

来源系统时间戳用业务字段名，例如 `source_created_at`。

## 7. 校验

```bash
uv run crawler4j check full
uv run crawler4j manifest lock
```

`check full` 至少检查：

- `runtime_api == core-native-v2`
- 装饰器元数据合法
- 名称唯一
- inject 目标存在
- 对象图无环
- workflow 没有 parameters
- component 参数类型合法
- page action 是函数或 async 函数
- 数据字段、索引、视图 schema 不使用宿主保留字段
- `module.yaml` 没有 v2 禁止字段

## 8. 打包

```bash
uv run crawler4j check release
uv run crawler4j package build
uv run crawler4j package verify dist/demo_module-0.1.0.zip
```

打包阶段会复用扫描诊断，防止过期 lock 或保留字段冲突进入安装包。
