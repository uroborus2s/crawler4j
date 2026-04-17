# Crawler4j SDK

用于构建 `crawler4j` 标准模块项目的 SDK 与 CLI。

当前源码与开发者文档统一以 `0.2.0` 为基线。注意：模块自己的 `module.yaml.version` 可以独立演进，因此示例 ZIP 名称里的 `0.1.0` 仅表示模块版本，不代表 SDK 仍停留在 `0.1.x`。

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
| `ModuleAssembler` | 标准模块根入口组装器 |
| `env_selector` / `EnvSelectorInfo` | 环境选择器声明与元信息 |
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
# 初始化模块项目：生成标准骨架、module.yaml、module_runtime.py
uvx --from crawler4j-sdk crawler4j module init my_model --repo owner/my_model

# 查看当前模块的版本、仓库、默认工作流、页面入口和数据表入口
uv run crawler4j module show

# 创建任务脚本：只写 tasks/<name>.py
uv run crawler4j task create login

# 创建工作流：写 workflows/<name>.py，并同步更新 module.yaml.workflows
uv run crawler4j workflow create sync_orders

# 创建代码型页面：写 ui/<name>.py，并设置 ui_extension.entry
uv run crawler4j page create dashboard

# 创建受控数据表：注册 core:data_table:<view_id>，并补 declare_ui 骨架
uv run crawler4j data-table create accounts

# 创建环境选择器：在 module_runtime.py 里追加 @env_selector(...) 函数
uv run crawler4j env-selector create pick_ready

# 设置默认配置模板
uv run crawler4j config set module --file defaults.yaml

# 发布前完整校验
uv run crawler4j check full

# 构建宿主可安装 ZIP
uv run crawler4j package build

# 发布本地 ZIP 到 GitHub Release
uv run crawler4j release publish --dry-run

# 通过 SDK CLI 桥接宿主能力
uv run crawler4j host devlink add /path/to/module
uv run crawler4j host install preview dist/my_model-0.1.0.zip --skip-remote-check
uv run crawler4j host upgrade check my_model
uv run crawler4j host debug config
```

当前命令树按“模块元素”和“生命周期动作”分组：

- `module`：初始化模块项目，或维护 `repo / version / default-workflow`
- `task`：管理 `tasks/` 里的 `TaskScript`
- `workflow`：管理 `workflows/` 和 `module.yaml.workflows`
- `page`：管理代码型页面和 `ui_extension.entry`
- `data-table`：管理受控 `core:data_table:<id>` 入口
- `env-selector`：管理 `module_runtime.py` 里的环境选择策略函数
- `config`：管理 `module.yaml.config_defaults`
- `package`：构建和校验安装 ZIP
- `release`：看本地发布状态、检查 GitHub Release 最新版本、发布 Release 资产
- `host`：通过 SDK CLI 桥接宿主的 DevLink、安装、升级和调试配置
- `check`：运行 `structure / release / full` 三档完整性校验

`module init` 会默认：

- 生成 `.gitignore`
- 生成 `.python-version`
- 生成 `module_runtime.py`
- 执行 `git init`
- 执行 `uv sync`

如果你在 CI 或脚本里使用 CLI，可以直接补齐 `--repo`、`--no-git`、`--no-install` 等参数。第一版命令树已经切到 `module / task / workflow / page / data-table / env-selector / config / package / release / host / check` 分组体系，不再兼容旧平铺命令。

调试主路径已经收敛到 Core 调试会话。旧的 `debug_runner.py` 辅助脚本已从宿主仓库移除，CLI 也不再生成任何本地调试壳脚本。
模块持久配置由宿主统一维护，`config_schema.json` / `strategy.yaml` 已不再受支持；详情页扩展数据表也应通过 `data-table create` 写入受控的 `core:data_table:<view_id>` 入口，而不是手改 `module.yaml`。

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
- `declare_ui`
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
- 当前源码包版本：`0.2.0`
