# 4.1 编写 TaskScript

## TaskScript 是什么

`TaskScript` 是最小可执行单元。  
如果工作流是“怎么编排”，那任务脚本就是“具体做什么”。

在 SDK 里，一个标准任务脚本有这些稳定接口：

- 类属性：`name`、`display_name`、`description`、`default_config`
- 方法：`execute(ctx)`

`TaskScript` 类本身已经不再承载官方生命周期 hooks。
模块级生命周期统一由 ATM 在 `module_runtime.py` 中调度：

```text
prepare_env
-> init_env
-> before_run
-> execute
-> on_success / on_failure / on_timeout
-> ATM env action
-> on_cleanup
```

如果你完全没接触过 `TaskScript`，可以把它想成：

- 输入：`TaskContext`
- 过程：做一件具体业务动作
- 输出：`TaskResult`

它不是“整个业务流程”，只是整个流程中的一个最小步骤。

如果任务脚本内部需要前后置、异常兜底或局部清理，请直接在 `execute()` 里用正常 Python 控制流处理，例如 `try / except / finally`。不要再给 `TaskScript` 类补一套私有 hooks。

## 最小可运行示例

```python
from crawler4j_sdk import TaskContext, TaskResult, TaskScript


class FetchHotelsTask(TaskScript):
    name = "fetch_hotels"
    display_name = "抓取酒店"
    description = "打开页面并采集标题"

    default_config = {
        "start_url": "https://example.com",
    }

    async def execute(self, ctx: TaskContext) -> TaskResult:
        if not ctx.page:
            return TaskResult.fail(
                message="当前运行环境没有可用的浏览器 Page",
                error="page_not_available",
            )

        start_url = ctx.get_config("start_url", "https://example.com")
        await ctx.page.goto(start_url, wait_until="domcontentloaded")
        title = await ctx.page.title()

        return TaskResult.ok(
            message="采集完成",
            data={"url": ctx.page.url, "title": title},
        )
```

## 任务脚本怎样控制 ATM 流程

任务脚本只负责业务逻辑；如果需要让 ATM 接手流程动作，例如：

- 标记任务失败
- 等待人工确认
- 指定任务结束后销毁运行环境

请通过 `TaskSignal` 表达，而不是直接调用 REM。

```python
from crawler4j_sdk import EnvAction, TaskResult, TaskScript, TaskSignal


class CheckAccountTask(TaskScript):
    name = "check_account"

    async def execute(self, ctx):
        need_manual_review = True
        if need_manual_review:
            signal = TaskSignal.wait_for_confirmation(
                message="等待人工复核",
                reason="risk_control",
                env_action=EnvAction.KEEP_ALIVE,
                payload={
                    "review_type": "account",
                    "confirmation": {
                        "title": "账号复核",
                        "description": "请确认该账号是否允许继续执行。",
                        "fields": [
                            {"label": "账号", "value": "demo-account"},
                            {"label": "风险等级", "value": "high"},
                        ],
                        "confirm_text": "确认放行",
                        "reject_text": "确认拦截",
                    },
                },
            )
            return TaskResult.ok(
                message="等待人工复核",
                signal=signal,
            )

        is_black = False
        if is_black:
            signal = TaskSignal.fail(
                message="检测到黑号",
                error="black_account",
                reason="risk_control",
                env_action=EnvAction.DESTROY,
            )
            return TaskResult.fail(
                message="检测到黑号",
                error="black_account",
                signal=signal,
            )

        return TaskResult.ok(message="账号正常")
```

如果是 `module_runtime.py` 的 `init_env` / `before_run` 阶段，也可以直接调用 `ctx.emit_signal(...)`。当前正式允许发信号的阶段只有：

- `init_env`
- `before_run`
- `run_module`（也就是 `TaskScript.execute()` / `TaskFlow.run()` 内部）

`on_cleanup` 会在 ATM 完成环境动作之后执行，模块可以从 `ctx.runtime["env_action"]` 读取最终动作结果。如果你只是想在“环境已经销毁之后”做模块数据自清理，不需要额外增加一个 `env_deleted` hook。

这里固定一条规则：

- `on_cleanup` 不要求环境一定被删除
- 只要任务已经进入终态并且模块执行上下文已建立，ATM 就会调用它
- 需要区分 `destroy` / `recycle` / `keep_alive` 时，统一读取 `ctx.runtime["env_action"]`
- 需要客户端弹出结构化确认面板时，统一把展示协议写入 `TaskSignal.wait_for_confirmation(..., payload={"confirmation": ...})`

## 第一次看这个示例时，应该怎么看

不要急着一行一行抄。先看结构：

1. 类继承 `TaskScript`
2. 定义 `name`、`display_name`、`description`
3. 定义 `default_config`
4. 在 `execute()` 里从 `ctx` 取参数和能力
5. 最后返回 `TaskResult`

第一次写模块时，只要你能把这 5 件事都写出来，就已经合格了。

## 最常用的 `TaskContext` 能力

第一次写模块时，最常用的是下面这些：

| 能力 | 用途 |
|---|---|
| `ctx.page` | 当前浏览器页面 |
| `ctx.context` | Playwright BrowserContext |
| `ctx.logger` | 打日志 |
| `ctx.http` | 发 HTTP 请求 |
| `ctx.config` / `ctx.get_config()` | 读运行参数 |
| `ctx.state` | 与工作流共享状态 |
| `ctx.screenshot()` | 截图取证 |
| `ctx.should_stop()` | 检查停止标志 |
| `ctx.tools` | 宿主注入的统一工具入口 |

如果你想看完整、正式的能力面，而不是只看“最常用的那几个”，请直接读：

- [4.4 Core 提供的能力清单](04-core-capabilities.md)

### 小白最先该用哪几个

第一次开发模块时，优先掌握下面 5 个就够了：

1. `ctx.get_config()`
2. `ctx.page`
3. `ctx.logger`
4. `ctx.state`
5. `ctx.screenshot()`

其它能力等你已经把主链跑通后再扩展，不要一开始就把所有接口都用上。

## 写任务脚本时，数据能力应该怎么用

如果你的任务脚本需要读写模块数据，不要自己去连数据库。
当前正确做法只有一个：通过 Core 注入的 `ctx.tools.call(...)` 使用正式工具。
`crawler4j-sdk 1.1.1` 起，模块侧统一通过 `TaskContext.tools` 访问宿主扩展能力。

也就是说，当前模块里允许依赖的数据能力只有：

- `db.list_records`
- `db.replace_records`
- `db.get_state` / `db.set_state` / `db.exists_state`
- `db.acquire_lock` / `db.release_lock` / `db.is_locked`

### 一个最小示例

```python
if ctx.tools and ctx.tools.has_tool("db.list_records"):
    records = ctx.tools.call("db.list_records", dataset="orders")
    cursor = ctx.tools.call("db.get_state", key="hotel_demo:orders:cursor") or {"page": 1}

    if ctx.tools.call("db.acquire_lock", scope="orders", key="sync", ttl=60):
        try:
            records.append({"id": "o-1", "status": "new"})
            ctx.tools.call("db.replace_records", dataset="orders", records=records)
            ctx.tools.call(
                "db.set_state",
                key="hotel_demo:orders:cursor",
                value={"page": cursor["page"] + 1},
                ttl=3600,
            )
        finally:
            ctx.tools.call("db.release_lock", scope="orders", key="sync")
```

### 为什么这里强调自己带命名空间

当前 `get_state()` / `set_state()` 使用的是轻量状态键。
为了避免不同模块或不同任务把键名撞在一起，建议你自己带上模块前缀，例如：

- `hotel_demo:orders:cursor`
- `ctrip:login:cookies`

比起只写 `cursor`、`cookies` 这种泛名，前者更稳。

### 从旧模块升级时先改什么

如果你接手的是旧模块，先做下面这组直接替换，再继续写业务逻辑：

1. 删除 `DataService` 导入
2. 把历史 `ctx.db.*` 调用改成 `ctx.tools.call("db.*", ...)`
3. 把旧账号、任务等聚合入口改成 `db.list_records` / `db.replace_records`

## 什么时候返回失败，什么时候抛异常

建议遵守下面的分工：

- 预期内的业务失败：返回 `TaskResult.fail(...)`
- 真正的异常状态：直接抛异常

例如：

- 页面里没有目标元素，但这是业务上允许的结果，可以返回失败。
- 模块逻辑写错、关键对象为空、外部调用崩了，则应抛异常，让运行时进入失败链路。

### 一个简单判断方法

你可以这样问自己：

- 这是业务上“允许失败”的结果吗？
  如果是，优先考虑 `TaskResult.fail(...)`
- 这是程序逻辑或运行环境的异常吗？
  如果是，优先抛异常

这样写出来的行为通常更容易被宿主正确理解和记录。

## 一个适合新手的编写顺序

建议第一次写任务脚本时按这个顺序来：

1. 先把类名和 `name` 写好
2. 先让 `execute()` 能打印日志
3. 再让它读取一个最简单配置项
4. 再让它执行一个最简单动作
5. 最后再补错误处理和截图

不要一开始就把真实业务流程全部搬进去。

## 一个稳妥的编写习惯

第一次写任务脚本时，优先遵守下面几条：

1. 每个任务脚本只做一件事
2. 需要参数时优先从 `ctx.get_config()` 读取
3. 遇到异常场景时尽量截图
4. 不要把复杂编排逻辑塞进单个任务脚本

这样后续把它接进工作流时，你的结构会更清晰。

## 新手最常见的 4 个错误

1. 把整个业务流程都塞到一个任务脚本里
2. 不返回 `TaskResult`，导致上层很难判断执行结果
3. 不写日志，出了问题完全不知道卡在哪
4. 不区分“业务失败”和“程序异常”

如果你先避开这 4 个错误，后面的调试难度会明显下降。
