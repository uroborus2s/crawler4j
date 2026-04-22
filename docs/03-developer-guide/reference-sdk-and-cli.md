# SDK 与 CLI 参考

`crawler4j-sdk` CLI 按“模块工程”“模块升级包”“宿主桥接”三层工作。模块开发者只要记住一条标准主线：先在模块项目里生成和校验，再用 DevLink/ATM 联调，最后产出 ZIP 升级包，并决定是否发布 GitHub Release、是否让宿主执行安装或升级。

## 命令入口

- 在模块项目里执行：`uv run crawler4j ...`
- 不安装、直接用最新 CLI：`uvx --from crawler4j-sdk crawler4j ...`
- 在 `crawler4j` Core 源码仓核对本地 CLI 实现：`uv run python -m crawler4j_sdk.cli.commands ...`

这份页面默认以最新发布的 `crawler4j-sdk` 命令树为准，不再在示例里固定历史版本号。

先补一条环境规则：

- `module / task / workflow / page / data-table / env-selector / config / check / package / release` 面向模块工程环境
- `host devlink / host debug / host install / host upgrade` 依赖 `crawler4j` 宿主运行时，只能在宿主环境执行

## 运行与交付主线

1. `module init` 创建标准模块工程
2. `task` / `workflow` / `page` / `data-table` / `env-selector` / `config` 生成模块内容
3. `check` 作为本地 gate
4. 切到宿主环境，`host devlink add` 把源码目录接到宿主，在 ATM 执行一次或调试
5. 回到模块工程环境，`package build` + `package verify` 产出模块升级包
6. 回到模块工程环境，`release` 查看发布状态、检查远端版本或发布 GitHub Release 资产
7. 切到宿主环境，`host install` 让宿主安装本地 ZIP 或 GitHub 仓库
8. 切到宿主环境，`host upgrade` 让已安装模块按 GitHub Release 升级

这条主线里，CLI 既是模块工程入口，也是宿主桥接入口，但不同命令组负责的资产并不一样。

## 责任边界

| 层级 | 命令组 | 负责什么 | 不负责什么 |
|---|---|---|---|
| 模块工程入口 | `module` `task` `workflow` `page` `data-table` `env-selector` `config` `check` | 生成和校验 `module.yaml`、`module_runtime.py`、`tasks/`、`workflows/` 等模块源码与清单 | 不直接安装到宿主，不发布 Release |
| 模块升级包与发布资产 | `package` `release` | 构建单根目录 ZIP，检查本地发布就绪度，发布 GitHub Release 资产 | 不修改宿主安装状态 |
| 宿主桥接入口 | `host devlink` `host debug` `host install` `host upgrade` | 让宿主加载源码、生成调试配置、安装正式包、执行升级 | 不构建 ZIP，不修改模块源码结构 |

三个边界要分清：

- 模块升级包是 `package build` 产出的 ZIP。
- GitHub Release 是模块升级包的远端分发面。
- `host install` / `host upgrade` 是宿主消费升级包的入口，不是打包命令。

## 模块工程命令

| 命令组 | 关键命令 | 主要输出 | 典型用途 |
|---|---|---|---|
| `module` | `module init` `module show` `module set repo/version/default-workflow` | 模块根目录、`module.yaml`、`module_runtime.py` | 初始化模块，维护版本、升级源和默认 workflow |
| `task` | `task create` `task list` | `tasks/<name>.py` | 新建 `TaskScript` |
| `workflow` | `workflow create` `workflow list` | `workflows/<name>.py`、`module.yaml.workflows` | 新建编排并写回清单 |
| `page` | `page create` `page list` | `module.yaml.ui_extension.pages[]`、`module_runtime.py` | 注册 Hosted UI V1 宿主页 |
| `data-table` | `data-table create` `data-table list` | `module.yaml.ui_extension.pages[]`、`module_runtime.py` | 注册 `core:data_table:<view_id>` |
| `env-selector` | `env-selector create` `env-selector list` | `module_runtime.py` | 追加 `@env_selector(...)` 选择器 |
| `config` | `config show` `config set ...` `config lint` | `module.yaml.config_defaults` | 维护模块级和 workflow 级默认配置 |
| `check` | `check structure` `check release` `check full` | 无 | 结构、发布前提和完整导入校验 |

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
| `uv run crawler4j check structure` | 只看目录、清单、workflow 声明和 UI 入口格式 |
| `uv run crawler4j check release` | 在 `structure` 基础上继续检查版本、`upgrade_source.repo`、`config_defaults` 等发布前提 |
| `uv run crawler4j check full` | 在 `release` 基础上再尝试导入模块、task、workflow，并校验 Hosted UI V1 与数据表声明 |

`check full` 当前会直接校验：

- `declare_ui()` 是否为同步函数
- Hosted UI 是否真的通过 `ui.declare_page` 注册
- 数据表是否真的通过 `ui.declare_data_table` 注册
- Hosted UI 的 `load_handler` 是否存在且为同步函数

补一条脚手架刷新语义：

- `uv run crawler4j page create <page_id> --force` 会同步刷新 `module.yaml.ui_extension.pages[]` 和 `module_runtime.py` 里该页面对应的 helper block；如果页面已存在，不会只改 manifest 而留下旧 `build_*_page_schema` / `load_*_page` 实现。

## 模块升级包、安装和升级的边界

### 模块升级包

`uv run crawler4j package build`

- 在当前模块根目录构建单根目录 ZIP
- 产物默认写到 `dist/<module>-<version>.zip`
- 这是正式模块交付物，也是后续 GitHub Release 资产的来源

`uv run crawler4j package verify dist/<module>-<version>.zip`

- 校验 ZIP 结构、`module.yaml` 和发布前提
- 适合作为交付前最后一道本地结构检查

### GitHub Release

`uv run crawler4j release ...`

- `status`：看本地是否具备发布条件
- `check-remote`：对比本地版本和 GitHub Release 最新版本
- `publish`：把 ZIP 资产发布到 GitHub Release

`release publish` 只负责上传资产，不会改动宿主里任何已安装模块。正式可安装的 Release 还必须满足：每个 Release 只有一个 ZIP 资产，ZIP 内 `module.yaml.version` 与 Release 版本一致，且 `module.yaml.upgrade_source.repo` 与目标仓库一致。

### 宿主安装

`uv run crawler4j host install preview|apply <source>`

`host install` 只接受两类输入：

- 本地 ZIP 路径
- GitHub 来源：`owner/repo`、完整仓库 URL，或完整 GitHub Release URL

它不接受源码目录；源码目录必须走 `uv run crawler4j host devlink add <module_root>`。本地 ZIP 场景下，`preview` 和 `apply` 都支持 `--skip-remote-check`。

补一条实际语义：

- 传 GitHub Release URL 时，CLI 会先把它归一化成对应仓库，再按该仓库的最新 Release 安装
- 如果你要表达稳定安装源，正式事实源仍然是 `module.yaml.upgrade_source.repo` 里的 `owner/repo`

### 宿主升级

`uv run crawler4j host upgrade check|preview|apply <module_name>`

`host upgrade` 的前提是：模块已经以正式安装态存在于宿主中，它的 `upgrade_source.repo` 能指向满足约束的 GitHub Release，并且模块当前空闲。`check` 只看远端版本；`preview` 和 `apply` 都会在模块有运行中任务时被拒绝。它不是 DevLink 命令，也不是 ZIP 打包命令。

## 开发态与正式态的推荐顺序

### 开发态联调

以下命令默认在宿主环境执行：

```bash
uv run crawler4j host devlink add /abs/path/to/module
uv run crawler4j host debug config
```

进入宿主环境前，应先在模块工程环境跑完：

```bash
uv run crawler4j check full
```

然后回到宿主里的 ATM 创建作业，先点 `执行一次`，需要断点时再点 `调试`。

### 正式交付

```bash
uv run crawler4j check release
uv run crawler4j package build
uv run crawler4j package verify dist/<module>-<version>.zip
uv run crawler4j release publish --dry-run
```

### 宿主安装与升级验收

以下命令默认在宿主环境执行：

本地 ZIP 验收或首次安装：

```bash
uv run crawler4j host install preview dist/<module>-<version>.zip
uv run crawler4j host install apply dist/<module>-<version>.zip
uv run crawler4j host install apply dist/<module>-<version>.zip --skip-remote-check
```

正式安装后的升级验收：

```bash
uv run crawler4j host upgrade check <module_name>
uv run crawler4j host upgrade preview <module_name>
uv run crawler4j host upgrade apply <module_name>
```

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

和 Hosted UI V1、数据表直接相关的工具名：

- `ui.declare_page`
- `ui.get_page`
- `ui.declare_data_table`
- `ui.get_data_table`
- `db.list_records`
- `db.replace_records`
- `db.append_event`
- `db.query_events`

如果只记一个结论：SDK CLI 负责把模块工程、升级包和宿主桥接拆成清晰的命令组；模块开发者不要把 `package`、`release`、`host install`、`host upgrade` 混成同一层动作。
