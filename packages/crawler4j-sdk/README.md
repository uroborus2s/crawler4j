# Crawler4j SDK

任务脚本开发工具包（Software Development Kit）。

## 使用 CLI 的两种方式

方式 1：安装后长期使用

```bash
uv tool install crawler4j-sdk
crawler4j --help
```

方式 2：不安装，直接一次性运行

```bash
uvx --from crawler4j-sdk crawler4j --help
```

如果你已经创建了 model 项目，并且项目目录里执行过 `uv sync`，也可以直接在项目内使用：

```bash
uv run crawler4j --help
```

## 快速开始

```python
from crawler4j_sdk import TaskContext, TaskResult, TaskScript


class MyTask(TaskScript):
    name = "my_task"
    display_name = "我的任务"
    description = "这是一个示例任务"
    default_config = {"timeout": 30}

    async def execute(self, ctx: TaskContext) -> TaskResult:
        if not ctx.page:
            return TaskResult.fail(message="当前运行环境没有可用的浏览器 Page")

        await ctx.page.goto("https://example.com")
        timeout = ctx.get_config("timeout", 30)
        ctx.logger.info(f"任务执行中，timeout={timeout}")

        if ctx.tools and ctx.tools.has_tool("db.get_state"):
            cursor = ctx.tools.call("db.get_state", key="demo:cursor")
            ctx.logger.info(f"当前游标: {cursor}")

        return TaskResult.ok(message="完成")
```

## 核心 API

### 稳定契约（同 MAJOR 版本内冻结）

| 类型 | 说明 |
|:---|:---|
| `TaskScript` | 原子任务基类 |
| `TaskFlow` | 工作流编排基类 |
| `TaskContext` | 任务执行上下文 |
| `TaskResult` | 任务结果模型 |
| `TaskSignal` | 模块通知 ATM 的流程控制信号 |
| `TaskSignalAction` | `TaskSignal` 的动作枚举 |
| `EnvAction` | 任务结束后 ATM 对运行环境执行的动作 |
| `ToolsCapability` | Core 注入的统一工具入口 |
| `ToolSpec` | Core 工具声明元数据（`name` / `description` / `is_async`） |

### TaskContext 常用能力

| 属性/方法 | 说明 |
|:---|:---|
| `ctx.page` | Playwright Page 对象 |
| `ctx.logger` | 日志记录器 |
| `ctx.http` | HTTP 客户端 |
| `ctx.config` | 宿主持久化后的模块/工作流配置视图 |
| `ctx.state` | 共享状态 |
| `ctx.runtime` | ATM/Debug 写入的执行态输入与元数据 |
| `ctx.run_subtask()` | 调用子任务 |
| `ctx.should_stop()` | 检查停止标志 |
| `ctx.screenshot()` | 截图 |
| `ctx.emit_signal()` | 向 ATM 发出流程控制信号 |
| `ctx.tools` | 宿主注入的统一扩展工具入口 |

固定边界如下：

- `ctx.get_config()` / `ctx.config` 只读取宿主持久化的模块级配置和工作流级覆盖
- `workflow`、`devel_mode`、`execution_params`、`job_params`、`params`、`creation_params` 统一读取 `ctx.runtime`

## Core 工具能力边界

模块侧只应通过 `ctx.tools.call(...)` 使用宿主注入的扩展能力。

当前内置工具名如下：

- `db.list_records`
- `db.replace_records`
- `db.acquire_lock`
- `db.release_lock`
- `db.is_locked`
- `db.get_state`
- `db.set_state`
- `db.exists_state`
- `ip_pool.pick_proxy`
- `env.set_proxy`
- `ui.declare_data_table`
- `ui.get_data_table`
- `captcha.match_slider`
- `captcha.match_click_targets`

如果你需要发现能力，而不是直接调用固定名字，可以使用：

- `ctx.tools.has_tool(name)`
- `ctx.tools.list_tools()`

`ctx.tools.list_tools()` 返回的每一项都是 `ToolSpec`，其中：

- `name` 是工具名
- `description` 是工具描述
- `is_async` 表示这个工具是否需要 `await ctx.tools.call(...)`

不要在模块里直接连接宿主数据库，也不要假设存在 ORM Session、原生 SQLite 连接或其他私有存储对象。

### 常见调用示例

```python
if ctx.tools and ctx.tools.has_tool("db.list_records"):
    records = ctx.tools.call("db.list_records", dataset="orders")
    ctx.tools.call("db.replace_records", dataset="orders", records=records)

if ctx.tools and ctx.tools.has_tool("env.set_proxy"):
    await ctx.tools.call("env.set_proxy", env_id=ctx.env_id, proxy_value="http://127.0.0.1:8888")

if ctx.tools and ctx.tools.has_tool("captcha.match_slider"):
    result = ctx.tools.call(
        "captcha.match_slider",
        background_image=bg_bytes,
        puzzle_piece_image=piece_bytes,
    )
```

## CLI 命令

```bash
# 初始化完整 model 项目
uvx --from crawler4j-sdk crawler4j init-model my_model

# 进入模块目录并安装依赖后，创建任务脚本（交互式）
uv run crawler4j add

# 进入模块目录后，创建任务脚本（快速）
uv run crawler4j new my_task

# 进入模块目录后，列出任务脚本
uv run crawler4j list

# 创建工作流并写入 module.yaml
uv run crawler4j add-workflow sync_orders

# 创建代码型 UI 页面
uv run crawler4j add-ui dashboard
```

`init-model` 默认会进入一轮初始化向导，并在创建后自动：

- 生成 `.gitignore`
- 生成 `.python-version`
- 执行 `git init`
- 执行 `uv sync`

如果你在 CI 或脚本里使用 CLI，可以加 `--defaults` 跳过交互；如需跳过自动初始化动作，可额外使用 `--no-git` 或 `--no-install`。

调试主路径已经收敛到 Core 调试会话。CLI 不再生成 `debug_runner.py`。

## 工作流示例

```python
from crawler4j_sdk import TaskContext, TaskFlow


class MyWorkflow(TaskFlow):
    name = "my_workflow"

    async def run(self, ctx: TaskContext) -> None:
        await ctx.run_subtask("login")

        while not ctx.should_stop():
            ctx.state["phase"] = "claim"
            task = await ctx.run_subtask("claim_task")
            if not task:
                break

            ctx.state["phase"] = "process"
            await ctx.run_subtask("process", task=task)
```

## 运行期控制信号

模块如果需要让 ATM 接管流程动作，例如等待人工确认或在失败后销毁环境，应通过 `TaskSignal`，而不是直接操作宿主运行环境。

```python
from crawler4j_sdk import EnvAction, TaskResult, TaskSignal


return TaskResult.fail(
    message="检测到黑号",
    error="black_account",
    signal=TaskSignal.fail(
        message="检测到黑号",
        error="black_account",
        env_action=EnvAction.DESTROY,
    ),
)
```

当前 `TaskScript` / `TaskFlow` 自身只有一个稳定入口方法：`execute(ctx)` 或 `run(ctx)`。
`module_runtime.py` 现在是标准模块文件，不再是可选扩展点。模块级生命周期统一在其中实现：

- `prepare_env`
- `@env_selector(...)` 声明环境选择回调，供 ATM 的“选择环境”模式调用
- `init_env`
- `before_run`
- `on_success`
- `on_failure`
- `on_timeout`
- `on_cleanup`

脚手架默认会生成两个示例环境选择器：

- `return_none`：占位选择器，固定返回 `None`，用于提醒开发者必须替换成真实逻辑
- `random_ready`：从当前 `ready` 候选环境里随机选择一个

`on_cleanup` 发生在 ATM 完成环境动作之后。如果模块需要在环境已删除后清理自己的数据，应在 `on_cleanup` 中读取 `ctx.runtime["env_action"]`，而不是再增加一套额外的“环境删除 hook”。

## 版本兼容

- Python: `>= 3.12`
- 遵循语义化版本（SemVer）
