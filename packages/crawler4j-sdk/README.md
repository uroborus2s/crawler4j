# Crawler4j SDK

用于构建 `crawler4j` 标准模块项目的 SDK 与 CLI。

当前源码与开发者文档统一以 `0.4.0` 为基线。注意：模块自己的 `module.yaml.version` 可以独立演进，因此示例 ZIP 名称里的 `0.1.0` 仅表示模块版本，不代表 SDK 仍停留在 `0.1.x`。

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
| `ctx.http` | 可选 HTTP 客户端（宿主注入，或模块显式注入） |
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
- `ctx.http` 是可选注入的 `HttpClient` 协议对象；contracts 层不再默认构造 aiohttp 客户端，如需默认实现可显式注入 `crawler4j_sdk.context.DefaultHttpClient()`

`ctx.run_subtask()` 的返回语义：

- 成功且子任务返回了 `TaskResult.data` 时，直接返回该 payload
- 成功但没有 payload 时，返回 `True`
- 失败时，返回一个 `dict` 风格但布尔值为 `False` 的失败结果，至少保留 `status=failed` 以及可用的 `message` / `error`

## Core 工具能力边界

模块侧只应通过 `ctx.tools.call(...)` 使用宿主注入的扩展能力。

当前内置工具名如下：

- `db.list_records`
- `db.replace_records`
- `db.append_event`
- `db.query_events`
- `db.acquire_lock`
- `db.release_lock`
- `db.is_locked`
- `db.get_state`
- `db.set_state`
- `db.exists_state`
- `db.declare_data_resource`
- `db.declare_db_view`
- `db.query_view`
- `ip_pool.pick_proxy`
- `env.set_proxy`
- `env.bind_resource_pool`
- `env.mark_resource_pool_eligible`
- `env.mark_resource_pool_ineligible`
- `env.remove_resource_pool`
- `env.replace_resource_pool_snapshot`
- `ui.declare_page`
- `ui.get_page`
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

if ctx.tools and ctx.tools.has_tool("db.append_event"):
    ctx.tools.call(
        "db.append_event",
        dataset="order_events",
        event_type="status_changed",
        entity_key="order-001",
        previous_status="pending",
        next_status="paid",
        result="success",
        reason="payment_confirmed",
        payload={"gateway": "alipay"},
    )

if ctx.tools and ctx.tools.has_tool("env.set_proxy"):
    await ctx.tools.call("env.set_proxy", env_id=ctx.env_id, proxy_value="http://127.0.0.1:8888")

from crawler4j_sdk import bind_resource_pool, mark_resource_pool_ineligible

if ctx.tools and ctx.tools.has_tool("env.bind_resource_pool"):
    await bind_resource_pool(ctx, pool_name="bound_account_ready")

if ctx.tools and ctx.tools.has_tool("env.mark_resource_pool_ineligible"):
    await mark_resource_pool_ineligible(
        ctx,
        pool_name="bound_account_ready",
        reason="blacklisted",
    )

if ctx.tools and ctx.tools.has_tool("captcha.match_slider"):
    result = ctx.tools.call(
        "captcha.match_slider",
        background_image=bg_bytes,
        puzzle_piece_image=piece_bytes,
    )
```

固定环境池口径：

- `bind_resource_pool` / `mark_resource_pool_eligible` / `mark_resource_pool_ineligible` / `remove_resource_pool` / `replace_resource_pool_snapshot` 都是异步 helper，必须 `await`
- 这些 helper 依赖宿主提供对应的 `env.*resource_pool*` capability；如果宿主版本可能偏旧，请先用 `ctx.tools.has_tool(...)` 判断
- 若 capability 缺失，helper 会抛出明确 `RuntimeError`，而不是让底层 `call()` 直接冒出 `KeyError`
- helper 的 `pool_name` 只写资源池名，例如 `bound_account_ready`
- 宿主内部会按当前模块自动生成 metadata key `<module_name>:<pool_name>`；模块侧不要自己拼这个 key

## CLI 命令

```bash
# 初始化模块项目：生成标准骨架、module.yaml、module_runtime.py
uvx --from crawler4j-sdk crawler4j module init my_model --repo owner/my_model

# 查看当前模块的版本、仓库、默认工作流和页面入口
uv run crawler4j module show

# 创建任务脚本：只写 tasks/<name>.py
uv run crawler4j task create login

# 创建工作流：写 workflows/<name>.py，并同步更新 module.yaml.workflows
uv run crawler4j workflow create sync_orders

# 创建宿主页：写 module_runtime.py 中的 schema / load handler，并注册 ui_extension.pages[]
uv run crawler4j page create dashboard

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
- `page`：管理 hosted page 和 `ui_extension.pages[]`
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

如果你在 CI 或脚本里使用 CLI，可以直接补齐 `--repo`、`--no-git`、`--no-install` 等参数。第一版命令树已经切到 `module / task / workflow / page / env-selector / config / package / release / host / check` 分组体系，不再兼容旧平铺命令。

调试主路径已经收敛到 Core 调试会话。旧的 `debug_runner.py` 辅助脚本已从宿主仓库移除，CLI 也不再生成任何本地调试壳脚本。
模块持久配置由宿主统一维护，`config_schema.json` / `strategy.yaml` 已不再受支持；列表页、统计页和可编辑表格页都应通过 `page create` 生成页面骨架，再在页面 schema 中声明 `DataTable` 组件，而不是手改旧式 `entry` 或独立数据表入口。

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

`on_cleanup` 会在 ATM 执行计划中的环境动作之前触发。如果模块需要根据即将执行的 `recycle / keep_alive / destroy` 做收尾，应在 `on_cleanup` 中读取 `ctx.runtime["env_action"]`，而不是再增加一套额外的“环境删除 hook”。

## 版本兼容

- Python: `>= 3.12`
- 遵循语义化版本（SemVer）
- 当前源码包版本：`0.4.0`
