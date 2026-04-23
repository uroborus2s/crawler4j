# Core 能力参考

模块运行时只有两个正式边界：

1. 从 `crawler4j-contracts` 导入共享契约
2. 通过 `ctx.tools` 调用宿主能力

模块不应该直接 import Core 内部实现，也不应该依赖 `crawler4j-sdk` 参与运行时装配。

## 宿主扫描协议

Core 会扫描固定目录并读取固定导出：

| 目录 | 必需导出 | 作用 |
|---|---|---|
| `tasks/*.py` | `TASK`、`execute` | 原子任务 |
| `workflows/*.py` | `WORKFLOW`、`run` | 工作流 |
| `hooks/*.py` | `handle` | 生命周期 Hook |
| `env_selectors/*.py` | `SELECTOR`、`select` | 环境选择器 |
| `pages/*.py` / `pages/<group>/*.py` | `PAGE`、页面 handler | Hosted UI 页面 |

Core 不会调用模块根 `run()`，也不会让模块自己做运行时装配。

## 共享契约

运行时模块通常只需要这些类型：

- `TaskContext`
- `TaskResult`
- `TaskSignal`
- `EnvAction`
- `EnvCandidate`
- `TaskSpec`
- `WorkflowSpec`
- `EnvSelectorSpec`
- `PageSpec`

## `TaskContext.tools`

宿主能力统一经 `ctx.tools` 暴露：

- `ctx.tools.has_tool(name)`
- `ctx.tools.list_tools()`
- `ctx.tools.call(name, **kwargs)`

常见能力面如下：

| 类别 | 工具名 | 主要用途 |
|---|---|---|
| Hosted UI | `ui.get_page` | 调试页面声明结果 |
| 数据记录 | `db.get_record` `db.list_records` `db.replace_records` | 读取/覆盖已在 `module.yaml.data.resources[]` 注册的资源记录 |
| 数据查询 | `db.run_query` `db.query_view` | 执行已注册命名查询或视图 |
| 审计事件 | `db.append_event` `db.query_events` | append-only 历史 |
| 轻状态 | `db.get_state` `db.set_state` `db.exists_state` | 轻量状态与游标 |
| 锁 | `db.acquire_lock` `db.release_lock` `db.is_locked` | 幂等与互斥 |
| 环境与资源池 | `env.*` `ip_pool.pick_proxy` | 环境选择、代理、固定池维护 |
| 验证码 | `captcha.match_slider` `captcha.match_click_targets` | 图像辅助 |

## 任务与工作流

最小任务签名：

```python
async def execute(ctx: TaskContext) -> TaskResult:
    ...
```

最小工作流签名：

```python
async def run(ctx: TaskContext):
    return await ctx.run_subtask("task_name")
```

如果 `run()` 返回：

- `TaskResult`：宿主直接使用
- `dict`：宿主归一化为成功结果
- `None`：宿主会把当前 `ctx.state` 归一化为成功结果

## 生命周期 Hook

当前宿主识别的 Hook 文件名固定为：

- `prepare_env`
- `init_env`
- `before_run`
- `on_success`
- `on_failure`
- `on_timeout`
- `on_cleanup`

每个文件都导出：

```python
async def handle(context: TaskContext):
    ...
```

文件名就是 Hook 名。宿主负责调度，不需要模块再注册。

## 环境选择器

环境选择器文件导出：

```python
from crawler4j_contracts import EnvCandidate, EnvSelectorSpec, TaskContext

SELECTOR = EnvSelectorSpec(name="pick_ready")

def select(context: TaskContext, candidates: list[EnvCandidate]):
    ...
```

返回值约定：

- 返回 `env_id`：宿主绑定该环境
- 返回 `None`：当前轮未选中

当作业配置了 `resource_pool` 时，`None` 会进入宿主管理的等待语义；没有 `resource_pool` 时会按失败处理。

## 页面与处理函数

页面文件导出：

```python
from crawler4j_contracts import PageSpec

PAGE = PageSpec(
    id="dashboard",
    label="Dashboard",
    icon="📄",
    schema={...},
)
```

常见 handler 签名：

```python
def load_dashboard_page(context: TaskContext, page_id: str, params: dict | None = None) -> dict:
    ...

def query_orders_table(
    context: TaskContext,
    table_id: str,
    query: dict,
    params: dict | None = None,
) -> dict:
    ...
```

正式约束：

- `PAGE.id` 必须与 `module.yaml.ui_extension.pages[]` 对齐
- `PAGE.schema` 顶层必须是 `Page`
- `load_handler` 必须指向页面文件中真实存在的函数
- `DataTable(query_handler)` 必须指向页面文件中真实存在的函数

## 数据表

`DataTable` 是页面内组件，不是独立运行时入口。当前正式数据源只有三种：

- `binding`
- `rows`
- `query_handler`

推荐用法：

- 单条详情：`db.get_record`
- 快照列表：`db.list_records` + `binding`
- 统计查询：内联 `DataTable(query_handler)` + `db.query_view`
- 命名 SQL：`db.run_query(query_id=..., params=...)`
- 审计时间线：`db.query_events` 后由页面自己组装

文档示例统一只写 `resource=...` 来对应 `module.yaml.data.resources[]`；运行时不再接受历史别名 `dataset=...`。

## 数据能力约束

`db.replace_records` 的语义只有一个：全量覆盖，不是 patch 或 upsert。

模块不能在运行时代码里声明表或视图。表、视图、命名查询统一来自：

- `module.yaml.data`
- `data/sql/views/*.sql`
- `data/sql/queries/*.sql`
- `data/seeds/*.json`

未在 `module.yaml.data.resources[]` 注册的 `resource_id` 会直接报错；`managed_dataset` 也不再按 `dataset` 名自动创建托管表资源。

`db.run_query` / `db.query_view` 当前只支持：

- 宿主已注册的 `query_id` / `view_id`
- 受控 `SELECT` / `WITH ... SELECT`
- 通过 `{{resource:<resource_id>}}` 引用已在 `module.yaml.data.resources[]` 注册的资源
- 不允许执行未注册 SQL

## 调试建议

能力边界问题优先这样查：

1. `uv run crawler4j check full`
2. 确认导出对象和 handler 是否存在
3. 用 `ctx.tools.list_tools()` 看宿主是否真的暴露了目标能力
4. 再去查业务逻辑
