# SDK 与 CLI 参考

`crawler4j-sdk` CLI 现在围绕一套固定模块结构工作：`tasks/`、`workflows/`、`pages/`、`hooks/`、`env_selectors/`。模块 UI、Hook、环境选择器都不再直接写进 `module_runtime.py`。

## 命令入口

- 在模块项目里执行：`uv run crawler4j ...`
- 不安装、直接使用最新 CLI：`uvx --from crawler4j-sdk crawler4j ...`
- 在 Core 源码仓核对本地 CLI：`uv run python -m crawler4j_sdk.cli.commands ...`

## 模块工程命令

| 命令组 | 关键命令 | 主要输出 |
|---|---|---|
| `module` | `module init` `module show` `module set repo/version/default-workflow` | 模块根目录、`module.yaml`、`module_runtime.py` |
| `task` | `task create` `task list` | `tasks/<name>.py` |
| `workflow` | `workflow create` `workflow list` | `workflows/<name>.py`、`module.yaml.workflows` |
| `page` | `page create` `page list` | `pages/<page>.py`、`module.yaml.ui_extension.pages[]` |
| `hook` | `hook create` `hook list` | `hooks/<hook>.py` |
| `env-selector` | `env-selector create` `env-selector list` | `env_selectors/<name>.py` |
| `config` | `config show` `config set ...` `config lint` | `module.yaml.config_defaults` |
| `check` | `check structure` `check release` `check full` | 无 |

## `module init`

```bash
uv run crawler4j module init hotel_demo --repo your-org/hotel_demo
```

默认会生成：

- `module.yaml`
- `module_runtime.py`
- `tasks/`
- `workflows/`
- `pages/`
- `hooks/`
- `env_selectors/`
- `tests/`

其中：

- `module_runtime.py` 是宿主接缝薄壳
- `pages/`、`hooks/`、`env_selectors/` 是正式源码目录

## `page create`

```bash
uv run crawler4j page create dashboard
uv run crawler4j page create accounts --display-name "账号列表"
```

它会同时：

- 创建 `pages/<page_id>.py`
- 把页面入口写入 `module.yaml.ui_extension.pages[]`

它不会再去拼接 `module_runtime.py` 里的大段页面逻辑；页面装配代码固定留在 `pages/<page_id>.py`。

页面文件默认包含：

- `declare_<page_id>_page`
- `build_<page_id>_page_schema`
- `load_<page_id>_page`

如果页面里要用 `DataTable`，直接在这个页面 schema 里补上组件与 `query_handler`。

## `hook create`

```bash
uv run crawler4j hook create on_cleanup
uv run crawler4j hook create on_success --force
```

正式支持的 Hook 名有：

- `prepare_env`
- `init_env`
- `before_run`
- `on_success`
- `on_failure`
- `on_timeout`
- `on_cleanup`

命令会在 `hooks/` 下创建对应文件。`--force` 用于重建脚手架。

## `env-selector create`

```bash
uv run crawler4j env-selector create pick_ready
uv run crawler4j env-selector create return_none --force
```

命令会在 `env_selectors/` 下创建一个 `@env_selector(...)` 文件，并由 `module_runtime.py` 自动暴露给宿主。

## `check` 的三档 gate

| 命令 | 作用 |
|---|---|
| `uv run crawler4j check structure` | 校验目录、清单、工作流声明、`pages/hooks/env_selectors` 结构 |
| `uv run crawler4j check release` | 在 `structure` 基础上继续校验版本、`upgrade_source`、`config_defaults` |
| `uv run crawler4j check full` | 在 `release` 基础上再导入模块、校验 `declare_ui()`、页面 `load_handler` 和内联表格 `query_handler` |

`check full` 当前会直接检查：

- `declare_ui()` 是否为同步函数
- `module.yaml.ui_extension.pages[]` 声明的页面是否真的被 `ui.declare_page` 注册
- 页面 `load_handler` 是否存在且为同步函数
- 页面内联表格 `query_handler` 若声明，是否存在且为同步函数

## Hosted UI 的正式边界

当前只保留一种 Hosted UI 协议：

- `module.yaml.ui_extension.pages[]` 只放导航元信息
- 页面 schema 和 handler 放在 `pages/*.py`
- `module_runtime.py` 只做薄壳导出
- 宿主只负责纯 UI 渲染和通用能力

如果是同一菜单项下的详情态切换，继续使用同一个 `page_id`，通过 `open_page(page_id, params)` 和 `load_handler(..., params)` 处理，不需要额外创建第二套 UI 入口。
