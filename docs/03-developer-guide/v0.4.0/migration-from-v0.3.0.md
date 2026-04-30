# 从 v0.3.0 迁移

> 版本绑定：迁移是一次破坏性重写，不是兼容升级。先用 0.3.x SDK 保留和验证旧基线，再切到 0.4.x SDK / Contracts 重写为 `core-native-v2`；0.4.x SDK 不负责继续维护 0.3.x 开发模式。

这一页只用于迁移。新模块不要先写 v0.3.0 结构再迁移。

## 迁移判断

如果模块里还有这些内容，它仍是 v0.3.0 / `core-native-v1` 思路：

- `TaskSpec`
- `WorkflowSpec`
- `WORKFLOW = WorkflowSpec(...)`
- `TASK = TaskSpec(...)`
- `module.yaml.workflows[].parameters[]`
- `module.yaml.data`
- `module_runtime.py`
- `TaskScript`
- `TaskFlow`
- `ModuleAssembler`
- `declare_ui()`
- `ctx.tools.call("db.*")`

## 一次迁移的推荐顺序

1. 新建迁移分支，保留 v0.3.x 可运行基线
2. 用 0.3.x SDK 在 v0.3.x 状态下完成最后一次基线校验
3. 切换开发环境到 0.4.x SDK / Contracts
4. 运行 0.4.x 迁移诊断报告
5. 把 workflow 迁到 `@workflow`
6. 把业务编排迁到 `@component`
7. 把 task 迁到 `@page_action`
8. 把 `module.yaml.data` 迁到 `@data_table` / `@data_query`
9. 移除旧 SDK 命令产物、旧固定导出和旧数据目录事实源
10. 修复装饰器扫描和保留字段诊断
11. 最后再切 `runtime_api` 到 `core-native-v2`
12. 生成 manifest lock
13. 用 Core 0.4.0 DevLink 回归运行模板和页面

```bash
uv run crawler4j migrate native-v2
uv run crawler4j check full
uv run crawler4j manifest lock
```

## WorkflowSpec 到 @workflow

旧写法：

```python
WORKFLOW = WorkflowSpec(
    name="hotel_sync",
    tasks=("fetch_hotels",),
)


async def run(ctx):
    return await ctx.run_subtask("fetch_hotels")
```

新写法：

```python
@workflow(
    name="hotel_sync",
    inject=[
        {"name": "orchestrator", "type": "interface", "target": "orchestrator"},
    ],
)
class HotelSyncWorkflow:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    async def run(self, ctx):
        return await self.orchestrator.run(ctx)
```

## workflow parameters 到 component parameters

旧写法：

```yaml
workflows:
  - name: hotel_sync
    parameters:
      - name: base_url
        type: string
```

新写法：

```python
from typing import Annotated

from crawler4j_contracts import component, object_param


@component(
    name="api_labor",
    implements="labor",
)
class ApiLabor:
    base_url: Annotated[str, object_param()]

    def __init__(self, base_url: str):
        self.base_url = base_url
```

运行模板会把值保存到 `object_params.api_labor.base_url`。

## TaskSpec 到 @page_action

旧写法：

```python
TASK = TaskSpec(name="open_login_page")


async def execute(ctx):
    await ctx.page.goto("https://example.com")
```

新写法：

```python
@page_action(name="open_login_page")
async def open_login_page(ctx, url: str):
    await ctx.page.goto(url)
    return {"opened": True}
```

如果旧 task 里有业务编排，把编排代码移入 orchestrator component。

## module.yaml.data 到装饰器

旧写法：

```yaml
data:
  resources:
    - id: accounts
      storage_mode: custom_table
```

新写法：

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

如果旧资源是 `managed_dataset`，新写法改为 `@data_table(storage_mode="managed_dataset", ...)`，数据仍落到 `module_datasets`。命名查询迁到 `@data_query`，但 SQL 继续只能引用 `custom_table` 的 `{{resource:<id>}}`。

## 数据字段改名

迁移时重点查这些字段：

- `created_at`
- `updated_at`
- `create_at`
- `update_at`

它们不能作为模块业务列进入 v2。改成业务字段名，例如：

- `source_created_at`
- `source_updated_at`

## 最后检查

```bash
uv run crawler4j check full
uv run crawler4j manifest lock
uv run crawler4j package verify dist/<module>-<version>.zip
```

迁移完成的最小判断：

- `module.yaml` 不再承载对象图、workflow 参数和数据契约
- 模块工程不再依赖 0.3.x SDK 命令生成的 `TaskSpec`、`WorkflowSpec`、`hooks/`、`env_selectors/` 或 `data/sql` 事实源
- lock 来自当前源码扫描
- 运行模板只展示对象装配和 component 参数
- 数据访问只走 `ctx.db`
