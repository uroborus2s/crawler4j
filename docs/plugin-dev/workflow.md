# 任务与工作流开发 (Task & Workflow)

在 Crawler4j 中，**任务 (Task)** 是最小的执行单元，而 **工作流 (Workflow)** 是任务的串联编排。

## 🧩 原子任务 (Atomic Task)

原子任务应遵循**单一职责原则**。不要把所有逻辑写在一个任务里。

### 优秀实践
*   ✅ `LoginTask`: 只负责登录。
*   ✅ `SearchTask`: 只负责搜索列表页。
*   ✅ `DetailTask`: 只负责抓取详情页。

### 数据交互
任务的输入来自 `ctx.config` 或 `ctx.state`，输出通过 `TaskResult` 返回。

## ⛓️ 任务链编排 (Workflow)

通过 `TaskFlow` (如果 SDK 提供) 或在主任务中手动调度子任务来编排工作流。

```python
class TicketBookingFlow(TaskScript):
    name = "ticket_booking_flow"
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        # 1. 登录
        # 子任务共享 ctx.state，登录凭证会自动保存在 state 中
        await ctx.run_subtask("login_task")
        
        # 2. 查询
        flights = await ctx.run_subtask("search_flight_task", 
                                      dept="SHA", arr="PEK")
        
        # 3. 预订
        if flights:
            await ctx.run_subtask("book_flight_task", flight_id=flights[0]['id'])
            
        return TaskResult.ok("流程完成")
```

## 📦 数据上下文 (Data Context)

`ctx.state` 是工作流的"内存"。

*   **生命周期**: 从工作流开始到结束。
*   **作用域**: 所有子任务共享同一个 `ctx.state` 对象。
*   **用途**: 传递 Cookie、Token、中间结果。

```python
# Task A: 写入
ctx.state["user_token"] = "abcdefg"

# Task B: 读取
token = ctx.state.get("user_token")
```
