# 快速开始

这一页给你一条从零到可继续开发的最短路径。

目标不是一次看懂全部概念，而是 5 到 10 分钟内得到一个可检查、可调试、可继续扩展的标准模块项目。

## 开始前

你至少需要：

- Python `3.12+`
- `uv`
- 一个可写目录

先确认基础环境：

```bash
python3 --version
uv --version
uvx --from crawler4j-sdk crawler4j --help
```

如果这三条都跑不通，不要继续。

## 第一步：初始化模块项目

下面示例模块名使用 `hotel_demo`。

```bash
cd /absolute/path/to/your/workspace
uvx --from crawler4j-sdk crawler4j module init hotel_demo \
  --repo your-org/hotel_demo \
  --no-git \
  --no-install
cd /absolute/path/to/your/workspace/hotel_demo
uv sync
```

立即确认自己已经站在模块根目录：

```bash
pwd
test -f module.yaml && echo "OK: 当前就在模块根目录" || echo "ERROR: 当前不在模块根目录"
```

后面所有 `uv run crawler4j ...` 都默认在模块根目录执行。

标准脚手架会自带：

- `tasks/example_task.py`
- 一个初始 workflow 文件
- `module_runtime.py` 的 `declare_ui()` 壳子

先把这些文件当参考样板即可。

## 第二步：生成开发骨架

```bash
uv run crawler4j task create fetch_hotels
uv run crawler4j workflow create hotel_sync --display-name "酒店同步"
uv run crawler4j module set default-workflow hotel_sync
uv run crawler4j page create dashboard --display-name "Dashboard"
uv run crawler4j data-table create hotels --label "Hotels"
uv run crawler4j check structure
```

这些命令的真实副作用如下：

| 命令 | 会改什么 |
|---|---|
| `uv run crawler4j task create fetch_hotels` | 生成 `tasks/fetch_hotels.py` |
| `uv run crawler4j workflow create hotel_sync` | 生成 `workflows/hotel_sync.py`，并更新 `module.yaml.workflows` |
| `uv run crawler4j module set default-workflow hotel_sync` | 把默认 workflow 切到 `hotel_sync` |
| `uv run crawler4j page create dashboard` | 更新 `module.yaml.ui_extension.pages`，并在 `module_runtime.py` 追加 hosted page 骨架 |
| `uv run crawler4j data-table create hotels` | 更新 `module.yaml.ui_extension.pages`，并在 `module_runtime.py` 追加数据表声明 helper |
| `uv run crawler4j check structure` | 不改文件，只做骨架级自检 |

执行完后，模块根目录里最重要的 4 个现成落点是：

- `module.yaml`
- `tasks/fetch_hotels.py`
- `workflows/hotel_sync.py`
- `module_runtime.py`

后续重点就是改这几个文件，不要再发明第二套目录。

## 第三步：改清单和运行时

### `module.yaml`

至少先改这些字段：

- `display_name`
- `description`
- `upgrade_source.repo`
- `workflows[*].display_name`
- `config_defaults`
- `ui_extension.pages`

最小示例如下：

```yaml
name: hotel_demo
version: 0.1.0
display_name: 酒店采集示例
description: 酒店业务模块
author: crawler4j
upgrade_source:
  type: github_release
  repo: your-org/hotel_demo
  allow_prerelease: false
workflows:
  - name: hotel_sync
    display_name: 酒店同步
    description: 抓取并刷新酒店列表
ui_extension:
  pages:
    - id: dashboard
      label: Dashboard
      icon: 📄
      entry: core:page:dashboard
    - id: hotels
      label: Hotels
      icon: 📋
      entry: core:data_table:hotels
config_defaults:
  module:
    city: shanghai
    page_size: 20
  workflows:
    hotel_sync:
      retry_enabled: false
```

这里最容易抄错的一点：

- 当前正式 UI 入口只有 `core:page:<page_id>` 和 `core:data_table:<view_id>`
- 不再使用 `ui:DashboardPage`
- 也不再使用 `detail_menu`

### `module_runtime.py`

`page create dashboard` 会在 `module_runtime.py` 里生成这三类 hosted page 骨架：

- `build_dashboard_page_schema()`
- `load_dashboard_page(...)`
- `_declare_dashboard_page(context)`

`data-table create hotels` 会追加：

- `_declare_hotels_table(context)`

标准 `declare_ui()` 会变成：

```python
def declare_ui(context: TaskContext):
    _declare_dashboard_page(context)
    _declare_hotels_table(context)
    return None
```

你需要做的，是把 CLI 生成的宿主页 schema 和数据表 schema 改成真实业务内容，而不是再去创建 `ui/` 目录或 `PyQt6` 页面类。

### `tasks/fetch_hotels.py`

```python
from crawler4j_sdk import TaskContext, TaskResult, TaskScript


class FetchHotelsTask(TaskScript):
    name = "fetch_hotels"
    display_name = "抓取酒店列表"
    description = "抓取当前城市酒店列表"

    async def execute(self, ctx: TaskContext) -> TaskResult:
        city = ctx.get_config("city", "shanghai")
        if not ctx.page:
            return TaskResult.fail(
                message="当前环境没有可用 Page",
                error="page_not_available",
            )

        await ctx.page.goto(f"https://example.com/hotels?city={city}")
        records = [{"id": "hotel-001", "name": "示例酒店", "city": city}]

        if ctx.tools and ctx.tools.has_tool("db.replace_records"):
            ctx.tools.call("db.replace_records", dataset="hotels", records=records)

        return TaskResult.ok(
            message="抓取完成",
            data={"records": records},
        )
```

这里需要记住：

- `db.replace_records` 负责当前快照
- `db.append_event` / `db.query_events` 负责 append-only 历史
- `core:data_table` 不直接充当事件流水表

### `workflows/hotel_sync.py`

```python
from crawler4j_sdk import TaskContext, TaskFlow, TaskResult


class HotelSyncWorkflow(TaskFlow):
    name = "hotel_sync"
    display_name = "酒店同步"
    description = "同步酒店列表"

    async def run(self, ctx: TaskContext):
        ctx.state["phase"] = "fetch_hotels"
        payload = await ctx.run_subtask("fetch_hotels")
        if payload is False:
            return TaskResult.fail(
                message="fetch_hotels 执行失败",
                error="fetch_hotels_failed",
            )

        records = payload.get("records", []) if isinstance(payload, dict) else []
        return {"records": records}
```

## 第四步：补齐 hosted UI

推荐心智模型只有两条：

- `core:page:<page_id>`：宿主页，用于看板、概览页、组合展示
- `core:data_table:<view_id>`：宿主管理的数据表页，用于快照数据 CRUD

典型搭配：

- `dashboard` 用 hosted page 展示 KPI、说明和只读表格
- `hotels` 用 `core:data_table` 维护当前酒店快照

如果你需要页面加载数据，就改 `load_dashboard_page()`；
如果你需要数据表 CRUD，就改 `ui.declare_data_table` 对应的 schema 和 handler。

## 第五步：做最小自检

```bash
uv run crawler4j check structure
uv run crawler4j check full
uv run crawler4j package build
uv run crawler4j package verify dist/hotel_demo-0.1.0.zip
```

这四步至少说明：

- 模块骨架还合法
- `declare_ui()`、hosted page 和数据表声明可导入
- 打包结构没坏

## 第六步：接到宿主里调试

本地开发主路径：

```bash
uv run crawler4j host devlink add /absolute/path/to/hotel_demo
uv run crawler4j host debug config
```

然后在宿主里：

1. 打开模块详情页
2. 先看 `dashboard`
3. 再点 `hotels`
4. 点页面里的刷新或数据表里的刷新，确认最新 `declare_ui()` 已生效

如果宿主页或数据表没有出现，优先检查：

1. `module.yaml.ui_extension.pages`
2. `module_runtime.py` 里的 `declare_ui()`
3. `crawler4j check full`

## 最短成功标准

做到下面 6 条，就已经是一个可继续开发的合格起点：

1. `uv run crawler4j check structure` 通过
2. `uv run crawler4j check full` 通过
3. `module.yaml.workflows` 已切到真实 workflow
4. `module.yaml.ui_extension.pages` 已出现至少一个 `core:page` 或 `core:data_table`
5. `module_runtime.py` 已开始接入真实 hosted page / data table schema
6. 宿主 DevLink 能看到页面入口

下一步建议直接看 [UI 与数据表](ui-and-data-table.md) 和 [SDK 与 CLI 参考](reference-sdk-and-cli.md)。
