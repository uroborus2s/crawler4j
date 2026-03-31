# 4.4 Core 提供的能力清单

这一页回答一个最实际的问题：

> 模块开发者到底怎么知道 Core 会给我什么能力？

当前正式答案是：

1. 稳定能力清单以 `crawler4j_contracts/context.py` 里的 `TaskContext` 和各个 `Protocol` 为准。
2. `crawler4j_sdk` 只是把这些稳定契约重新导出，方便你在模块里直接导入。
3. 非稳定扩展看 `crawler4j_sdk/extensions.py`，但这部分不能当成长期稳定依赖。

如果你只想记住一句话，请记住：

> 模块不是“随便向 Core 要对象”，而是“只能使用 `TaskContext` 明确暴露出来的能力”。

## 哪些是稳定能力

下面这些字段和方法，当前都属于模块开发者可以依赖的正式接口。

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

### 基础方法

| 方法 | 返回 | 用途 |
|---|---|---|
| `await ctx.wait(seconds)` | `None` | 异步等待 |
| `await ctx.screenshot(name)` | `str` | 截图并返回路径 |
| `ctx.get_config(key, default=None)` | `Any` | 读取配置项 |
| `ctx.should_stop()` | `bool` | 检查停止标志 |
| `ctx.request_stop()` | `None` | 请求停止工作流 |
| `await ctx.run_subtask(task_name, **kwargs)` | `Any` | 调用子任务 |

## 哪些是宿主按需注入的能力接口

这些接口不是每次都一定有，但它们属于正式能力面。  
模块在使用前应该先判断是否存在。

### `ctx.db`

用于模块数据、运行态状态和简单互斥锁。

这里有一个非常重要的边界：

> 对模块开发者来说，`ctx.db` 就是当前正式的数据接口。不要绕过它直接连接宿主数据库。

换句话说，当前模块开发能依赖的数据能力只有这一个最小面，不要继续假设：

- ORM Session
- 原生 SQLite 连接
- 私有 Repository / DAO
- 已删除的历史 `ctx.db.storage` / `ctx.db.accounts` / `ctx.db.tasks` 聚合对象

| 方法 | 用途 |
|---|---|
| `list_records(dataset)` | 读取模块数据集 |
| `replace_records(dataset, records)` | 全量覆盖模块数据集 |
| `acquire_lock(scope, key, ttl, owner=None)` | 获取锁 |
| `release_lock(scope, key)` | 释放锁 |
| `is_locked(scope, key)` | 查询锁状态 |
| `get_state(key)` | 读取运行态状态 |
| `set_state(key, value, ttl=None)` | 写入运行态状态 |
| `exists_state(key)` | 判断状态键是否存在 |

### 从旧模块升级到当前口径时要直接替换什么

当前没有兼容过渡层。升级旧模块时，直接按下面方式改：

1. 删除 `DataService` 导入，类型标注改成 `DatabaseCapability` 或直接依赖 `ctx.db`
2. 把 `ctx.db.storage.state` 改成 `get_state()` / `set_state()`
3. 把历史账号、任务等聚合对象改成 `list_records()` / `replace_records()`
4. 停止直接连接宿主数据库

### `ctx.ip_pool`

用于按条件挑选代理。

| 方法 | 用途 |
|---|---|
| `pick_proxy(criteria=None)` | 挑选可用 IP / 代理 |

### `ctx.env_ops`

用于操作当前运行环境。

| 方法 | 用途 |
|---|---|
| `await set_proxy(env_id, proxy_value=None, proxy_pool_id=None)` | 为当前环境设置代理 |

### `ctx.ui`

用于声明和读取模块 UI 数据表元数据。

| 方法 | 用途 |
|---|---|
| `declare_data_table(view_id, schema)` | 声明数据表视图 |
| `get_data_table(view_id)` | 读取数据表视图元数据 |

## `ctx.http` 具体能做什么

`ctx.http` 当前暴露的是一个简单 HTTP 客户端协议：

| 方法 | 用途 |
|---|---|
| `await ctx.http.get(url, **kwargs)` | 发 GET 请求并返回 JSON |
| `await ctx.http.post(url, data=None, **kwargs)` | 发 POST 请求并返回 JSON |

如果你的模块需要更复杂的 HTTP 行为，优先确认当前协议是否足够，不要直接假设宿主会额外注入私有客户端。

## 开发时怎么判断某个能力能不能用

最稳妥的写法是先判断，再调用。

```python
if ctx.db is not None:
    rows = ctx.db.list_records("orders")

if ctx.env_ops is not None:
    await ctx.env_ops.set_proxy(ctx.env_id, proxy_value="http://127.0.0.1:8888")

if ctx.ui is not None:
    ctx.ui.declare_data_table("orders", {"columns": ["id", "status"]})
```

不要写成“我觉得宿主应该有这个能力，所以直接调”。

### `ctx.db` 最推荐的使用方式

如果你准备在模块里用数据能力，建议默认遵守下面 3 条：

1. 数据集名保持稳定，例如 `accounts`、`orders`、`tasks`
2. 状态键自己带模块前缀，例如 `hotel_demo:orders:cursor`
3. 写操作尽量幂等，先拿锁再写

一个更接近真实开发的写法如下：

```python
if ctx.db is not None:
    state_key = "hotel_demo:orders:cursor"
    cursor = ctx.db.get_state(state_key) or {"page": 1}

    if ctx.db.acquire_lock("orders", "sync", ttl=60, owner={"task": ctx.task_name}):
        try:
            records = ctx.db.list_records("orders")
            records.append({"id": "o-1", "status": "pending"})
            ctx.db.replace_records("orders", records)
            ctx.db.set_state(state_key, {"page": cursor["page"] + 1}, ttl=3600)
        finally:
            ctx.db.release_lock("orders", "sync")
```

### 当前不建议怎么做

不要把下面这些做法当成正式开发方式：

- 在模块里直接 `import sqlite3` 去连宿主数据库
- 从宿主代码里偷拿内部存储对象
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

## 非稳定扩展怎么看

`crawler4j_sdk/extensions.py` 里当前有一组非稳定扩展辅助：

| 项目 | 说明 |
|---|---|
| `ExtendedContextFields` | 放在 `ctx.state["_ext"]` 的扩展字段 |
| `get_ctrip_account(ctx)` | 读取携程账号扩展 |
| `get_labor_account(ctx)` | 读取劳保账号扩展 |
| `get_input_callback(ctx)` | 读取手动输入回调 |

这一层的规则很简单：

- 可以用，但只能在明确知道宿主会注入时使用
- 不能把它当成稳定契约去写通用模块
- 版本升级时要优先复验这部分

## 当前开发者应该看哪里

如果你想确认 Core 到底提供了哪些能力，建议按下面顺序看：

1. 本页
2. `crawler4j_contracts/context.py`
3. `crawler4j_sdk/README.md`
4. `crawler4j_sdk/extensions.py`（仅当你确实需要非稳定扩展）

如果文档和代码不一致，以代码为准；其中能力契约的源码事实源就是 `crawler4j_contracts/context.py`。
