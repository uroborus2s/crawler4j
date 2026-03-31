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
当前 CLI 生成的新模块项目默认面向 `crawler4j-sdk 2.x`：模块项目依赖会落到 2.x，`module.yaml.sdk_version_range` 也会从 `>=2.0.0` 起步。

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

生成或补齐 `config_schema.json`，并把 `module.yaml.ui_extension` 指向它。

如果命令提示：

```text
当前目录不在 model 项目中，找不到 module.yaml
```

先不要继续排别的问题，先确认你已经 `cd` 到模块根目录。因为对这些命令来说，“你在哪个目录里执行”本身就是输入条件的一部分。

## `config_schema.json` 的最小示例

CLI 模板生成的默认内容类似下面这样：

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "title": "Hotel Demo 配置",
  "description": "Hotel Demo 的运行参数配置",
  "properties": {
    "workflow": {
      "type": "string",
      "title": "工作流名称",
      "default": "main_workflow"
    },
    "start_url": {
      "type": "string",
      "title": "起始 URL",
      "default": "https://example.com"
    },
    "headless": {
      "type": "boolean",
      "title": "无头模式",
      "default": false
    }
  }
}
```

第一次开发模块时，建议把 UI 目标控制在“能输入和保存运行参数”这个级别，不要一开始就设计复杂交互。

### 作为小白，你应该先关注哪几个字段

第一次先看懂下面 3 个字段就够了：

1. `title`
2. `description`
3. `properties`

其中 `properties` 可以简单理解成“这个配置页上有哪些可配置项”。

例如：

- `workflow`
  让你选择或填写工作流名
- `start_url`
  让你填写入口网址
- `headless`
  让你选择是否启用无头模式

你不需要一开始就掌握完整 JSON Schema 规范。

## `module.yaml` 里的 UI 扩展示例

### 声明式配置 UI

```yaml
ui_extension:
  type: declarative
  entry: config_schema.json
  nav_item:
    icon: "🧩"
    label: "模块配置"
```

这条路径最适合作为新模块的第一版 UI。

对小白来说，这也是最推荐的开始方式。

### 通用数据表入口

```yaml
ui_extension:
  type: declarative
  entry: config_schema.json
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
if ctx.ui is not None:
    ctx.ui.declare_data_table("accounts", {
        "title": "账号管理",
        "dataset": "accounts",
        "columns": ["id", "phone_number", "status"],
    })

if ctx.db is not None:
    rows = ctx.db.list_records("accounts")
    ctx.db.replace_records("accounts", rows)
```

也就是说，`core:data_table:<view_id>` 负责页面入口声明，真正的数据仍然来自 Core 注入的 `ctx.db`。
如果你的旧模块还在用 `ctx.db.accounts`、`ctx.db.tasks` 这类历史写法，先改到 `ctx.db` 最小接口，再继续接数据表页面。

### 代码型 UI 页面 (Micro App)

当声明式 UI 无法满足需求（如需要实时图表、复杂的拖拽交互）时，你可以使用 `micro_app` 模式。

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
要在模块中实现代码型 UI，你必须在模块根目录创建 `ui.py`，并导出一个继承自 `QWidget` 的类：

```python
# ui.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class DashboardPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx  # Core 注入的 TaskContext

        layout = QVBoxLayout(self)
        self.label = QLabel("正在连接实时数据...")
        layout.addWidget(self.label)

    def refresh_data(self):
        # 利用 ctx.db 读取最新状态并更新 UI
        stats = self.ctx.db.get_state("sync_stats")
        self.label.setText(f"已同步: {stats.get('count', 0)}")
```

#### 2. 注意事项
*   **线程安全**：UI 在宿主主线程运行，耗时操作必须通过 `QThread` 或异步方式处理，严禁阻塞 UI 线程。
*   **上下文共享**：UI 拿到的 `ctx` 与任务脚本拿到的 `ctx` 共享同一个后端存储，因此可以通过 `ctx.db` 实现 UI 与后台任务的准实时通信。

---

## 模块发布前自检清单 (Release Checklist)

在打包 `.zip` 提交给用户或安装到正式环境前，请依次确认以下 6 项：

1. **[ ] 目录契约**：模块目录名、`module.yaml.name` 和包名（`__init__.py` 所在目录）必须完全一致。
2. **[ ] 版本范围**：`module.yaml` 中的 `sdk_version_range` 必须设置为 `>=2.0.0`。
3. **[ ] 依赖孤立**：确保所有第三方库已在 `pyproject.toml` 中声明，且没有硬编码任何本地绝对路径。
4. **[ ] 接口合规**：代码中已彻底删除 `DataService`、`ctx.db.storage` 等 1.x 时代的旧接口。
5. **[ ] 停止响应**：长循环任务中是否已调用 `ctx.should_stop()` 检查停止信号？
6. **[ ] 离线验证**：在未联网环境下，模块的基础导入逻辑（`import` 部分）是否能正常通过？


## 第一次开发模块时该怎么选

建议按下面优先级来：

1. `config_schema.json`
2. `core:data_table:<view_id>`
3. `ui:SomePage`

原因很简单：越往下，越依赖更多宿主侧条件。第一次开发模块时，你要优先追求“能稳定跑通”，而不是“最炫的扩展能力”。

## 一条适合新手的 UI 递进路线

如果你想稳一点，可以按下面这个顺序升级：

1. 第一版只做 `config_schema.json`
2. 第二版再考虑 `core:data_table:<view_id>`
3. 最后才考虑代码型 UI 页面

这样你每次只解决一类问题，不会把“模块主链问题”和“UI 扩展问题”混在一起。
