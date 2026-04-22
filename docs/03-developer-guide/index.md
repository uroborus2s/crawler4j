# crawler4j 开发者指南

这份指南面向模块开发者。目标只有一个：把一个业务模块从本地源码做成可在 `crawler4j` 宿主里联调、安装、升级和交付的正式模块。

当前仓内基线如下：

- `crawler4j-sdk`：`0.4.0`
- `crawler4j` 宿主 / Core：`0.2.0`

这两个版本描述的是工具链和宿主能力，不是你的模块版本。模块自己的版本始终由你维护。

## 入门主线

按下面这条线走，不要把 DevLink、ZIP 安装、GitHub Release、宿主升级混成一团：

1. [快速开始](quickstart.md)
   从零创建一个标准模块项目，跑通当前 CLI 主命令树和第一次自检。
2. [核心概念](core-concepts.md)
   看清模块、宿主、CLI、Hosted UI V1、配置和运行态分别是谁的边界。
3. [模块结构](module-structure.md)
   搞清楚 `module.yaml`、`pyproject.toml`、`module_runtime.py`、`tasks/`、`workflows/` 各自负责什么。
4. [构建模块](build-modules.md)
   开始写 task、workflow、环境选择器、Hosted UI V1 页面和数据表。
5. [调试模块](debugging.md)
   用 DevLink、ATM 和 debugpy 在宿主里联调。
6. [交付模块](shipping.md)
   把源码收口成正式 ZIP 安装包，并在宿主里完成安装验收。

## 当前命令树怎么理解

CLI 已经按“模块生命周期”收口，不再是旧平铺命令。

| 命令组 | 解决什么问题 |
|---|---|
| `module` | 初始化模块项目，维护 `repo`、`version`、默认 workflow |
| `task` | 创建和列出 `tasks/` 下的原子任务 |
| `workflow` | 创建和列出 `workflows/`，并维护 `module.yaml.workflows` |
| `page` | 生成 Hosted UI V1 的 `core:page:<page_id>` 宿主页骨架 |
| `data-table` | 生成 Hosted UI V1 的 `core:data_table:<view_id>` 入口和声明函数 |
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
uv run crawler4j data-table create <view_id>
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

- `module / task / workflow / page / data-table / config / check / package / release` 默认在模块工程环境里执行
- `host *` 只能在已安装 `crawler4j` 宿主运行时的环境里执行，不能假设新初始化模块的虚拟环境天然可用

## Hosted UI V1 是当前唯一正式 UI 契约

模块 UI 现在只有两条正式入口：

- `core:page:<page_id>`
- `core:data_table:<view_id>`

它们都通过 `module_runtime.py -> declare_ui()` 声明，宿主统一渲染。模块不再导出 `PyQt6` 页面类，也不再维护 `ui/` 目录、`detail_menu`、`ui:*` 或其他旧入口。

如果你准备写页面，先接受这三个事实：

1. 宿主页通过 `ui.declare_page` 声明。
2. 托管数据表通过 `ui.declare_data_table` 声明。
3. `declare_ui()`、`load_*_page()`、数据表 handler 当前都必须是同步函数。

## 三条版本与升级轨道

模块开发最容易混淆的，不是代码，而是版本和升级链路。下面三条轨道必须分开理解：

| 轨道 | 事实源 | 由谁维护 | 典型动作 |
|---|---|---|---|
| SDK / Core 包版本 | `crawler4j-sdk`、`crawler4j` 的 `pyproject.toml` | 平台维护者 | 升级 CLI、升级宿主、补 Hosted UI V1 和 Core 能力 |
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

## 这份指南默认站在什么立场

- 模块是业务交付单元，不是二次平台。
- CLI 先生成骨架，再补业务代码。
- Hosted UI V1 是正式事实，不再兼容旧 UI 路径。
- 正式安装包是 ZIP，不是 wheel。
- `module.yaml`、`module_runtime.py`、`tasks/`、`workflows/` 是主要开发落点。

如果你是第一次写模块，直接从 [快速开始](quickstart.md) 开始。
如果你已经会写模块，只是需要查某个约束，优先看 [核心概念](core-concepts.md)、[模块结构](module-structure.md) 和 [构建模块](build-modules.md)。
