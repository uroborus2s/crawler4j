# SDK 与 CLI 参考

这一页只写当前命令树。默认使用最新 `crawler4j-sdk`，不要在命令里固定版本号。

## CLI 命令总表

| 命令 | 建议执行位置 | 会改哪些文件 | 用途 |
|---|---|---|---|
| `uvx --from crawler4j-sdk crawler4j module init <name> --repo owner/repo` | 目标模块的父目录 | 新建整个模块目录树 | 初始化标准模块项目 |
| `uv run crawler4j module show` | 模块根目录 | 无 | 查看版本、仓库、默认工作流、宿主页和数据表入口 |
| `uv run crawler4j task create <name>` | 模块根目录 | `tasks/<name>.py` | 新建 task |
| `uv run crawler4j workflow create <name>` | 模块根目录 | `workflows/<name>.py`、`module.yaml` | 新建 workflow 并注册到清单 |
| `uv run crawler4j page create <name>` | 模块根目录 | `module.yaml`、`module_runtime.py` | 新建 hosted page 并注册 `ui_extension.pages` |
| `uv run crawler4j data-table create <name>` | 模块根目录 | `module.yaml`、`module_runtime.py` | 注册 `core:data_table:<view_id>` 页并补 `declare_ui()` 骨架 |
| `uv run crawler4j env-selector create <name>` | 模块根目录 | `module_runtime.py` | 新建环境选择策略函数 |
| `uv run crawler4j config show` | 模块根目录 | 无 | 查看当前 `config_defaults` |
| `uv run crawler4j config set module --file <yaml>` | 模块根目录 | `module.yaml` | 写入模块级默认配置 |
| `uv run crawler4j config set workflow <workflow> --file <yaml>` | 模块根目录 | `module.yaml` | 写入 workflow 级默认配置 |
| `uv run crawler4j package build` | 模块根目录 | `dist/*.zip` | 构建正式安装包 |
| `uv run crawler4j package verify <archive>` | 模块根目录 | 无 | 校验现有 ZIP 结构 |
| `uv run crawler4j release status` | 模块根目录 | 无 | 查看本地发布就绪度 |
| `uv run crawler4j release check-remote` | 模块根目录 | 无 | 对比远端 GitHub Release 版本 |
| `uv run crawler4j release publish` | 模块根目录 | 可能新建或复用 `dist/*.zip` | 发布 GitHub Release 资产 |
| `uv run crawler4j host devlink add <module_root>` | 宿主环境或模块根目录 | 宿主 DevLink 状态 | 注册宿主开发链接 |
| `uv run crawler4j host devlink remove <module_name>` | 宿主环境或模块根目录 | 宿主 DevLink 状态 | 移除宿主开发链接 |
| `uv run crawler4j host devlink list` | 宿主环境或模块根目录 | 无 | 查看宿主 DevLink 列表 |
| `uv run crawler4j host install preview <source>` | 宿主环境或模块根目录 | 无 | 预检 ZIP / GitHub 源安装 |
| `uv run crawler4j host install apply <source>` | 宿主环境或模块根目录 | 宿主安装状态 | 真正安装 ZIP / GitHub 源 |
| `uv run crawler4j host upgrade check <module>` | 宿主环境 | 无 | 查看是否有新版本 |
| `uv run crawler4j host upgrade preview <module>` | 宿主环境 | 无 | 预览升级包 |
| `uv run crawler4j host upgrade apply <module>` | 宿主环境 | 宿主安装状态 | 真正安装升级包 |
| `uv run crawler4j host debug config` | 模块根目录 | `.vscode/launch.json` | 生成 VS Code attach 配置 |
| `uv run crawler4j check structure` | 模块根目录 | 无 | 做 hosted UI 骨架级校验 |
| `uv run crawler4j check release` | 模块根目录 | 无 | 做发布前提校验 |
| `uv run crawler4j check full` | 模块根目录 | 无 | 做完整导入和 hosted UI 契约校验 |

## 第一次交付时的最小安全顺序

```bash
uv run crawler4j check release
uv run crawler4j package build
uv run crawler4j package verify dist/<module>-<version>.zip
```

如果还要接到宿主里继续验收，再走：

- 本地宿主桥接安装：`uv run crawler4j host install preview <zip>`，确认无误后再执行 `uv run crawler4j host install apply <zip>`
- GitHub Release 发布：先执行 `uv run crawler4j release publish --dry-run`，确认无误后再执行 `uv run crawler4j release publish`

## `module`

| 命令 | 作用 |
|---|---|
| `uv run crawler4j module show` | 查看模块摘要 |
| `uv run crawler4j module set repo owner/repo` | 更新 `upgrade_source.repo` |
| `uv run crawler4j module set version 0.1.1` | 更新 `module.yaml.version` |
| `uv run crawler4j module set default-workflow hotel_sync` | 更新 `module_runtime.py` 里的默认 workflow |

## `task` / `workflow`

| 命令 | 作用 |
|---|---|
| `uv run crawler4j task create fetch_hotels` | 创建 task 文件 |
| `uv run crawler4j task list` | 列出 `tasks/` 下的 task |
| `uv run crawler4j workflow create hotel_sync --display-name "酒店同步"` | 创建 workflow 并写回 `module.yaml` |
| `uv run crawler4j workflow list` | 列出 `module.yaml.workflows` |

## `page` / `data-table` / `env-selector`

| 命令 | 作用 |
|---|---|
| `uv run crawler4j page create dashboard --display-name "Dashboard"` | 创建 hosted page 并注册 `core:page:dashboard` |
| `uv run crawler4j page list` | 列出 `ui_extension.pages` 中的宿主页入口 |
| `uv run crawler4j data-table create hotels --label "Hotels"` | 注册 `core:data_table:hotels` 并补 `module_runtime.py` helper |
| `uv run crawler4j data-table list` | 列出 `ui_extension.pages` 中的数据表入口 |
| `uv run crawler4j env-selector create random_ready --display-name "随机环境"` | 追加环境选择器函数 |
| `uv run crawler4j env-selector list` | 列出模块声明的环境选择器 |

补一条规则：

- `page create` 不再生成 `ui/` 页面类
- hosted page 骨架统一落在 `module_runtime.py`

## `config`

| 命令 | 作用 |
|---|---|
| `uv run crawler4j config show` | 打印当前 `config_defaults` |
| `uv run crawler4j config set module --file module.defaults.yaml` | 从 YAML 文件写模块级默认配置 |
| `uv run crawler4j config set workflow hotel_sync --file workflow.defaults.yaml` | 从 YAML 文件写 workflow 级默认配置 |
| `uv run crawler4j config lint` | 校验 `config_defaults` 结构和 workflow 引用 |

## `check`

| 命令 | 作用 |
|---|---|
| `uv run crawler4j check structure` | 只看骨架、清单和 `ui_extension.pages` 格式 |
| `uv run crawler4j check release` | 在 `structure` 基础上再看版本、仓库、默认配置等发布前提 |
| `uv run crawler4j check full` | 在 `release` 基础上再尝试导入模块、task、workflow，并校验 `declare_ui()` / `ui.declare_page` / `ui.declare_data_table` 契约 |

`check full` 当前会直接校验：

- `declare_ui()` 是否为同步函数
- hosted page 是否真的通过 `ui.declare_page` 注册
- 数据表是否真的通过 `ui.declare_data_table` 注册
- hosted page 的 `load_handler` 是否存在且为同步函数
- `declare_ui()` 是否误写 `db.append_event`

## `package` / `release`

| 命令 | 作用 |
|---|---|
| `uv run crawler4j package build` | 先做 `release` 级校验，再产出正式 ZIP |
| `uv run crawler4j package verify dist/hotel_demo-0.1.0.zip` | 校验已有 ZIP 的单根目录和清单结构 |
| `uv run crawler4j release status` | 查看本地是否具备发布条件 |
| `uv run crawler4j release check-remote` | 查看远端 GitHub Release 最新版本并对比本地版本 |
| `uv run crawler4j release publish --dry-run` | 先打印 `gh release` 将执行的命令 |
| `uv run crawler4j release publish --rebuild` | 发布前强制重新构建 ZIP，再调用 `gh release` |

## `host`

| 命令 | 作用 |
|---|---|
| `uv run crawler4j host devlink add /abs/path/to/module` | 把本地模块目录注册为宿主 DevLink |
| `uv run crawler4j host devlink remove hotel_demo` | 移除宿主中的 DevLink |
| `uv run crawler4j host devlink list` | 查看宿主当前 DevLink 列表 |
| `uv run crawler4j host install preview dist/hotel_demo-0.1.0.zip` | 只做本地 ZIP 安装预检 |
| `uv run crawler4j host install apply dist/hotel_demo-0.1.0.zip` | 直接把 ZIP 安装到宿主 |
| `uv run crawler4j host install preview owner/repo` | 预览 GitHub 源安装 |
| `uv run crawler4j host upgrade check hotel_demo` | 看已安装模块是否有新版本 |
| `uv run crawler4j host upgrade preview hotel_demo` | 下载并预览升级包，但不安装 |
| `uv run crawler4j host upgrade apply hotel_demo` | 下载并安装升级包 |
| `uv run crawler4j host debug config --port 5678` | 生成或更新 VS Code attach 配置 |

`host install <source>` 的 `source` 只认两种：

- 本地 ZIP 路径，例如 `dist/hotel_demo-0.1.0.zip`
- GitHub 仓库，例如 `owner/hotel_demo`

它不接受源码目录；源码目录要走 `host devlink add <module_root>`。

## `crawler4j_sdk` 公开导出

| 名称 | 类型 | 模块开发者怎么用 |
|---|---|---|
| `TaskScript` | 基类 | 写 task |
| `TaskFlow` | 基类 | 写 workflow |
| `ModuleAssembler` | 装配器 | 根薄壳使用，业务代码一般不直接调用 |
| `env_selector` | 装饰器 | 声明环境选择器 |
| `EnvSelectorInfo` | 数据类 | 选择器元数据，通常只读不手写 |
| `TaskContext` | 数据类 | 运行上下文 |
| `TaskResult` | 数据类 | 标准结果对象 |
| `TaskSignal` | 数据类 | 控制信号 |
| `TaskSignalAction` | 枚举 | 信号动作 |
| `EnvAction` | 枚举 | 环境后续动作 |
| `ToolSpec` | 数据类 | 工具元数据 |
| `ToolsCapability` | 协议 | `ctx.tools` 的接口 |
| `EnvCandidate` | 数据类 | 环境选择器入参 |

## `TaskContext`

### 主要字段

| 字段 | 说明 |
|---|---|
| `env_id` | 当前环境 ID |
| `task_name` | 当前任务名 |
| `config` | 宿主持久配置视图 |
| `page` | Playwright `Page`，可为空 |
| `context` | Playwright `BrowserContext`，可为空 |
| `logger` | 日志器 |
| `http` | HTTP 客户端 |
| `tools` | Core 注入工具能力，可为空 |
| `captured_data` | 采集结果快照 |
| `state` | 单次执行共享内存 |
| `runtime` | 当前执行期元数据 |

### 和 hosted UI 直接相关的工具名

- `ui.declare_page`
- `ui.declare_data_table`
- `db.list_records`
- `db.replace_records`
- `db.append_event`
- `db.query_events`

如果你只记一个结论：

- hosted UI 统一通过 `module_runtime.py` 的同步声明函数接入，不再导出模块侧页面类。
