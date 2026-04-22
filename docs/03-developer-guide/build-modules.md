# 构建模块

这一页回答一个问题：标准模块应该怎么从“目录骨架”写成“可联调、可交付、可升级”的业务模块。

最短答案是：

- 用 `task` 写原子动作
- 用 `workflow` 写流程编排
- 用 `module_runtime.py` 接宿主生命周期、环境选择器和 Hosted UI V1
- 先用 `check` 跑通模块工程和 DevLink 联调，再用 `package`、`release`、`host` 收口成正式交付物

## 开发顺序固定按这条线走

推荐顺序不要改：

1. `module init`
2. `task create`
3. `workflow create`
4. `page create` / `data-table create`
5. 补 `module.yaml`、`tasks/`、`workflows/`、`module_runtime.py`
6. `check full`
7. DevLink 联调
8. `package build`
9. `release publish`
10. `host upgrade`

这样做的好处是，CLI、源码、宿主、交付链路始终是同一条主线，不会出现“本地能跑，正式安装不通”的双轨结构。

## 先把命令树映射到开发动作

| 命令组 | 你在开发时什么时候用 |
|---|---|
| `task` | 新增一个原子业务动作时 |
| `workflow` | 新增一个业务流程或默认工作流时 |
| `page` | 需要概览页、看板、说明页时 |
| `data-table` | 需要维护当前快照数据时 |
| `env-selector` | 需要 ATM 的“选择环境”模式时 |
| `config` | 需要更新默认配置模板时 |
| `check` | 每完成一个阶段就跑 gate |
| `package` | 准备正式交付时 |
| `release` | 准备把 ZIP 发布到 GitHub Release 时 |
| `host` | 在宿主里联调、安装或升级模块时 |

不要绕过这些命令手写第二套工程流程。

## 写 TaskScript：一个 task 只做一个原子动作

`TaskScript` 是模块里的最小业务单元。一个动作满足下面任意一点，就应该做成 task：

- 可以单独调试
- 会被多个 workflow 复用
- 本质上只做一个动作

典型例子：

- 登录
- 打开目标页
- 抓一页列表
- 提交一个表单

最小写法：

```python
from crawler4j_sdk import TaskContext, TaskResult, TaskScript


class FetchHotelsTask(TaskScript):
    name = "fetch_hotels"
    display_name = "抓取酒店列表"
    description = "抓取当前城市酒店列表"

    async def execute(self, ctx: TaskContext) -> TaskResult:
        if not ctx.page:
            return TaskResult.fail(
                message="当前环境没有可用页面",
                error="page_unavailable",
            )

        city = ctx.get_config("city", "shanghai")
        await ctx.page.goto(f"https://example.com/hotels?city={city}")
        rows = [{"id": "hotel-001", "name": "示例酒店", "city": city}]

        if ctx.tools and ctx.tools.has_tool("db.replace_records"):
            ctx.tools.call("db.replace_records", dataset="hotels", records=rows)

        return TaskResult.ok(message="抓取完成", data={"records": rows})
```

task 的边界很明确：

- 读取配置和运行态
- 做一个原子业务动作
- 返回清晰结果

一旦开始出现明显的第二阶段、循环、分支或状态机，就该上升为 workflow。

## 写 TaskFlow：workflow 只做编排

`TaskFlow` 负责的是“组织 task”，不是重写 task 的细节。

workflow 适合做：

- 顺序
- 分支
- 循环
- stop 判断
- 阶段切换

最小写法：

```python
from crawler4j_sdk import TaskContext, TaskFlow, TaskResult


class HotelSyncWorkflow(TaskFlow):
    name = "hotel_sync"
    display_name = "酒店同步"
    description = "抓取并刷新酒店列表"

    async def run(self, ctx: TaskContext):
        ctx.state["phase"] = "fetch_hotels"
        payload = await ctx.run_subtask("fetch_hotels")
        if payload is False:
            return TaskResult.fail(
                message="fetch_hotels 执行失败",
                error="fetch_hotels_failed",
            )

        return {"records": payload.get("records", []) if isinstance(payload, dict) else []}
```

workflow 的硬约束也很简单：

- 子任务失败时不要静默降级
- 页面操作和字段解析不要在 workflow 里越写越重
- 不要在 workflow 里再造调度框架

## `module_runtime.py` 只做宿主接缝

模块开发的第三个落点是 `module_runtime.py`。这里的职责固定为三类：

1. lifecycle hook
2. `@env_selector(...)`
3. Hosted UI V1 声明

如果你准备在这里手写 hook、页面 schema 或数据表 handler，先继续看：

- [UI 与数据表](ui-and-data-table.md)
- [SDK 与 CLI 参考](reference-sdk-and-cli.md)
- [Core 能力参考](reference-core-capabilities.md)

最小签名边界先记住：

| 名称 | 当前约束 |
|---|---|
| `declare_ui(context)` | 同步函数，必须可重放 |
| `load_*_page(context, page_id, params=None)` | 同步函数，返回结构化字典 |
| `create_handler(context, payload)` | 同步函数 |
| `update_handler(context, pk_value, payload)` | 同步函数 |
| `ctx.tools.call(...)` | 统一宿主能力边界 |

### 生命周期 hook

包括：

- `prepare_env`
- `init_env`
- `before_run`
- `on_success`
- `on_failure`
- `on_timeout`
- `on_cleanup`

这些 hook 解决的是“宿主和模块的接缝问题”，不是业务主流程本身。

### 环境选择器

如果你的作业走 ATM 的“选择环境”模式，就在这里声明：

```python
@env_selector(
    name="pick_ready",
    display_name="优先选择可用环境",
    description="从当前资源池里选择一个可用候选",
)
def pick_ready_selector(candidates, context):
    ...
```

注意：

- 真正要写的是 `@env_selector(...)` 函数
- 不是再发明一个名叫 `select_env` 的自定义 hook
- 固定环境池是否进入等待，还取决于运行模板是不是 `Service Job + select + resource_pool`

### Hosted UI V1

当前 UI 正式写法只有一种：在 `module_runtime.py` 里声明。

最小骨架：

```python
def declare_ui(context: TaskContext):
    _declare_dashboard_page(context)
    _declare_hotels_table(context)
    return None
```

#### 宿主页

适合：

- KPI
- 说明文案
- 只读表格
- 页面按钮

入口写法：

- `module.yaml.ui_extension.pages[].entry = core:page:<page_id>`
- `context.tools.call("ui.declare_page", ...)`

#### 托管数据表

适合：

- 当前账号列表
- 当前酒店列表
- 小型业务记录维护

入口写法：

- `module.yaml.ui_extension.pages[].entry = core:data_table:<view_id>`
- `context.tools.call("ui.declare_data_table", ...)`

它默认服务的是“当前快照”，不是历史事件流。

## 把配置、运行态、快照数据和历史事件分开

这一条是写模块时最容易出事故的边界。

| 类别 | 正式入口 | 用法 |
|---|---|---|
| 持久配置 | `ctx.get_config()` / `ctx.config` | 读模块级和 workflow 级配置 |
| 运行态元数据 | `ctx.runtime` | 读 `workflow`、`params`、`devel_mode`、`creation_params` |
| 单次执行状态 | `ctx.state` | 保存一次执行内的小体量临时状态 |
| 当前快照数据 | `db.list_records` / `db.replace_records` | 保存当前列表、当前结果集 |
| append-only 历史 | `db.append_event` / `db.query_events` | 保存状态迁移、操作痕迹、事件历史 |

不要混用：

- 不要把 `workflow`、`params` 写进配置
- 不要把长期数据塞进 `ctx.state`
- 不要把历史事件混进 `core:data_table`

## 当前明确推荐的抽象层次

一个合格模块，通常只需要这几层：

1. `workflow`
2. `task`
3. `utils/` 里的纯函数
4. `module_runtime.py` 里的薄 hook 和 Hosted UI V1 声明

下面这些结构，当前默认视为过度抽象：

- `services/`
- `repositories/`
- `managers/`
- `controllers/`
- `BaseTask`
- `BaseWorkflow`
- `ContextAdapter`
- `DbClient`

模块是交付业务，不是证明架构技巧。

## 每完成一个阶段就跑 gate

建议最少用这几档校验：

```bash
uv run crawler4j check structure
uv run crawler4j check release
uv run crawler4j check full
```

直接理解成：

- `structure`：骨架、清单和 UI 入口格式
- `release`：版本、升级源、默认配置等发布前提
- `full`：模块、task、workflow、Hosted UI V1 的完整导入和声明 gate

只要 `check full` 没过，就不要把问题推给宿主。

## 从联调切到正式交付

模块开发的最后两步，不是继续写代码，而是切换边界。

### 联调边界

用 DevLink：

```bash
uv run crawler4j host devlink add /abs/path/to/module
uv run crawler4j host debug config
```

这条链路解决的是：

- 本地源码能否被宿主加载
- ATM 能否执行和调试
- Hosted UI V1 入口是否出现

### 交付边界

用 ZIP 和 GitHub Release：

```bash
uv run crawler4j package build
uv run crawler4j package verify dist/<module>-<version>.zip
uv run crawler4j release publish
```

这条链路解决的是：

- 正式安装包是否合格
- 远端分发源是否存在
- 宿主后续是否能执行正式升级

DevLink 和正式交付是两条不同边界，不要混用。

## 升级一个模块时到底改什么

模块升级时，动作顺序应该非常清楚：

1. 改模块版本
2. 重建 ZIP
3. 发布到 GitHub Release
4. 让宿主检查并安装升级包

推荐命令：

```bash
uv run crawler4j module set version 0.1.1
uv run crawler4j package build
uv run crawler4j release publish --rebuild
uv run crawler4j host upgrade check hotel_demo
uv run crawler4j host upgrade apply hotel_demo
```

这条线里有三个不要混淆的点：

- 你改的是模块版本，不是 SDK 版本
- 你发的是模块 ZIP，不是宿主本体
- 宿主执行的是模块升级，不是 CLI 升级

## 一页记住构建主线

```text
CLI 生成骨架
-> task / workflow 写业务
-> module_runtime.py 接生命周期、环境选择器和 Hosted UI V1
-> check full
-> DevLink 联调
-> package build
-> release publish
-> host upgrade
```

这就是当前 `crawler4j` 模块开发的正式主线。
