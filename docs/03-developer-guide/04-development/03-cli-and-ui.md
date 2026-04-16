# 4.3 CLI 命令与 UI 配置

## CLI 命令怎么理解

下面这些命令都要求当前目录处于模块项目里，也就是当前目录或父目录能找到 `module.yaml`。

```bash
uv run crawler4j add
uv run crawler4j new fetch_hotels
uv run crawler4j list
uv run crawler4j add-workflow sync_hotels
uv run crawler4j add-ui
```

各命令的真实作用如下。
当前 CLI 生成的新模块项目默认面向 `crawler4j-sdk 1.2.0`：模块项目依赖会落到 `>=1.2.0,<2.0.0`，`module.yaml.sdk_version_range` 也会从 `>=1.2.0` 起步。

如果你是第一次接触这些命令，可以把它们理解成“在标准模块项目上继续补结构的工具”，而不是“随便在哪个目录都能用的通用命令”。

### `add`

交互式创建任务脚本。适合第一次上手或你不想自己想文件名模板时使用。

如果你还不熟悉任务脚本的文件命名规则，先用它会更稳。

### `new <task_name>`

快速创建任务脚本文件。如果你已经知道任务名，通常比 `add` 更快。

第一次写模块时，最常见的做法是先用 `new` 补一个自己命名的任务脚本，再去修改内容。

### `list`

列出当前模块中的任务脚本。这是最简单的自检命令之一：如果这里列不出你的任务，说明项目结构或发现逻辑有问题。

对新手来说，这个命令的价值非常高。因为它能帮你快速回答一个问题：

> “CLI 有没有把我刚写的任务真正识别出来？”

### `add-workflow <workflow_name>`

创建工作流文件，并同步更新 `module.yaml.workflows`。这比手工加文件后再手改清单更稳。

第一次开发模块时，建议优先用它，而不是自己手动新建空文件。

### `add-ui`

生成代码型 UI 页面 `ui/<name>.py`，并把 `module.yaml.ui_extension` 更新为 `micro_app` 入口。

如果命令提示：

```text
当前目录不在 model 项目中，找不到 module.yaml
```

先不要继续排别的问题，先确认你已经 `cd` 到模块根目录。因为对这些命令来说，“你在哪个目录里执行”本身就是输入条件的一部分。

## `add-ui` 生成的最小示例

例如执行：

```bash
uv run crawler4j add-ui dashboard
```

CLI 会生成类似下面的页面骨架：

```python
# ui/dashboard.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from crawler4j_sdk import TaskContext


class DashboardPage(QWidget):
    def __init__(self, ctx: TaskContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Dashboard"))

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.on_refresh)
        layout.addWidget(refresh_btn)

    def on_refresh(self):
        self.ctx.logger.info("UI 请求刷新数据")
```

同时，CLI 会把 `module.yaml` 更新成：

```yaml
ui_extension:
  type: micro_app
  entry: ui:DashboardPage
```

`config_schema.json` 已从当前脚手架和主链路中移除。模块持久配置由宿主统一维护并保存，不再要求模块目录里再放一份声明式 JSON 文件。

## `module.yaml` 里的 UI 扩展示例

### 通用数据表入口

```yaml
ui_extension:
  detail_menu:
    - id: accounts
      icon: "👤"
      label: "账号管理"
      entry: "core:data_table:accounts"
```

这表示模块详情页左侧会出现一个二级菜单，入口类型是宿主提供的通用数据表页面。

可以把它理解成“宿主已经帮你准备好的一个标准表格页”，你只需要声明入口，不需要自己从头画页面。

这条能力通常和下面这组调用一起出现：

```python
if ctx.tools and ctx.tools.has_tool("ui.declare_data_table"):
    ctx.tools.call("ui.declare_data_table", view_id="accounts", schema={
        "title": "账号管理",
        "dataset": "accounts",
        "columns": ["id", "phone_number", "status"],
    })

if ctx.tools and ctx.tools.has_tool("db.list_records"):
    rows = ctx.tools.call("db.list_records", dataset="accounts")
    ctx.tools.call("db.replace_records", dataset="accounts", records=rows)
```

也就是说，`core:data_table:<view_id>` 负责页面入口声明，真正的数据仍然来自 Core 注入的 `ctx.tools`。
如果你的旧模块还在用 `ctx.db.accounts`、`ctx.db.tasks` 这类历史写法，先改到 `ctx.tools.call("db.*", ...)` 再继续接数据表页面。

从当前实现开始，宿主在打开或刷新 `core:data_table:<view_id>` 页面时，会先同步调用模块根入口导出的 `declare_ui(context)` 来刷新 schema。
如果 schema 中声明了 `create_handler`、`update_handler`，通用页的“新增 / 编辑”会继续路由到同名同步 hook。
推荐做法仍然是让根 `__init__.py` 只做薄壳转发，真实逻辑放在 `module_runtime.py`。

如果当前模块来源是 `DevLink`，详情页点击“刷新”时会以 `devel_mode=true` 重新加载本地 hook，便于联调数据表 schema 和 CRUD 行为。

### 代码型 UI 页面 (Micro App)

当你需要实时图表、复杂的拖拽交互或专门的管理面板时，可以使用 `micro_app` 模式。

```yaml
ui_extension:
  type: micro_app
  detail_menu:
    - id: dashboard
      icon: "📊"
      label: "实时面板"
      entry: "ui:DashboardPage"
```

#### 1. 实现契约
要在模块中实现代码型 UI，你需要在 `ui/` 包内提供页面类，并从 `ui/__init__.py` 导出一个继承自 `QWidget` 的类：

```python
# ui/__init__.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class DashboardPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx  # Core 注入的 TaskContext

        layout = QVBoxLayout(self)
        self.label = QLabel("正在连接实时数据...")
        layout.addWidget(self.label)

    def refresh_data(self):
        # 利用 ctx.tools 读取最新状态并更新 UI
        stats = self.ctx.tools.call("db.get_state", key="sync_stats") or {}
        self.label.setText(f"已同步: {stats.get('count', 0)}")
```

#### 2. 注意事项
*   **线程安全**：UI 在宿主主线程运行，耗时操作必须通过 `QThread` 或异步方式处理，严禁阻塞 UI 线程。
*   **上下文共享**：UI 拿到的 `ctx` 与任务脚本拿到的 `ctx` 共享同一个后端存储，因此可以通过 `ctx.tools.call("db.*", ...)` 实现 UI 与后台任务的准实时通信。

---

## 模块发布前自检清单 (Release Checklist)

在打包 `.zip` 提交给用户或安装到正式环境前，请依次确认以下 6 项：

1. **[ ] 目录契约**：模块目录名、`module.yaml.name` 和包名（`__init__.py` 所在目录）必须完全一致。
2. **[ ] 版本范围**：`module.yaml` 中的 `sdk_version_range` 必须设置为 `>=1.2.0`。
3. **[ ] 依赖孤立**：确保所有第三方库已在 `pyproject.toml` 中声明，且没有硬编码任何本地绝对路径。
4. **[ ] 接口合规**：代码中已彻底删除 `DataService`、`ctx.db.storage` 和直接依赖 `ctx.db` 字段的旧接口。
5. **[ ] 停止响应**：长循环任务中是否已调用 `ctx.should_stop()` 检查停止信号？
6. **[ ] 离线验证**：在未联网环境下，模块的基础导入逻辑（`import` 部分）是否能正常通过？


## 第一次开发模块时该怎么选

建议按下面优先级来：

1. 不写 `ui_extension`，先用宿主默认配置页
2. `core:data_table:<view_id>`
3. `ui:SomePage`

原因很简单：越往下，越依赖更多宿主侧条件。第一次开发模块时，你要优先追求“能稳定跑通”，而不是“最炫的扩展能力”。

## 一条适合新手的 UI 递进路线

如果你想稳一点，可以按下面这个顺序升级：

1. 第一版只做宿主默认配置页
2. 第二版再考虑 `core:data_table:<view_id>`
3. 最后才考虑代码型 UI 页面

这样你每次只解决一类问题，不会把“模块主链问题”和“UI 扩展问题”混在一起。
