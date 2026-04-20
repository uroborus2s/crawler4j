# Core 能力参考

模块运行时不应该直连宿主内部对象。统一边界只有一个:

```python
ctx.tools.call(...)
```

配套接口只有:

- `ctx.tools.has_tool(name)`
- `ctx.tools.list_tools()`
- `ctx.tools.call(name, **kwargs)`

如果你绕过这层边界，模块就不再是受控轻量应用，而是在偷偷绑定宿主内部实现。

数据相关工具最好先按三类心智来理解:

- 快照数据集: `db.list_records` / `db.replace_records`
- append-only 审计事件: `db.append_event` / `db.query_events`
- 轻状态与锁: `db.get_state` / `db.set_state` / `db.acquire_lock`

## 工具总表

当前工作区可直接确认的宿主工具如下:

| 工具名                                  | 是否异步 | 主要用途                                   | 典型返回值                      |       |
| ------------------------------------ | ---- | -------------------------------------- | -------------------------- | ----- |
| `db.list_records`                    | 否    | 读取业务数据集                                | `list[dict]`               |       |
| `db.replace_records`                 | 否    | 全量覆盖业务数据集                              | `bool`                     |       |
| `db.append_event`                    | 否    | 追加模块审计事件                               | `bool`                     |       |
| `db.query_events`                    | 否    | 查询模块审计事件                               | `list[dict]`               |       |
| `db.acquire_lock`                    | 否    | 获取互斥锁                                  | `bool`                     |       |
| `db.release_lock`                    | 否    | 释放互斥锁                                  | `bool`                     |       |
| `db.is_locked`                       | 否    | 查询锁状态                                  | `bool`                     |       |
| `db.get_state`                       | 否    | 读取轻量状态                                 | `Any`                      |       |
| `db.set_state`                       | 否    | 写入轻量状态                                 | `bool`                     |       |
| `db.exists_state`                    | 否    | 判断状态键是否存在                              | `bool`                     |       |
| `ip_pool.pick_proxy`                 | 否    | 选择代理                                   | `dict                      | None` |
| `env.set_proxy`                      | 是    | 给环境设置代理                                | `bool`                     |       |
| `env.bind_resource_pool`             | 是    | 登记环境到模块资源池并写入资格卡片                      | `bool`                     |       |
| `env.mark_resource_pool_eligible`    | 是    | 标记环境当前可接单                              | `bool`                     |       |
| `env.mark_resource_pool_ineligible`  | 是    | 标记环境当前不可接单                             | `bool`                     |       |
| `env.remove_resource_pool`           | 是    | 移除环境的资源池资格卡片                           | `bool`                     |       |
| `env.replace_resource_pool_snapshot` | 是    | 全量重建某个资源池的资格快照，未出现在 `entries` 里的卡片会被删除 | `bool`                     |       |
| `ui.declare_data_table`              | 否    | 声明托管数据表 schema                         | `bool`                     |       |
| `ui.get_data_table`                  | 否    | 读取托管数据表 schema                         | `dict`                     |       |
| `captcha.match_slider`               | 否    | 识别滑块验证码                                | `SliderCaptchaMatchResult` |       |
| `captcha.match_click_targets`        | 否    | 识别点选验证码                                | `ClickCaptchaMatchResult`  |       |

## 数据工具

先记住一个大原则：

- `db.list_records` / `db.replace_records` = 快照型当前状态
- `db.append_event` / `db.query_events` = append-only 审计历史

### `db.list_records`

```python
rows = ctx.tools.call("db.list_records", dataset="hotels")
```

适用场景:

- 读取结构化业务记录
- 给 task、workflow、代码型 UI 提供列表数据

不适合:

- 读取配置
- 读取一次性运行参数

### `db.replace_records`

```python
ok = ctx.tools.call("db.replace_records", dataset="hotels", records=rows)
```

这是当前最容易被误用的工具。

真实语义:

- 它是全量覆盖
- 不是增量更新
- 不是 patch
- 不是 upsert API

这意味着如果你这么写:

```python
ctx.tools.call("db.replace_records", dataset="hotels", records=[new_row])
```

你不是“插入一条”，你是在把整个 `hotels` 数据集重写成只剩一条。

安全写法通常是:

```python
rows = ctx.tools.call("db.list_records", dataset="hotels") or []
rows.append(new_row)
ctx.tools.call("db.replace_records", dataset="hotels", records=rows)
```

并发风险也必须知道:

- 两个 task 同时读旧列表再各自 `replace_records`，后写入的一方会覆盖前一方结果
- 如果存在并发写，优先先加锁
- 如果写逻辑越来越复杂，说明这个数据集设计该重做，而不是继续叠补丁
- 如果同一条业务既要保留“当前状态”又要保留“发生过什么”，当前状态继续放 dataset，历史另走 `db.append_event`

### `db.append_event`

```python
ok = ctx.tools.call(
    "db.append_event",
    dataset="account_events",
    event_type="status_changed",
    entity_key="13800000001",
    previous_status="active",
    next_status="blocked",
    reason="risk_control",
    payload={"operator": "system"},
)
```

适用场景:

- 记录账号状态流转
- 写入运行留痕
- 保存 append-only 审计事件

不适合:

- 回写当前快照列表
- 覆盖历史事件
- 充当通用 CRUD 表

当前签名固定为：

- `dataset`
- `event_type`
- `entity_key`
- `run_id`
- `previous_status`
- `next_status`
- `result`
- `reason`
- `payload`
- `created_at`

写法约束：

- `previous_status` / `next_status` / `result` / `reason` 已有一等字段时，直接写顶层
- `payload` 只保留模块私有扩展字段，不要再重复包一层同名结构化字段

### `db.query_events`

```python
events = ctx.tools.call(
    "db.query_events",
    dataset="account_events",
    entity_key="13800000001",
    event_type="status_changed",
    limit=20,
)
```

适用场景:

- 查询某个账号的历史轨迹
- 按事件类型筛选历史记录
- 按时间范围拉取运行留痕

返回结果按时间排序，支持：

- `entity_key`
- `event_type`
- `run_id`
- `start_at`
- `end_at`
- `limit`
- `offset`
- `order`

返回的每条事件当前会包含这些顶层键：

- `id`
- `module_name`
- `dataset_name`
- `entity_key`
- `event_type`
- `run_id`
- `previous_status`
- `next_status`
- `result`
- `reason`
- `payload`
- `created_at`

### `db.get_state` / `db.set_state` / `db.exists_state`

这些是轻量状态，不是正式业务表。

适合放:

- 分页游标
- 最近一次成功时间
- 短 TTL 会话标记
- 小体量中间状态

不适合放:

- 大批量 records
- 正式配置
- 长期结构化业务数据

推荐 key 命名:

```python
key = "hotel_demo:sync:cursor"
ctx.tools.call("db.set_state", key=key, value={"page": 2}, ttl=300)
cursor = ctx.tools.call("db.get_state", key=key)
```

## 固定环境池工具

固定环境池场景不要再让模块自己 `sleep` 轮询。模块只负责同步资格快照，排队和补位由宿主处理。

先记住一个前提:

- 只调用资源池 helper，不会自动让作业进入等待队列
- 固定环境池等待语义只在 `Service Job + acquisition.mode=select + resource_pool 非空` 时成立

### 运行模板语义矩阵

| 运行模板配置 | 宿主是否进入固定池等待语义 | `select_env` 是否会被调用 | 当前轮没命中时的结果 |
|---|---|---|---|
| `mode=create` | 否 | 否 | 不适用 |
| `mode=select` + 只有 `selector_name` | 否 | 会 | 直接失败，错误为 `环境选择回调函数返回了 none: <selector>` |
| `Service Job + mode=select` + 只有 `resource_pool` | 是 | 不会；宿主直接取当前池内第一个可分配候选 | 进入等待席位，底层状态仍是 `PENDING`；若候选在发号后被别人先抢走，也会回到等待，不直接失败 |
| `Service Job + mode=select` + `resource_pool` + `selector_name` | 是 | 会；只在当前资源池候选内挑选 | `selector` 返回 `None` 时回到等待，而不是直接失败；若选中的候选在租约阶段被别人先抢走，也会回到等待 |

如果你要的是“固定环境池 Service Job 排队补位”，至少要满足三件事：

1. 作业类型是 `Service Job`
2. 运行模板里选 `选择环境`
3. `resource_pool` 填上稳定池名，例如 `bound_account_ready`

如果是批次任务，即使你填了 `resource_pool` 并调用了 helper，当前实现也不会为它开启等待席位。

如果你定义了 `selector_name`，再补一条术语：

- 你真正实现的是 `module_runtime.py` 里通过 `@env_selector(...)` 声明的 selector 函数
- 运行时看到的 `select_env(...)` 是 SDK / 宿主包装壳，不是让你手写一个名叫 `select_env` 的业务 hook
- `selector_name` 要填的是被装饰 selector 的名字，不是随便起一个回调标签

如果你是在迁移一个已经依赖 `selector_name` 的旧模块，还要多记一条：

- 把 `selector_name` 留空，不是“沿用原行为”
- 这会把模块自定义选环境逻辑切成“宿主直接取当前池内第一个可分配候选”
- 当前实现没有给这个“第一个候选”额外定义业务优先级或稳定排序承诺
- 只有确认业务不再需要自定义挑选顺序时，才把 `selector_name` 清空

当前宿主提供的资源池工具是：

- `env.bind_resource_pool`
- `env.mark_resource_pool_eligible`
- `env.mark_resource_pool_ineligible`
- `env.remove_resource_pool`
- `env.replace_resource_pool_snapshot`

更推荐直接使用 SDK helper，而不是手写工具名：

```python
from crawler4j_sdk import (
    bind_resource_pool,
    mark_resource_pool_ineligible,
    replace_resource_pool_snapshot,
)

if ctx.tools and ctx.tools.has_tool("env.bind_resource_pool"):
    await bind_resource_pool(ctx, pool_name="bound_account_ready")

if ctx.tools and ctx.tools.has_tool("env.mark_resource_pool_ineligible"):
    await mark_resource_pool_ineligible(
        ctx,
        pool_name="bound_account_ready",
        reason="blacklisted",
    )

if ctx.tools and ctx.tools.has_tool("env.replace_resource_pool_snapshot"):
    await replace_resource_pool_snapshot(
        ctx,
        pool_name="bound_account_ready",
        entries=[
            {"env_id": 101, "eligible": True},
            {"env_id": 102, "eligible": False, "reason": "manual_disabled"},
        ],
    )
```

命名口径：

- `pool_name` 只写资源池名，例如 `bound_account_ready`
- 宿主会按当前模块的根模块名归一化后生成 metadata key `<root_module>:<pool_name>`；例如模块运行名是 `demo.foo` 时，卡片 key 前缀仍然是 `demo`
- 模块不要自己拼这个 key，也不要把点号后的子模块名当成独立池前缀
- SDK helper 依赖宿主提供对应 `env.*resource_pool*` capability；如果 capability 缺失，helper 会抛明确异常，推荐在兼容旧宿主时先用 `ctx.tools.has_tool(...)` 判断

### helper 该在什么时候用

先把 `env_id` 的真实含义记住：

- 这里的 `env_id` 是宿主 `environments.id` 主键，不是外部浏览器 `browser_id`、`external_id`，也不是账号 ID
- `prepare_env` 阶段的 `TaskContext.env_id` 当前固定是 `0`
- 所以不要在 `prepare_env` 里写资源池卡片；等真正拿到宿主环境 ID 后再写，或者在离线对账里显式传 `env_id`

| helper | 适合的时机 | 关键约束 |
|---|---|---|
| `bind_resource_pool` | 某个环境第一次正式属于这个资源池 | 默认使用 `ctx.env_id`；当前上下文没有绑定环境时必须显式传 `env_id` |
| `mark_resource_pool_eligible` | 临时不可接单的环境恢复可用 | 只改资格，不会把环境重新“绑定”到别的池 |
| `mark_resource_pool_ineligible` | 黑号、人工停用、风控失效、暂停接单 | `reason` 必填，后续排障靠它解释为什么不能接单 |
| `remove_resource_pool` | 环境不再属于这个资源池 | 这是彻底移卡，不是“临时停发号” |
| `replace_resource_pool_snapshot` | 宿主重启、批量对账、全量重建事实 | `entries` 必须是这个池的完整权威列表；未出现的环境卡片会被删除，不是 patch API |

`replace_resource_pool_snapshot` 最容易被误用。正确心智和 `db.replace_records` 一样：

- 它是全量重建
- 不是增量补丁
- 不是“只传本次变更的几条 env”

这意味着如果一个池当前应该有 10 张卡片，你只传 2 条 `entries`，剩下 8 张会被宿主删除。

`exclusive` 也要单独记住：

- 当前 V1 只会把它写进资格卡片
- 当前分配器不会依据 `exclusive` 改变调度路径
- 除非你在模块自己的对账逻辑里另有约束，否则保持默认 `True`，不要把它当成切换路由的开关

### 最小接入闭环

```python
from crawler4j_sdk import (
    bind_resource_pool,
    mark_resource_pool_eligible,
    mark_resource_pool_ineligible,
    remove_resource_pool,
    replace_resource_pool_snapshot,
)


async def on_bound_ready(ctx):
    await bind_resource_pool(ctx, pool_name="bound_account_ready")


async def on_manual_resume(ctx):
    await mark_resource_pool_eligible(
        ctx,
        pool_name="bound_account_ready",
        reason="manual_resume",
    )


async def on_blacklisted(ctx):
    await mark_resource_pool_ineligible(
        ctx,
        pool_name="bound_account_ready",
        reason="blacklisted",
    )


async def on_unbound(ctx):
    await remove_resource_pool(ctx, pool_name="bound_account_ready")


async def reconcile_pool(ctx, bindings: list[dict]):
    await replace_resource_pool_snapshot(
        ctx,
        pool_name="bound_account_ready",
        entries=[
            {
                "env_id": item["env_id"],
                "eligible": item.get("eligible", True),
                "reason": item.get("reason", ""),
            }
            for item in bindings
        ],
    )
```

上面最后一个 `reconcile_pool(...)` 示例代表的是“把当前整池事实重写一遍”。如果你只想把某个环境暂时停发号，用 `mark_resource_pool_ineligible(...)`，不要拿全量快照 helper 当补丁。

业务语义固定为：

- 资源池归属和运行中占用分离，占用时不需要移出资源池
- 黑号先停发号，再按策略销毁环境
- Service Job 在资源不足时会保持 `PENDING` 等待，而不是因为“当前轮没命中”直接失败

### 状态与文案对照

| 名称 | 真实语义 | 什么时候看它 |
|---|---|---|
| `TaskStatus.PENDING` | 底层任务状态；固定池等待席位会复用它 | 看运行时状态机，不要直接拿 UI 文案当枚举 |
| `等待环境` | UI / 运营展示文案 | 在 ATM 列表和详情页看是否处于等待口径 |
| `等待环境池工位: <pool>` | 固定池等待中的 `task.message` | 判断这个 `PENDING` 是否真的是固定池等待 |
| `等待环境池工位超时: <pool> (<seconds>s)` | 固定池等待超时后的失败错误 | 排障时看是超时失败，不是“仍在等待” |

`wait_timeout` 也不要和 `execution.timeout` 混用：

- `wait_timeout` 当前同时传给环境租约获取和固定环境池等待席位收口
- 当前实现不会单独用 `wait_timeout` 中断 `select_env(...)` 本身；selector 里不要做长轮询、慢外部查询或睡眠等待
- 固定池等待的计时起点是任务第一次进入等待席位并写下 `waiting_since`
- `wait_timeout = 0` 时，固定池等待席位不会自动超时收口
- `execution.timeout` 是模块真正开始执行后的超时，不负责等待队列阶段
- 固定池当前只把 `eligible=true`、`READY`、且 `lease_id` 为空的环境视为可发号工位；`KEEP_ALIVE` 留下的 `RUNNING` 环境不会自动回池复用
- 如果候选环境在发号快照之后被标成 `eligible=false` 或移出资源池，宿主会在真正执行前再次确认资格；失效候选会回到等待席位，不会硬跑在错误工位上

### 锁工具

```python
ok = ctx.tools.call(
    "db.acquire_lock",
    scope="hotels",
    key="hotel-001",
    ttl=60,
    owner={"task_id": "t-1"},
)
```

适合:

- 防重跑
- 并发互斥
- 避免同一账号或记录被重复处理

## 代理和环境工具

### `ip_pool.pick_proxy`

```python
proxy = ctx.tools.call(
    "ip_pool.pick_proxy",
    criteria={
        "pool_id": "hotel_pool",
        "protocol": "http",
        "min_safety_score": 90,
        "max_bound_count": 2,
    },
)
```

返回值可能是 `None`，所以必须判空。

### 异步环境工具

当前这些环境工具都必须 `await`:

- `env.set_proxy`
- `env.bind_resource_pool`
- `env.mark_resource_pool_eligible`
- `env.mark_resource_pool_ineligible`
- `env.remove_resource_pool`
- `env.replace_resource_pool_snapshot`

例如：

```python
if ctx.tools and ctx.tools.has_tool("env.set_proxy"):
    await ctx.tools.call(
        "env.set_proxy",
        env_id=ctx.env_id,
        proxy_value="http://1.1.1.1:8001",
    )
```

或者直接用 SDK 的异步 helper：

```python
from crawler4j_sdk import bind_resource_pool

if ctx.tools and ctx.tools.has_tool("env.bind_resource_pool"):
    await bind_resource_pool(ctx, pool_name="bound_account_ready")
```

## UI 工具

### `ui.declare_data_table`

```python
ctx.tools.call(
    "ui.declare_data_table",
    view_id="hotels",
    schema={...},
)
```

当前真实约束:

- `view_id` 必须是 `snake_case`
- `dataset` 必须和 `view_id` 完全一致
- schema 只允许受控字段
- handler 名也必须是 `snake_case`

schema 顶层只允许这些字段:

- `title`
- `dataset`
- `primary_key`
- `lock_scope`
- `lock_key`
- `display_fields`
- `create_fields`
- `update_fields`
- `create_handler`
- `update_handler`
- `columns`

列定义只允许:

- `key`
- `label`
- `visible`
- `required`
- `type`
- `options`
- `default`

列类型只允许:

- `text`
- `number`
- `int`
- `bool`
- `select`

额外约束:

- 只有 `select` 列允许配置 `options`
- `select` 列必须提供非空 `options`
- `lock_key` 只用于 Core 临时锁，不用于表达业务占用态
- 已声明 `lock_key` 时，不要再声明 `occupied` / `occupied_label` 等业务占用列；Core 会直接拒绝这类 schema
- `core:data_table` 只服务快照 dataset，不直接承载 append-only 审计历史

### `ui.get_data_table`

```python
schema = ctx.tools.call("ui.get_data_table", view_id="hotels")
```

它适合:

- 调试 schema 是否真的声明成功
- 页面初始化时查看当前持久化 schema

## 验证码工具

### `captcha.match_slider`

```python
result = ctx.tools.call(
    "captcha.match_slider",
    background_image=bg_bytes,
    puzzle_piece_image=piece_bytes,
    puzzle_piece_start_bbox=(0, 0, 40, 40),
    device="cpu",
    return_debug=True,
)
```

### `captcha.match_click_targets`

```python
result = ctx.tools.call(
    "captcha.match_click_targets",
    query_icons_image=query_bytes,
    background_image=bg_bytes,
    device="cuda",
    return_debug=False,
)
```

## 防御式写法

```python
if ctx.tools and ctx.tools.has_tool("db.list_records"):
    rows = ctx.tools.call("db.list_records", dataset="hotels")
else:
    rows = []
```

## 明确禁止的“再包一层”

只要你开始写这些东西，就已经偏离“轻量业务模块”了:

- `DbClient(ctx.tools)` 再封一遍所有 `db.*`
- `CoreApi` 再包装 `has_tool/list_tools/call`
- `ContextFacade`
- `HostRuntimeAdapter`
- `ModuleStateStore`

判断标准很简单:

- 同一个工具名在模块里只出现 1 到 3 次，直接调
- 真有重复，就抽一个纯函数
- 不要为了“以后也许会复用”先搭一层平台
