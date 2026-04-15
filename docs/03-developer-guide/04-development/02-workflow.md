# 4.2 编写 Workflow

## Workflow 是什么

`TaskFlow` 负责把多个任务脚本组织成一条完整流程。  
它的职责不是做页面细节操作，而是编排：

- 顺序
- 分支
- 循环
- 停止条件
- 阶段状态

一个标准工作流的稳定接口包括：

- 类属性：`name`、`display_name`、`description`
- 方法：`run(ctx)`

`TaskFlow` 类本身不再提供官方 hooks。工作流层只有一个稳定入口 `run(ctx)`；模块级生命周期仍由 ATM 在 `module_runtime.py` 中调度。

如果你是第一次看 `TaskFlow`，可以把它理解成“一个用 Python 写的流程编排器”。它主要负责决定：

- 先做什么
- 后做什么
- 做失败了怎么办
- 做到什么时候停止
- 当前做到哪一步

## 最小工作流示例

```python
from crawler4j_sdk import TaskContext, TaskFlow


class SyncHotelsWorkflow(TaskFlow):
    name = "sync_hotels"
    display_name = "同步酒店"
    description = "按顺序执行抓取任务"

    async def run(self, ctx: TaskContext) -> None:
        ctx.state["phase"] = "sync"
        result = await ctx.run_subtask("fetch_hotels")
        if not result:
            raise RuntimeError("fetch_hotels 执行失败")
```

如果工作流内部需要做错误分支、收尾动作或阶段性回滚，请直接在 `run()` 里写清楚 `try / except / finally`，而不是再给 `TaskFlow` 维护第二套回调系统。

写完以后，别忘了把它声明进 `module.yaml`：

```yaml
workflows:
  - name: sync_hotels
    display_name: 同步酒店
    description: 酒店同步主工作流
```

## 第一次写工作流时，最重要的不是“复杂”，而是“清楚”

一个对新手友好的工作流，通常满足：

1. 名字明确
2. 只调少量子任务
3. `ctx.state["phase"]` 写得清楚
4. 失败条件简单直接

第一次就写复杂循环、复杂状态恢复、复杂分支，往往只会让调试更困难。

## `ctx.run_subtask()` 的返回值语义

这是工作流开发里最容易踩坑的点之一。

当前实现下：

1. 如果子任务返回 `TaskResult.ok(data=...)`，`await ctx.run_subtask(...)` 会直接拿到 `data`
2. 如果子任务成功但没有 `data`，返回值通常会变成 `True`
3. 如果子任务失败且没有数据，返回值通常会变成 `False`

所以这种写法是成立的：

```python
task = await ctx.run_subtask("claim_task")
if not task:
    return
```

但你也要知道，这里拿到的不一定是完整 `TaskResult`，更常见的是“已经展开过的数据”。

### 这对新手意味着什么

你在工作流里不能默认这样写：

```python
result = await ctx.run_subtask("fetch_hotels")
print(result.success)
```

因为 `result` 很可能根本不是完整结果对象。更稳的思路是：

- 如果你希望拿到数据，就让子任务返回 `TaskResult.ok(data=...)`
- 如果你只关心成功/失败，就按真假值来判断

## 长循环里的推荐写法

工作流如果会循环跑多个子任务，建议：

1. 每一轮都检查 `ctx.should_stop()`
2. 在关键阶段写入 `ctx.state["phase"]`
3. 在需要恢复的位置写入 `ctx.state["cursor"]` 或类似字段

示例：

```python
while not ctx.should_stop():
    ctx.state["phase"] = "claim"
    task = await ctx.run_subtask("claim_task")
    if not task:
        break

    ctx.state["phase"] = "process"
    data = await ctx.run_subtask("process_task", task=task)

    ctx.state["phase"] = "submit"
    await ctx.run_subtask("submit_task", data=data)
```

### 为什么要写 `ctx.state["phase"]`

因为一旦工作流变长，你很容易在日志和调试里搞不清“现在到底执行到哪一步了”。写 `phase` 的好处是：

- 你自己更容易看懂
- 其它维护者更容易接手
- 调试时更容易快速定位卡住位置
- 出问题时更容易知道失败发生在哪一段

## 工作流怎样让 ATM 接管流程动作

`TaskFlow` 的职责是编排业务步骤，不是直接操作运行环境。如果流程里需要：

- 等待用户确认
- 明确标记成功 / 失败 / 取消
- 指定任务结束后的环境动作

请返回带 `signal` 的 `TaskResult`，或者在 `run()` 内部调用 `ctx.emit_signal(...)`。

```python
from crawler4j_sdk import EnvAction, TaskFlow, TaskResult, TaskSignal


class ManualReviewWorkflow(TaskFlow):
    name = "manual_review"

    async def run(self, ctx):
        suspect = await ctx.run_subtask("check_account")
        if suspect:
            return TaskResult.ok(
                message="等待人工确认",
                signal=TaskSignal.wait_for_confirmation(
                    message="请人工确认账号状态",
                    env_action=EnvAction.KEEP_ALIVE,
                    payload={"review_type": "account"},
                ),
            )

        return TaskResult.ok(message="无需人工确认")
```

`WAIT_FOR_CONFIRMATION` 会让任务停在 `WAITING_CONFIRMATION`，ATM 暂不执行终态 hooks 和环境清理；直到外部确认成功或失败后，ATM 才继续进入 `on_success` / `on_failure`、环境动作以及最终 `on_cleanup`。

## 推荐开发顺序

第一次开发模块时，工作流不要一开始就写成复杂状态机。  
更稳的顺序是：

1. 先让一个任务脚本稳定可用
2. 再写一个只调用它一次的最小工作流
3. 最后再逐步补循环、分支和恢复状态

这能让你在 DevLink 调试时更快定位问题是出在任务脚本还是出在编排逻辑。

## 新手第一次写工作流时最容易错在哪里

1. 还没写稳定的任务脚本，就先写复杂工作流
2. 没有在 `module.yaml` 里同步声明工作流
3. 把 `ctx.run_subtask()` 当成一定返回完整结果对象
4. 循环里不检查 `ctx.should_stop()`

如果你先把这 4 个点避开，第一次写工作流会轻松很多。
