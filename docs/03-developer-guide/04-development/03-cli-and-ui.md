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

### 代码型 UI 页面

```yaml
ui_extension:
  type: micro_app
  detail_menu:
    - id: custom
      icon: "🧩"
      label: "自定义页"
      entry: "ui:AccountConfigPage"
```

要让这条路径真正工作，还必须同时满足：

1. 模块里存在 `ui.py`
2. `ui.py` 导出了对应的 `QWidget` 类
3. 模块来源是 `DevLink` / 内置来源，或者模块名命中 `mms.ui.allowlist`

第一次开发模块时，如果你还没有把任务脚本、工作流和调试链路跑稳，不建议立刻走这条路径。

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
