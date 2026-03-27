# 6.2 TaskFlow（工作流编排契约）

TaskFlow 用于把多个 TaskScript 组合成一个“可取消、可重试、可观测”的复合流程。

> 术语：
>
> - **原子任务**：`TaskScript`（返回 `TaskResult`）
> - **工作流**：`TaskFlow`（编排多个原子任务）

## 6.2.1 需求说明

- MUST 支持以 Python 代码方式编排：顺序、循环、分支、条件判断。
- MUST 允许在工作流中调用子任务：`await ctx.run_subtask("task_name", **kwargs)`。
- SHOULD 支持“停止请求/取消语义”：工作流可在循环中定期检查 `ctx.should_stop()` 并退出。
- SHOULD 允许工作流级别错误处理：`on_error(ctx, error)`。
- SHOULD 允许工作流完成回调：`on_complete(ctx)`。

## 6.2.2 需求分析分解

TaskFlow 的核心能力拆解：

1. **编排能力**

- 通过 `run(ctx)` 作为唯一入口，允许任意 Python 控制流。

2. **子任务调用**

- 运行时注入 `_subtask_executor`，SDK 侧仅提供调用接口（`TaskContext.run_subtask`）。
- 子任务参数传递：通过 `kwargs` 合并到 `ctx.state`（当前实现）。

3. **停止/取消语义**

- `ctx.request_stop()`：请求停止
- `ctx.should_stop()`：工作流检查停止标志

4. **可观测性**

- 工作流名、子任务名必须进入日志（SDK 提供 `ctx.logger`；运行时负责结构化与采集）。

## 6.2.3 契约设计（状态迁移/断点恢复点）

### 6.2.3.1 最小接口（以当前实现为准）

实现参考：`crawler4j_sdk/workflow.py`

- MUST: `async def run(self, ctx: TaskContext) -> None`
- MAY: `async def on_error(self, ctx: TaskContext, error: Exception) -> None`
- MAY: `async def on_complete(self, ctx: TaskContext) -> None`

### 6.2.3.2 状态模型（建议）

虽然 TaskFlow 本身不返回 `TaskResult`，但运行时需要对“工作流整体成功/失败”进行归一：

- SHOULD：运行时为工作流提供 FlowResult（内部模型），并把关键字段投影到 UI/日志。
- SHOULD：工作流内的关键阶段写入 `ctx.state`（如 `state["phase"] = "search"`），便于诊断。

### 6.2.3.3 断点恢复（阶段性设计）

当前 SDK/实现未内置“自动断点恢复”，但为了可演进，建议约定：

- MAY：工作流通过 `ctx.state` 记录可恢复点，例如：
  - `state["cursor"]`（分页游标）
  - `state["last_task_id"]`（最后处理任务）
  - `state["phase"]`（阶段）
- SHOULD：运行时在需要时将 `ctx.state` 持久化并在重试/恢复时回灌。

## 6.2.4 功能级规格（按模板）

对于具体工作流（如 `ctrip_crawl`），建议在 Modules 章节按模板编写：

- 模板：`docs/archive/reference-srs/templates/feature.md`
- 必备内容：工作流图（可用 mermaid）、子任务清单、循环/终止条件、失败分支与重试策略、可恢复点（如有）。
