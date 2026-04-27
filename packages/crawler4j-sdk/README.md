# Crawler4j SDK

`crawler4j-sdk` 现在只负责 4 类能力：

- CLI
- 模块脚手架
- 本地校验
- 开发辅助

运行时 owner 只有 Core。模块在运行时环境里只需要安装 `crawler4j-contracts`，不再依赖 `crawler4j-sdk`。

## 包边界

### `crawler4j-contracts`

模块运行时代码只从这里导入稳定契约：

- `TaskContext`
- `TaskResult`
- `TaskSignal`
- `EnvAction`
- `EnvCandidate`
- `TaskSpec`
- `WorkflowSpec`
- `EnvSelectorSpec`
- `PageSpec`
- `crawler4j_contracts.hosted_ui` 里的 Hosted UI schema/helper

### `crawler4j-sdk`

这里只保留：

- `crawler4j` CLI
- 模块模板生成
- `check structure/release/full`
- 打包与发布辅助
- 少量开发期 helper，例如 `DefaultHttpClient`

不再导出：

- `ModuleAssembler`
- `TaskScript`
- `TaskFlow`
- `env_selector`
- `hosted_ui`
- 任何运行时 owner 角色

## 核心协议

模块必须声明：

```yaml
name: demo_module
runtime_api: core-native-v1
version: 0.1.0
upgrade_source:
  type: github_release
  repo: example/demo_module
default_workflow: main_workflow
workflows:
  - name: main_workflow
    display_name: Main Workflow
    description: 默认工作流
ui_extension:
  pages: []
```

没有 `runtime_api: core-native-v1`，或值不是这个，Core 会直接拒绝加载。

## 模块目录

```text
demo_module/
├── __init__.py
├── module.yaml
├── pyproject.toml
├── tasks/
│   └── *.py
├── workflows/
│   └── *.py
├── hooks/
│   └── *.py
├── env_selectors/
│   └── *.py
└── pages/
    ├── *.py
    └── <group>/
        └── *.py
```

Core 会自行扫描目录并生成 runtime descriptor。它不会调用模块根 `run()`，也不会再调用 `declare_ui()`。

固定扫描规则：

- `tasks/*.py` 导出 `TASK` 和 `execute`
- `workflows/*.py` 导出 `WORKFLOW` 和 `run`
- `hooks/*.py` 导出 `handle`
- `env_selectors/*.py` 导出 `SELECTOR` 和 `select`
- `pages/*.py` 或 `pages/<group>/*.py` 导出 `PAGE` 和页面处理函数

## 最小示例

### 任务

```python
from crawler4j_contracts import TaskContext, TaskResult, TaskSpec

TASK = TaskSpec(
    name="example_task",
    display_name="示例任务",
    description="最小任务示例",
)


async def execute(ctx: TaskContext) -> TaskResult:
    if not ctx.page:
        return TaskResult.fail(message="当前运行环境没有可用的浏览器 Page")
    await ctx.page.goto("https://example.com", wait_until="domcontentloaded")
    return TaskResult.ok(data={"url": ctx.page.url})
```

### 工作流

```python
from crawler4j_contracts import TaskContext, WorkflowSpec

WORKFLOW = WorkflowSpec(
    name="main_workflow",
    display_name="Main Workflow",
    tasks=("example_task",),
)


async def run(ctx: TaskContext):
    return await ctx.run_subtask("example_task")
```

### Hook

```python
from crawler4j_contracts import TaskContext


async def handle(context: TaskContext):
    return None
```

### 环境选择器

```python
from crawler4j_contracts import EnvCandidate, EnvSelectorSpec, TaskContext

SELECTOR = EnvSelectorSpec(
    name="pick_ready",
    display_name="选择 ready 环境",
)


def select(context: TaskContext, candidates: list[EnvCandidate]):
    del context
    ready = [item for item in candidates if item.status == "ready"]
    return ready[0].env_id if ready else None
```

### 宿主页

```python
from crawler4j_contracts import PageSpec, TaskContext

PAGE = PageSpec(
    id="dashboard",
    label="Dashboard",
    icon="📄",
    schema={
        "type": "Page",
        "load_handler": "load_dashboard_page",
        "children": [
            {"type": "Text", "style": "title", "binding": "title"},
        ],
    },
)


def load_dashboard_page(context: TaskContext, page_id: str, params: dict | None = None) -> dict:
    del context, page_id, params
    return {"title": "Dashboard"}
```

## CLI

### 初始化模块

```bash
uvx --from crawler4j-sdk crawler4j module init demo_module --repo example/demo_module
```

### 常用命令

```bash
uv run crawler4j module show
uv run crawler4j module repair-init
uv run crawler4j task create example_task
uv run crawler4j workflow create repair_orders
uv run crawler4j page create dashboard
uv run crawler4j page create account_detail --group account --no-menu
uv run crawler4j env-selector create pick_ready
uv run crawler4j hook create on_cleanup
uv run crawler4j check full
uv run crawler4j package build
```

`module repair-init` 会只重建模块根 `__init__.py`，适合在清理旧 `run()` / `declare_ui()` 残留后，把根包恢复到当前标准模板；它不会覆盖 `module.yaml`、任务、工作流或页面源码。

## 校验规则

`check full` 当前会校验：

- `module.yaml.runtime_api == core-native-v1`
- `default_workflow` 与 `module.yaml.workflows` 一致
- `data.resources[]` 不包含 `resource_id` 等未知字段；资源项公开字段使用 `id`
- `TaskSpec/WorkflowSpec/EnvSelectorSpec/PageSpec` 导出是否存在
- `TASK.name` / `WORKFLOW.name` / `SELECTOR.name` 是否与文件名一致
- `ui_extension.pages[]` 中的菜单页面是否有对应页面文件
- `pages/*.py`、`pages/<group>/*.py` 是否导出唯一且合法的 `PAGE.id`
- 页面 `load_handler` 和内联表格 `query_handler` 是否存在且签名兼容
- legacy `ui/`、`config_schema.json`、`strategy.yaml` 是否已清理

## 运行期依赖

模块自己的 `pyproject.toml` 应该是：

```toml
[project]
dependencies = [
  "crawler4j-contracts>=0.4.0,<0.5.0",
]

[dependency-groups]
dev = [
  "crawler4j-sdk>=0.6.1,<0.7.0",
  "pytest>=9.0.2",
  "pytest-asyncio>=1.3.0",
]
```

CLI 脚手架生成的 `pyproject.toml` 会默认写入同样的兼容范围。

意思是：

- 运行时只要 contracts
- 本地开发和脚手架才需要 sdk

## 资源池与 HTTP helper

SDK 仍保留 `crawler4j_sdk.context.DefaultHttpClient` 作为本地开发辅助。

模块运行时代码不得依赖 `crawler4j-sdk`。资源池运行时能力由宿主注入到 `ctx.tools`，模块如果需要绑定、标记或移除资源池，应通过 `ctx.tools.has_tool(...)` / `ctx.tools.call(...)` 调用宿主工具，例如：

```python
if ctx.tools.has_tool("env.bind_resource_pool"):
    await ctx.tools.call(
        "env.bind_resource_pool",
        env_id=ctx.env_id,
        pool_name="default",
    )
```
