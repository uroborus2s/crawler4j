# 快速开始

> 版本绑定：本文只适用于 0.4.x SDK / Contracts 与 Core 0.4.0。0.4.x SDK 不兼容 0.3.x 命令和开发模式；维护 0.3.x 模块时不要使用本页命令。

这一页只走 0.4.0 最短闭环：

1. 初始化 `core-native-v2` 模块
2. 声明 interface / component / workflow
3. 声明 page action 和数据契约
4. 生成 manifest lock
5. 用 DevLink 接到宿主联调

## 1. 初始化模块

```bash
cd /absolute/path/to/your/workspace
uvx --from crawler4j-sdk crawler4j module init
```

交互式输入必填项，其余使用 0.4.x 默认值：

```text
模块包名（snake_case）: hotel_demo
升级源 GitHub 仓库（owner/repo）: your-org/hotel_demo
```

资深开发者也可以一次性传入参数：

```bash
uvx --from crawler4j-sdk crawler4j module init hotel_demo \
  --repo your-org/hotel_demo \
  --runtime-api core-native-v2 \
  --no-git \
  --no-install

cd /absolute/path/to/your/workspace/hotel_demo
uv sync
uv run crawler4j module show
```

初始化后的关键事实：

- `module.yaml.runtime_api` 是 `core-native-v2`
- `module.yaml` 只保留模块元信息、升级源、页面菜单、配置默认值等静态宿主配置
- 运行能力来自代码装饰器
- manifest lock 由 SDK 生成，不手写
- 运行时代码只依赖 `crawler4j-contracts`
- SDK 只作为开发依赖
- 0.4.x SDK 不生成 `TaskSpec`、`WorkflowSpec`、`module.yaml.data`、`hooks/` 或 `env_selectors/` 旧骨架

## 2. 创建能力骨架

```bash
uv run crawler4j interface create labor
uv run crawler4j component create api_labor --implements labor
uv run crawler4j interface create orchestrator
uv run crawler4j component create hotel_orchestrator --implements orchestrator
uv run crawler4j workflow create hotel_sync
uv run crawler4j page-action create open_home_page
uv run crawler4j data table create hotels
uv run crawler4j data table create hotel_snapshots --storage-mode managed_dataset
uv run crawler4j data view create hotel_overview --source hotels
```

这一步创建装饰器模板。不要手写第二套运行能力清单。

## 3. 声明接口和组件

目标文件：`interfaces/labor.py`、`objects/api_labor.py`。

```python
from typing import Annotated

from crawler4j_contracts import component, interface, object_param


@interface(name="labor", label="劳保能力")
class Labor:
    pass


@component(
    name="api_labor",
    label="API 劳保对象",
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

普通参数只属于 component 创建。运行模板里的 `object_params.api_labor` 会用于创建 `ApiLabor(...)`，不会传给 workflow。

## 4. 声明业务编排对象

目标文件：`objects/hotel_orchestrator.py`。

```python
from typing import Annotated

from crawler4j_contracts import component, object_inject


@component(
    name="hotel_orchestrator",
    label="酒店同步编排器",
    implements="orchestrator",
)
class HotelOrchestrator:
    labor: Annotated[object, object_inject(type="interface", target="labor")]

    def __init__(self, labor):
        self.labor = labor

    async def run(self, ctx):
        await ctx.run_page_action("open_home_page", url="https://example.com")
        return {"count": 0}
```

业务编排放在 workflow 注入的对象里。page action 只做页面操作。

## 5. 声明 workflow

目标文件：`workflows/hotel_sync.py`。

```python
from typing import Annotated

from crawler4j_contracts import object_inject, workflow


@workflow(name="hotel_sync", label="酒店同步")
class HotelSyncWorkflow:
    def __init__(
        self,
        orchestrator: Annotated[object, object_inject(type="interface", target="orchestrator")],
    ):
        self.orchestrator = orchestrator

    async def run(self, ctx):
        return await self.orchestrator.run(ctx)
```

workflow 构造函数只接收注入对象。不要写 workflow `parameters`，也不要从 `ctx.runtime.params` 读取对象选择。

## 6. 声明 page action

目标文件：`tasks/open_home_page.py`。这里的 `tasks/` 是 v2 迁移保留目录名，不再表示 v1 `TaskSpec` 任务。

```python
from crawler4j_contracts import page_action


@page_action(name="open_home_page", label="打开首页")
async def open_home_page(ctx, url: str):
    if not ctx.tools or not ctx.tools.has_tool("browser.goto"):
        return {"opened": False, "error": "browser.goto_unavailable"}
    await ctx.tools.call("browser.goto", url=url)
    return {"opened": url, "title": await ctx.page.title() if ctx.page else None}
```

page action 必须是函数或 async 函数。它不保存业务状态，也不承担 workflow 编排。标准页面交互优先通过 `ctx.tools.call("browser.*", ...)` 调用宿主拟人化能力；`ctx.page` 保留给标题、HTML、可见性等读取或宿主未覆盖能力。

## 7. 声明数据契约

目标文件：`data/hotels.py`。

```python
from crawler4j_contracts import data_table, data_view


@data_table(
    name="hotels",
    label="酒店",
    storage_mode="custom_table",
    schema=[
        {"name": "hotel_id", "type": "string", "required": True},
        {"name": "name", "type": "string"},
        {"name": "source_created_at", "type": "string"},
    ],
    indexes=[{"fields": ["hotel_id"], "unique": True}],
)
class HotelsTable:
    pass


@data_view(
    name="hotel_overview",
    sources=["hotels"],
    sql="SELECT hotel_id, name FROM {{resource:hotels}}",
    schema=[
        {"name": "hotel_id", "type": "string"},
        {"name": "name", "type": "string"},
    ],
)
def hotel_overview():
    pass
```

不要声明 `created_at`、`updated_at`、`create_at`、`update_at`。宿主拥有这些字段，SDK 会阻断。

## 8. 校验并生成 lock

```bash
uv run crawler4j check full
uv run crawler4j manifest lock
```

`check full` 和 `manifest lock` 会扫描装饰器、检查对象图、检查数据字段保留名。lock 通过后会生成：

```text
.crawler4j/manifest.lock.json
```

这个文件是扫描快照，不是手写清单。

## 9. 接入宿主联调

这是 0.4.0 验收路径，只适用于 Core 0.4.0。不要用 0.3.x 宿主或 0.3.x SDK 验证本页模块。

切到宿主环境：

```bash
uv run python -c "import src.core; print('ok: host runtime ready')"
uv run crawler4j host devlink add /absolute/path/to/hotel_demo
uv run crawler4j host debug config
```

联调顺序：

1. 在模块管理页确认来源是 `开发链接`
2. 在任务监控里创建运行模板
3. 选择 `hotel_sync`
4. 在对象装配区选择 `orchestrator`、`labor` 实现
5. 填写 `api_labor` 的对象参数
6. 先执行一次
7. 需要断点时再进入调试

运行模板保存的是对象装配，不是 workflow 参数：

```yaml
execution:
  module: hotel_demo
  workflow: hotel_sync
  object_bindings:
    orchestrator: hotel_orchestrator
    orchestrator.labor: api_labor
  object_params:
    api_labor:
      base_url: https://labor.example.com
      timeout: 30
```

## 10. 构建 ZIP

```bash
uv run crawler4j check release
uv run crawler4j package build
uv run crawler4j package verify dist/hotel_demo-0.1.0.zip
```

正式安装前，至少确认 `check full`、`manifest lock`、`package verify` 都通过。
