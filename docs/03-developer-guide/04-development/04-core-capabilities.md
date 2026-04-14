# 4.4 Core 提供的能力清单

这一页回答一个最实际的问题：

> 模块开发者到底怎么知道 Core 会给我什么能力？

当前正式答案已经收敛成一句话：

> 模块不是“向 Core 要一堆私有对象”，而是“只能通过 `TaskContext.tools` 调用 Core 注册的正式工具”。

## 稳定事实源

1. 稳定能力清单以 `packages/crawler4j-contracts/src/context.py` 里的 `TaskContext`、`ToolsCapability` 和 `ToolSpec` 为准。
2. `crawler4j_sdk` 只负责把这些稳定契约重新导出，方便模块侧直接导入。
3. 除 SDK 顶层导出的稳定入口外，不要再假设宿主会注入其他私有对象或业务扩展。

## `TaskContext` 里哪些是稳定能力

### 基础字段

| 字段 | 类型 | 用途 |
|---|---|---|
| `ctx.env_id` | `int` | 当前运行环境 ID |
| `ctx.task_name` | `str` | 当前任务名 |
| `ctx.config` | `dict[str, Any]` | 运行配置原始字典 |
| `ctx.page` | `Page \| None` | 当前 Playwright Page |
| `ctx.context` | `BrowserContext \| None` | 当前 Playwright BrowserContext |
| `ctx.logger` | `logging.Logger` | 日志能力 |
| `ctx.http` | `HttpClient` | HTTP 请求能力 |
| `ctx.state` | `dict[str, Any]` | 任务 / 工作流共享状态 |
| `ctx.captured_data` | `list[Any]` | 运行过程收集的数据 |
| `ctx.tools` | `ToolsCapability \| None` | 宿主注入的统一工具入口 |

### 基础方法

| 方法 | 返回 | 用途 |
|---|---|---|
| `await ctx.wait(seconds)` | `None` | 异步等待 |
| `await ctx.screenshot(name)` | `str` | 截图并返回路径 |
| `ctx.get_config(key, default=None)` | `Any` | 读取配置项 |
| `ctx.should_stop()` | `bool` | 检查停止标志 |
| `ctx.request_stop()` | `None` | 请求停止工作流 |
| `await ctx.run_subtask(task_name, **kwargs)` | `Any` | 调用子任务 |

## `ctx.tools` 怎么用

`ctx.tools` 是当前唯一正式的宿主扩展入口。

你可以做三件事：

1. `ctx.tools.has_tool(name)`：判断工具是否存在
2. `ctx.tools.list_tools()`：枚举当前可用工具及其描述
3. `ctx.tools.call(name, **kwargs)`：调用工具

最稳妥的调用方式是先判断，再执行：

```python
if ctx.tools and ctx.tools.has_tool("db.list_records"):
    rows = ctx.tools.call("db.list_records", dataset="orders")

if ctx.tools and ctx.tools.has_tool("env.set_proxy"):
    await ctx.tools.call(
        "env.set_proxy",
        env_id=ctx.env_id,
        proxy_value="http://127.0.0.1:8888",
    )

if ctx.tools and ctx.tools.has_tool("captcha.match_slider"):
    slider = ctx.tools.call(
        "captcha.match_slider",
        background_image=bg_bytes,
        puzzle_piece_image=piece_bytes,
    )
```

不要写成“我觉得宿主应该有这个能力，所以直接调”。

## 当前内置工具清单

### `db.*`

用于模块数据、运行态状态和简单互斥锁。

| 工具名 | 用途 |
|---|---|
| `db.list_records` | 读取模块数据集 |
| `db.replace_records` | 全量覆盖模块数据集 |
| `db.acquire_lock` | 获取锁 |
| `db.release_lock` | 释放锁 |
| `db.is_locked` | 查询锁状态 |
| `db.get_state` | 读取运行态状态 |
| `db.set_state` | 写入运行态状态 |
| `db.exists_state` | 判断状态键是否存在 |

这里有一个非常重要的边界：

> 对模块开发者来说，`db.*` 是当前正式的数据接口。不要绕过它直接连接宿主数据库。

### `ip_pool.*`

用于按条件挑选代理。

| 工具名 | 用途 |
|---|---|
| `ip_pool.pick_proxy` | 按条件挑选可用 IP / 代理 |

### `env.*`

用于操作当前运行环境。

| 工具名 | 用途 |
|---|---|
| `env.set_proxy` | 为当前环境设置代理 |

注意：这是异步工具，应使用 `await ctx.tools.call(...)`。

### `ui.*`

用于声明和读取模块 UI 数据表元数据。

| 工具名 | 用途 |
|---|---|
| `ui.declare_data_table` | 声明数据表视图 |
| `ui.get_data_table` | 读取数据表视图元数据 |

### `captcha.*`

用于调用宿主封装的验证码模型能力。当前 `crawler4j` 内部接入的是：

- `captcha.match_slider` -> `sinanz.sn_match_slider(...)`
- `captcha.match_click_targets` -> 宿主侧封装的 `sinanz_group1_service.solve_click_targets(...)`

模块侧不要直接依赖这些私有模块路径，正式入口是 `ctx.tools.call(...)`。

| 工具名 | 用途 |
|---|---|
| `captcha.match_slider` | 识别滑块缺口位置 |
| `captcha.match_click_targets` | 识别点选验证码目标顺序与坐标 |

## `db.*` 最推荐的使用方式

如果你准备在模块里用数据能力，建议默认遵守下面 3 条：

1. 数据集名保持稳定，例如 `accounts`、`orders`、`tasks`
2. 状态键自己带模块前缀，例如 `hotel_demo:orders:cursor`
3. 写操作尽量幂等，先拿锁再写

一个更接近真实开发的写法如下：

```python
if ctx.tools and ctx.tools.has_tool("db.get_state"):
    state_key = "hotel_demo:orders:cursor"
    cursor = ctx.tools.call("db.get_state", key=state_key) or {"page": 1}

    locked = ctx.tools.call(
        "db.acquire_lock",
        scope="orders",
        key="sync",
        ttl=60,
        owner={"task": ctx.task_name},
    )
    if locked:
        try:
            records = ctx.tools.call("db.list_records", dataset="orders")
            records.append({"id": "o-1", "status": "pending"})
            ctx.tools.call("db.replace_records", dataset="orders", records=records)
            ctx.tools.call("db.set_state", key=state_key, value={"page": cursor["page"] + 1}, ttl=3600)
        finally:
            ctx.tools.call("db.release_lock", scope="orders", key="sync")
```

## 当前不建议怎么做

不要把下面这些做法当成正式开发方式：

- 在模块里直接 `import sqlite3` 去连宿主数据库
- 从宿主代码里偷拿内部存储对象
- 继续假设存在 `ctx.db`、`ctx.captcha` 这类专用能力字段
- 沿用历史资料里 `ctx.db.storage.state` 这类旧聚合写法

这些写法要么不是当前稳定契约，要么会让模块和宿主内部实现强耦合。

## `run_subtask()` 的真实语义

这是模块作者最容易误解的一个点。

`await ctx.run_subtask("task_name", **kwargs)` 当前行为是：

1. 如果你传了 `kwargs`，这些值会先合并进 `ctx.state`
2. 宿主执行子任务
3. 如果返回对象有 `data` 且不为空，直接返回 `data`
4. 否则如果返回对象有 `success` 字段，返回布尔值
5. 否则返回原始结果对象

所以它不是“永远返回 `TaskResult` 对象”。

## 当前开发者应该看哪里

如果你想确认 Core 到底提供了哪些能力，建议按下面顺序看：

1. 本页
2. `packages/crawler4j-contracts/src/context.py`
3. `packages/crawler4j-sdk/README.md`

如果文档和代码不一致，以代码为准；其中能力契约的源码事实源就是 `packages/crawler4j-contracts/src/context.py`。
