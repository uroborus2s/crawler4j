# SDK 与 CLI 参考

`crawler4j-sdk` CLI 按“模块工程”“模块升级包”“宿主桥接”三层工作。模块开发者只要记住一条标准主线：先在模块项目里生成和校验，再用 DevLink/ATM 联调，最后产出 ZIP 升级包，并决定是否发布 GitHub Release、是否让宿主执行安装或升级。

## 命令入口

- 在模块项目里执行：`uv run crawler4j ...`
- 不安装、直接用最新 CLI：`uvx --from crawler4j-sdk crawler4j ...`
- 在 `crawler4j` Core 源码仓核对本地 CLI 实现：`uv run python -m crawler4j_sdk.cli.commands ...`

环境规则：

- `module / task / workflow / page / env-selector / config / check / package / release` 面向模块工程环境
- `host devlink / host debug / host install / host upgrade` 依赖 `crawler4j` 宿主运行时，只能在宿主环境执行

## 模块工程命令

| 命令组 | 关键命令 | 主要输出 | 典型用途 |
|---|---|---|---|
| `module` | `module init` `module show` `module set repo/version/default-workflow` | 模块根目录、`module.yaml`、`module_runtime.py` | 初始化模块，维护版本、升级源和默认 workflow |
| `task` | `task create` `task list` | `tasks/<name>.py` | 新建 `TaskScript` |
| `workflow` | `workflow create` `workflow list` | `workflows/<name>.py`、`module.yaml.workflows` | 新建编排并写回清单 |
| `page` | `page create` `page list` | `module.yaml.ui_extension.pages[]`、`module_runtime.py` | 注册 Hosted UI 页面骨架 |
| `env-selector` | `env-selector create` `env-selector list` | `module_runtime.py` | 追加 `@env_selector(...)` 选择器 |
| `config` | `config show` `config set ...` `config lint` | `module.yaml.config_defaults` | 维护模块级和 workflow 级默认配置 |
| `check` | `check structure` `check release` `check full` | 无 | 结构、发布前提和完整导入校验 |

`page create` 现在只生成页面骨架。需要表格页时，直接在该页面 schema 中加入 `DataTable` 组件。

## 发布与宿主桥接命令

| 命令组 | 关键命令 | 负责资产 | 正式边界 |
|---|---|---|---|
| `package` | `package build` `package verify` | `dist/<module>-<version>.zip` | 只负责模块升级包，不触碰宿主 |
| `release` | `release status` `check-remote` `publish` | GitHub Release 元数据和 ZIP 资产 | 只负责发布状态与远端分发，不安装 |
| `host devlink` | `add` `remove` `list` | 宿主 DevLink 注册表 | 只服务开发态源码联调 |
| `host debug` | `config` | `.vscode/launch.json` | 只生成 attach 配置，不直接拉起调试会话 |
| `host install` | `preview` `apply` | 安装来源（本地 ZIP / GitHub 仓库）与宿主安装流程 | 负责首次安装或本地 ZIP 验收 |
| `host upgrade` | `check` `preview` `apply` | 宿主已安装模块的升级状态 | 负责正式安装模块按 GitHub Release 升级 |

## `check` 的三档 gate

| 命令 | 作用 |
|---|---|
| `uv run crawler4j check structure` | 只看目录、清单、workflow 声明和页面入口格式 |
| `uv run crawler4j check release` | 在 `structure` 基础上继续检查版本、`upgrade_source.repo`、`config_defaults` 等发布前提 |
| `uv run crawler4j check full` | 在 `release` 基础上再尝试导入模块、task、workflow，并校验 Hosted UI 页面声明 |

`check full` 当前会直接校验：

- `declare_ui()` 是否为同步函数
- Hosted UI 是否真的通过 `ui.declare_page` 注册
- 页面 `load_handler` 是否存在且为同步函数
- 内联表格 `query_handler` 若声明，是否存在且为同步函数
- 顶层 `ui/` 目录是否仍然存在

## Hosted UI 页面脚手架

`uv run crawler4j page create <page_id>`

它会同时：

- 在 `module.yaml.ui_extension.pages[]` 里追加页面导航项
- 在 `module_runtime.py` 里补 `declare_ui()` 调用
- 生成 `build_<page>_page_schema()` 和 `load_<page>_page()` 骨架

如果你需要第二张、第三张页面，就继续执行更多次 `page create`。CLI 不再提供独立的数据表页面命令。

## `TaskContext` 与稳定 SDK 类型

模块开发者最常用的稳定类型如下：

| 名称 | 作用 |
|---|---|
| `TaskScript` | 原子任务基类 |
| `TaskFlow` | 工作流编排基类 |
| `ModuleAssembler` | 模块根入口装配器 |
| `TaskContext` | 运行上下文 |
| `TaskResult` | 标准结果对象 |
| `TaskSignal` / `TaskSignalAction` | 对 ATM 的流程控制信号 |
| `EnvAction` | 任务结束后的环境动作 |
| `env_selector` / `EnvSelectorInfo` | 环境选择器声明与元信息 |
| `ToolsCapability` / `ToolSpec` | Core 工具能力边界 |

`TaskContext` 里的关键字段：

| 字段 | 语义 |
|---|---|
| `config` / `get_config()` | 宿主持久化配置 |
| `runtime` | ATM、Debug 和宿主注入的运行态元数据 |
| `state` | 单次执行内共享内存 |
| `page` / `context` | Playwright 运行对象，可为空 |
| `tools` | 宿主注入的统一工具入口 |

和 Hosted UI、数据直接相关的工具名：

- `ui.declare_page`
- `ui.get_page`
- `db.declare_data_resource`
- `db.declare_db_view`
- `db.query_view`
- `db.list_records`
- `db.replace_records`
- `db.append_event`
- `db.query_events`
