# 4.1 编写 TaskScript

## TaskScript 是什么

`TaskScript` 是最小可执行单元。  
如果工作流是“怎么编排”，那任务脚本就是“具体做什么”。

在 SDK 里，一个标准任务脚本有这些稳定接口：

- 类属性：`name`、`display_name`、`description`、`default_config`
- 方法：`execute(ctx)`
- 可选 hooks：`on_init(ctx)`、`on_error(ctx, error)`、`on_cleanup(ctx)`

生命周期顺序如下：

```text
on_init
-> execute
-> on_error（仅异常时）
-> on_cleanup
```

如果你完全没接触过 `TaskScript`，可以把它想成：

- 输入：`TaskContext`
- 过程：做一件具体业务动作
- 输出：`TaskResult`

它不是“整个业务流程”，只是整个流程中的一个最小步骤。

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
| `ctx.db` / `ctx.ip_pool` / `ctx.env_ops` / `ctx.ui` | 宿主注入的能力接口 |

### 小白最先该用哪几个

第一次开发模块时，优先掌握下面 5 个就够了：

1. `ctx.get_config()`
2. `ctx.page`
3. `ctx.logger`
4. `ctx.state`
5. `ctx.screenshot()`

其它能力等你已经把主链跑通后再扩展，不要一开始就把所有接口都用上。

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
