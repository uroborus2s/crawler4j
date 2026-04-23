# 快速开始

这一页只讲一条最短闭环：

1. 用 CLI 生成 `core-native-v1` 模块骨架
2. 用 `crawler4j-contracts` 写任务、工作流、页面
3. 用 DevLink 接到宿主里联调
4. 构建 ZIP 并做安装验收

## 1. 初始化模块

下面以 `hotel_demo` 为例：

```bash
cd /absolute/path/to/your/workspace
uvx --from crawler4j-sdk crawler4j module init hotel_demo \
  --repo your-org/hotel_demo \
  --no-git \
  --no-install

cd /absolute/path/to/your/workspace/hotel_demo
uv sync
uv run crawler4j module show
```

初始化后的关键事实：

- `module.yaml.runtime_api` 已固定为 `core-native-v1`
- 运行时依赖只包含 `crawler4j-contracts`
- `crawler4j-sdk` 只放在开发依赖里
- Core 会扫描 `tasks/`、`workflows/`、`hooks/`、`env_selectors/`、`pages/`

## 2. 生成业务骨架

```bash
uv run crawler4j task create fetch_hotels
uv run crawler4j workflow create hotel_sync --display-name "酒店同步"
uv run crawler4j module set default-workflow hotel_sync
uv run crawler4j page create dashboard --display-name "运营看板"
uv run crawler4j hook create before_run
uv run crawler4j env-selector create pick_ready
uv run crawler4j check structure
```

这一步只负责生成标准文件和更新 `module.yaml`。不要手写兼容薄壳，也不要把运行时逻辑放回根包。

## 3. 写最小任务

`tasks/fetch_hotels.py` 的正式导出是 `TASK` 和 `execute`：

```python
from crawler4j_contracts import TaskContext, TaskResult, TaskSpec

TASK = TaskSpec(
    name="fetch_hotels",
    display_name="抓取酒店",
    description="抓取酒店列表",
)


async def execute(ctx: TaskContext) -> TaskResult:
    return TaskResult.ok(data={"count": 0, "message": "ok"})
```

## 4. 写最小工作流

`workflows/hotel_sync.py` 的正式导出是 `WORKFLOW` 和 `run`：

```python
from crawler4j_contracts import TaskContext, WorkflowSpec

WORKFLOW = WorkflowSpec(
    name="hotel_sync",
    display_name="酒店同步",
    tasks=("fetch_hotels",),
)


async def run(ctx: TaskContext):
    return await ctx.run_subtask("fetch_hotels")
```

`module.yaml` 里必须同时满足：

- `runtime_api: core-native-v1`
- `default_workflow: hotel_sync`
- `workflows` 数组里存在 `hotel_sync`

## 5. 写最小页面

`pages/dashboard.py` 的正式导出是 `PAGE` 和页面 handler：

```python
from crawler4j_contracts import PageSpec, TaskContext

PAGE = PageSpec(
    id="dashboard",
    label="运营看板",
    icon="📄",
    schema={
        "type": "Page",
        "title": "运营看板",
        "load_handler": "load_dashboard_page",
        "children": [
            {"type": "Text", "style": "title", "binding": "title"},
        ],
    },
)


def load_dashboard_page(
    context: TaskContext,
    page_id: str,
    params: dict | None = None,
) -> dict:
    del context, page_id, params
    return {"title": "运营看板"}
```

这里不再有 `declare_ui()`。Core 会直接读取 `PAGE.schema`。

## 6. 校验并接入宿主

在第一次联调前，至少跑：

```bash
uv run crawler4j config lint
uv run crawler4j check full
```

然后切到宿主环境：

```bash
uv run python -c "import src.core; print('ok: host runtime ready')"
uv run crawler4j host devlink add /absolute/path/to/hotel_demo
uv run crawler4j host debug config
```

联调顺序：

1. 打开 `📦 模块管理`，确认来源是 `开发链接`
2. 打开 `📋 任务监控`，创建绑定 `hotel_demo` 的作业
3. 选择 `hotel_sync`
4. 先点 `▶ 执行一次`
5. 需要断点时再点 `🐞 调试`
6. 在模块详情页确认 `dashboard` 已出现

## 7. 构建并安装

回到模块工程环境：

```bash
uv run crawler4j package build
uv run crawler4j package verify dist/hotel_demo-0.1.0.zip
uv run crawler4j release publish --dry-run
```

再回到宿主环境做安装验收：

```bash
uv run crawler4j host install preview dist/hotel_demo-0.1.0.zip --skip-remote-check
uv run crawler4j host install apply dist/hotel_demo-0.1.0.zip --skip-remote-check
```

## 记住这 4 条

- 模块业务代码只 `import crawler4j-contracts`
- Core 是唯一运行时 owner
- 没有 `runtime_api: core-native-v1` 会直接拒绝加载
- 即使运行时环境卸载 `crawler4j-sdk`，模块也必须能跑
