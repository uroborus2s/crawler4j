# crawler4j 开发者指南

这份指南面向模块开发者。目标只有一个：把一个业务模块从本地源码做成可在 `crawler4j` 宿主里联调、安装、升级和交付的正式模块。

当前仓内基线如下：

- `crawler4j-sdk`：`0.4.0`
- `crawler4j` 宿主 / Core：`0.2.0`

这两个版本描述的是工具链和宿主能力，不是你的模块版本。模块自己的版本始终由你维护。

## 入门主线

按下面这条线走，不要把 DevLink、ZIP 安装、GitHub Release、宿主升级混成一团：

1. [快速开始](quickstart.md)
   从零创建一个标准模块项目，并跑通第一次自检。
2. [核心概念](core-concepts.md)
   看清模块、宿主、CLI、Hosted UI 和数据能力分别是谁的边界。
3. [模块结构](module-structure.md)
   搞清楚 `module.yaml`、`pyproject.toml`、`module_runtime.py`、`tasks/`、`workflows/` 各自负责什么。
4. [构建模块](build-modules.md)
   开始写 task、workflow、环境选择器和 Hosted UI 页面。
5. [UI 与数据表](ui-and-data-table.md)
   学会用 `Page / Section / Text / Button / DataTable` 组装页面，并把纯数据传给宿主。
6. [调试模块](debugging.md)
   用 DevLink、ATM 和 debugpy 在宿主里联调。
7. [交付模块](shipping.md)
   把源码收口成正式 ZIP 安装包，并在宿主里完成安装验收。

## 当前命令树怎么理解

CLI 已按“模块生命周期”收口，不再保留旧平铺命令。

| 命令组 | 解决什么问题 |
|---|---|
| `module` | 初始化模块项目，维护 `repo`、`version`、默认 workflow |
| `task` | 创建和列出 `tasks/` 下的原子任务 |
| `workflow` | 创建和列出 `workflows/`，并维护 `module.yaml.workflows` |
| `page` | 生成 Hosted UI 页面骨架，并维护 `ui_extension.pages[]` |
| `env-selector` | 在 `module_runtime.py` 里声明 `@env_selector(...)` |
| `config` | 维护 `module.yaml.config_defaults` |
| `package` | 构建和校验正式 ZIP 安装包 |
| `release` | 检查 GitHub Release 状态并发布正式 ZIP |
| `host` | 桥接宿主里的 DevLink、安装、升级和调试配置 |
| `check` | 运行 `structure / release / full` 三档 gate |

如果你只记一个命令序列，记这个：

```bash
uvx --from crawler4j-sdk crawler4j module init <module_name> --repo owner/<module_name>
uv run crawler4j task create <task_name>
uv run crawler4j workflow create <workflow_name>
uv run crawler4j page create <page_id>
uv run crawler4j check full
```

第一次联调优先停在这里。切到宿主环境后，再执行：

```bash
uv run crawler4j host devlink add /abs/path/to/module
```

跑通 DevLink 之后，回到模块工程环境构建升级包，再在宿主环境安装：

```bash
uv run crawler4j package build
uv run crawler4j host install preview dist/<module>-<version>.zip
```

这里的环境边界必须分清：

- `module / task / workflow / page / config / check / package / release` 默认在模块工程环境里执行
- `host *` 只能在已安装 `crawler4j` 宿主运行时的环境里执行，不能假设新初始化模块的虚拟环境天然可用

## Hosted UI 是当前唯一正式 UI 契约

模块 UI 现在只有一种正式写法：

- `module.yaml.ui_extension.pages[]` 只声明导航元信息：`id`、`label`、`icon`
- `module_runtime.py` 里的 `declare_ui(context)` 调用 `ui.declare_page(page_id=..., schema=...)`
- 页面 schema 只允许使用宿主提供的 `Page`、`Section`、`Text`、`Button`、`DataTable`
- `load_handler` / `query_handler` 返回纯结构化数据，由宿主统一渲染

这意味着：

- 模块不再导出 `PyQt6` 页面类
- 模块不再维护 `ui/` 目录
- 模块不再声明 `entry=core:page:*` 或 `entry=core:data_table:*`
- `ui.declare_data_table` / `ui.get_data_table` 已退出正式契约

如果你准备写页面，先接受这三个事实：

1. 宿主页通过 `ui.declare_page` 声明。
2. `DataTable` 只是页面内组件，不再是单独的宿主页面类型。
3. `declare_ui()`、`load_*_page()`、内联表格 `query_handler()` 当前都必须是同步函数。

## 三条版本与升级轨道

模块开发最容易混淆的，不是代码，而是版本和升级链路。下面三条轨道必须分开理解：

| 轨道 | 事实源 | 由谁维护 | 典型动作 |
|---|---|---|---|
| SDK / Core 包版本 | `crawler4j-sdk`、`crawler4j` 的 `pyproject.toml` | 平台维护者 | 升级 CLI、升级宿主、补 Hosted UI 和 Core 能力 |
| 模块版本 | 模块自己的 `module.yaml.version` 和 `pyproject.toml` | 模块作者 | `uv run crawler4j module set version <semver>` |
| 宿主里的模块升级 | 已安装模块的 `upgrade_source.repo` + GitHub Release ZIP | 模块作者发布，宿主执行升级 | `uv run crawler4j host upgrade check/preview/apply <module>` |

直接记住：

- `crawler4j-sdk 0.4.0` 不是你的模块版本。
- `module.yaml.version` 变化不会自动升级宿主本体。
- `host upgrade` 升的是“宿主里已安装的某个模块”，不是升级 SDK，也不是升级宿主程序。

## 交付边界

开发态和正式态边界很硬，不要混用：

| 场景 | 正式入口 |
|---|---|
| 本地联调 | 宿主环境里的 `host devlink add` + 宿主 ATM 调试 |
| 正式安装 | `package build` 产出的 ZIP |
| 远端发布 | `release publish` 上传 ZIP 到 GitHub Release |
| 已安装模块升级 | 宿主环境里的模块管理页或 `host upgrade` |

DevLink 只解决“本地源码联调”，不解决正式交付、安装和升级。
