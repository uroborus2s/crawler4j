# 快速开始

这一页给你一条从零到可继续开发的最短路径。

目标不是“看懂所有概念”，而是 5 到 10 分钟内得到一个可检查、可调试、可继续扩展的标准模块项目。

## 开始前

你至少需要:

- Python `3.12+`
- `uv`
- 一个可写目录

先确认基础环境:

```bash
python3 --version
uv --version
uvx --from crawler4j-sdk crawler4j --help
```

如果这三条都跑不通，不要继续。

## 第一步: 初始化模块项目

下面示例模块名用 `hotel_demo`。

如果你还没有真正创建 GitHub 仓库，也可以先填一个最终准备使用的 `owner/repo` 占位值。
当前 CLI 只要求它是合法的 `owner/repo` 形式；在你第一次做正式安装或发布前，再用
`uv run crawler4j module set repo <real-owner>/<real-repo>` 改成真实仓库即可。

```bash
cd /absolute/path/to/your/workspace
uvx --from crawler4j-sdk crawler4j module init hotel_demo \
  --repo your-org/hotel_demo \
  --no-git \
  --no-install
cd /absolute/path/to/your/workspace/hotel_demo
uv sync
```

立即确认自己已经站在模块根目录:

```bash
pwd
test -f module.yaml && echo "OK: 当前就在模块根目录" || echo "ERROR: 当前不在模块根目录"
```

后面所有 `uv run crawler4j ...` 都默认在模块根目录执行。

标准脚手架还会自带:

- `tasks/example_task.py`
- 一个初始 workflow 文件

先把它们当参考样板即可。等你自己的 `fetch_hotels` 和 `hotel_sync` 跑通后，再决定是否删除示例文件。

## 第二步: 生成开发骨架

```bash
uv run crawler4j task create fetch_hotels
uv run crawler4j workflow create hotel_sync --display-name "酒店同步"
uv run crawler4j module set default-workflow hotel_sync
uv run crawler4j data-table create hotels --label "Hotels"
uv run crawler4j page create dashboard --display-name "Dashboard"
uv run crawler4j check structure
```

这些命令的真实副作用如下:

| 命令 | 会改什么 |
|---|---|
| `uv run crawler4j task create fetch_hotels` | 生成 `tasks/fetch_hotels.py` |
| `uv run crawler4j workflow create hotel_sync` | 生成 `workflows/hotel_sync.py`，并更新 `module.yaml.workflows` |
| `uv run crawler4j module set default-workflow hotel_sync` | 把默认 workflow 从脚手架初始值切到 `hotel_sync` |
| `uv run crawler4j data-table create hotels` | 更新 `module.yaml.ui_extension.detail_menu`，并在 `module_runtime.py` 追加数据表声明 helper |
| `uv run crawler4j page create dashboard` | 生成 `ui/dashboard.py`，并更新 `ui_extension.entry` |
| `uv run crawler4j check structure` | 不改文件，只做骨架级自检 |

执行完后，模块根目录里已经有 5 个现成落点:

- `module.yaml`
- `tasks/fetch_hotels.py`
- `workflows/hotel_sync.py`
- `ui/dashboard.py`
- 根目录同级的 `module_runtime.py`

下面不是让你“再发明新文件”，而是直接改这几个现成文件。

## 第三步: 改这 5 个现成文件

### 1. `module.yaml`

至少先改:

- `display_name`
- `description`
- `upgrade_source.repo`
- `workflows[*].display_name`
- `config_defaults`

最小示例:

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
  type: micro_app
  entry: ui:DashboardPage
  detail_menu:
    - id: hotels
      icon: 📋
      label: Hotels
      entry: core:data_table:hotels
config_defaults:
  module:
    city: shanghai
    page_size: 20
  workflows:
    hotel_sync:
      retry_enabled: false
```

这里最容易抄错的一点:

- `ui:DashboardPage` 不是文件路径
- 它的意思是“`ui` 这个包导出的 `DashboardPage` 类”
- `page create dashboard` 已经帮你把 `ui/dashboard.py` 里的页面类导出到 `ui/__init__.py`

所以你通常不需要把它写成 `ui.dashboard:DashboardPage` 或 `ui/dashboard:DashboardPage`。

### 2. `tasks/fetch_hotels.py`

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

这里的两个工具名是宿主稳定契约，不是你自己发明的字符串:

- `db.replace_records`：同步写入快照数据集
- `db.append_event`：追加审计事件
- `ui.declare_data_table`：同步声明托管数据表 schema

这段示例故意只写“当前酒店列表快照”。如果你还要记录“这次抓取发生了什么”，历史应单独走审计事件通道，不要把日志行混进 `hotels` dataset，也不要指望 `core:data_table` 直接充当事件流水表。

完整工具列表和同步/异步语义，直接看 [Core 能力参考](reference-core-capabilities.md)。

### 3. `workflows/hotel_sync.py`

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

这段最短记忆只要记住一条:

- `run_subtask(...)` 优先返回子任务 `TaskResult.data`
- 如果子任务没有 `data`，它才退化成 `True` / `False`

所以这里先判断 `False`，再把成功载荷当 `dict` 读是故意的，不是魔法写法。

### 4. `ui/dashboard.py`

`page create dashboard` 已经生成了页面类文件。

如果你暂时只想验证“页面入口能被宿主加载”，把它保留成最小版本即可；如果你想让模块详情页顶部真正展示业务页，就改这里。

最小写法:

```python
from typing import Any

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DashboardPage(QWidget):
    def __init__(self, module: Any | None = None, parent=None):
        super().__init__(parent)
        self.module = module

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("酒店模块 Dashboard"))
```

如果这里的类名不再叫 `DashboardPage`，记得同时改两处:

1. `module.yaml.ui_extension.entry`
2. `ui/__init__.py` 里的页面类导出

少改任何一处，宿主加载页面入口时都会对不上。

### 5. `module_runtime.py`

当前 `module init` 一定会在模块根目录生成 `module_runtime.py`。
如果你没看到这个文件，说明脚手架不是用当前 CLI 正确初始化出来的，先回到第一步重建。

如果你刚执行过 `uv run crawler4j data-table create hotels`，CLI 已经做了两件事:

1. 在 `module.yaml.ui_extension.detail_menu` 注册 `core:data_table:hotels`
2. 在 `module_runtime.py` 里追加 `_declare_hotels_table(...)` helper，并让 `declare_ui(...)` 调它

所以下面不是从零新建，而是直接修改 CLI 生成的 helper。

下面这段示例只做一件事:

- 让你先得到一个“只读数据表”最小链路

它不会自动带上新增/编辑 handler。
如果你需要 `新增` / `编辑`，再去看 [UI 与数据表](ui-and-data-table.md) 里的完整版本。

把生成的 `_declare_hotels_table(...)` 改成这样:

```python
from crawler4j_sdk import TaskContext


def _declare_hotels_table(ctx: TaskContext):
    if not ctx.tools or not ctx.tools.has_tool("ui.declare_data_table"):
        return None

    return ctx.tools.call(
        "ui.declare_data_table",
        view_id="hotels",
        schema={
            "title": "酒店列表",
            "dataset": "hotels",
            "primary_key": "id",
            "display_fields": ["name", "city"],
            "columns": [
                {"key": "id", "label": "ID", "visible": False},
                {"key": "name", "label": "酒店名", "required": True},
                {"key": "city", "label": "城市", "required": True},
            ],
        },
    )
```

标准脚手架的根 `__init__.py` 会通过 `__getattr__` 自动转发 `module_runtime.py` 里的 hook。

只要你没手工改坏根入口，这一步不需要再碰 `__init__.py`。

这里声明的 `hotels` 也是“当前快照视图”，不是历史事件流。只要需求开始变成“我要回看每次变化”，就应该把历史转到审计事件通道，而不是继续扩张这张数据表。

## 第四步: 做最小检查

先在模块根目录跑:

```bash
uv run crawler4j check full
uv run crawler4j module show
```

你应该看到:

- `check full` 通过
- `module show` 里能看到模块名、默认 workflow、任务、页面入口和数据表入口

## 第五步: 在宿主里做最小验证

这一段不再是 CLI 命令，而是宿主内验证步骤。

先只记两个名词:

- DevLink: 让宿主直接加载你的本地模块源码目录
- ATM: 宿主里的 `📋 任务监控` 页面，负责创建作业、配置运行模板和执行任务

如果你现在只想完成“脚手架生成 + 文件改完 + 自检通过”，可以先停在第四步。

如果你要确认模块真的能被宿主加载，再按下面的最短路径走。

在宿主里按这个最短路径走:

1. `📦 模块管理` -> `🔗 添加开发模块`
2. 模块详情页确认 `来源: 开发链接`
3. `📋 任务监控` -> `+ 新建作业`
4. `配置运行模板` 里选中 `hotel_demo / hotel_sync`
5. 触发方式选 `执行一次`
6. 回到列表点 `▶ 执行一次`

如果你能看到任务实例、任务日志和阶段日志，说明最小链路已经通了。

第一次走宿主验证时，至少核对这 4 个事实:

1. 模块详情页显示 `来源: 开发链接`
2. 作业运行模板里选中的确实是 `hotel_demo / hotel_sync`
3. 回到任务监控列表后能看到 `▶ 执行一次`
4. 执行后在作业详情里能看到 `任务实例 (Tasks)` 和 `任务日志`

## 下一步看什么

- 想理解模块到底是什么: 看 [核心概念](core-concepts.md)
- 想搞清楚目录和 `module.yaml`: 看 [模块结构](module-structure.md)
- 想开始认真写业务: 看 [构建模块](build-modules.md)
- 想写页面或托管数据表: 看 [UI 与数据表](ui-and-data-table.md)
- 想继续走调试和交付: 看 [调试模块](debugging.md) 和 [交付模块](shipping.md)
