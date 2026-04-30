# Crawler4j SDK

`crawler4j-sdk` 0.4.x 只面向 `core-native-v2` 模块开发，不兼容 0.3.x 的 `TaskSpec` / `WorkflowSpec` / `EnvSelectorSpec` 模式。

运行时 owner 只有 Core。模块运行时代码只依赖 `crawler4j-contracts`，`crawler4j-sdk` 只作为开发依赖提供 CLI、脚手架、扫描、校验、manifest lock、打包与发布辅助。

## 包边界

模块运行时代码从 `crawler4j-contracts` 导入：

- `TaskContext`
- `TaskResult`
- `TaskSignal`
- `EnvAction`
- `interface`
- `component`
- `workflow`
- `object_param`
- `object_inject`
- `page`
- `page_action`
- `data_table`
- `data_query`
- `crawler4j_contracts.hosted_ui` 中的 Hosted UI schema/helper

`crawler4j-sdk` 不导出运行时 owner、`TaskScript`、`TaskFlow`、`ModuleAssembler` 或旧资源池 helper。

## 核心协议

模块必须声明：

```yaml
name: demo_module
runtime_api: core-native-v2
version: 0.1.0
upgrade_source:
  type: github_release
  repo: example/demo_module
  allow_prerelease: false
config_defaults:
  module: {}
```

`module.yaml` 不再声明 `default_workflow`、`workflows`、`data`、`interfaces`、`objects`、`tasks` 或 `ui_extension`。这些能力都由代码装饰器声明并由 SDK/Core 扫描。

## 模块目录

```text
demo_module/
├── .crawler4j/
│   └── manifest.lock.json
├── __init__.py
├── module.yaml
├── pyproject.toml
├── interfaces/
├── objects/
├── workflows/
├── tasks/
├── data/
└── pages/
```

固定扫描规则：

- `interfaces/*.py` 声明 `@interface`
- `objects/*.py` 声明 `@component`
- `workflows/*.py` 声明 `@workflow`
- `tasks/*.py` 声明 `@page_action`
- `data/*.py` 声明 `@data_table` / `@data_query`
- `pages/*.py` 或 `pages/<group>/*.py` 声明 `@page(...)`

## CLI

```bash
uvx --from crawler4j-sdk crawler4j module init
```

交互式输入模块名和升级源仓库，其他选项使用默认值。脚本化场景仍支持完整参数：

```bash
uvx --from crawler4j-sdk crawler4j module init demo_module --repo example/demo_module --runtime-api core-native-v2

uv run crawler4j interface create labor
uv run crawler4j component create api_labor --implements labor
uv run crawler4j workflow create main_workflow
uv run crawler4j page-action create open_login_page
uv run crawler4j data table create accounts
uv run crawler4j data query create get_account_by_id --source accounts
uv run crawler4j page create dashboard
uv run crawler4j manifest lock
uv run crawler4j check full
uv run crawler4j package build
```

`check full` 会拒绝运行时代码 import `crawler4j-sdk`、旧 `ctx.tools.call("db.*")`、`ctx.captured_data`、旧 manifest 区段，以及 v2 装饰器扫描中的重复名、缺失注入目标、循环依赖和数据契约错误。

SDK scanner 同时支持两类对象装配声明：

- 传统装饰器参数：`@component(inject=[...], parameters=[...])`、`@workflow(inject=[...])`
- 注解 helper：类属性或 `__init__` 参数上的 `Annotated[..., object_param(...)]` / `Annotated[..., object_inject(...)]`

两类声明都会进入同一份 `.crawler4j/manifest.lock.json` 元数据；不要在同一对象里用两个入口重复声明同名参数或同名注入。

`object_param(...)` 当前支持 `string/text/integer/number/boolean/enum/array/object/json/date/datetime/time/url/path/secret`。SDK 静态扫描可从 `str/int/float/bool`、`Literal[...]`、`list[T]`、`dict[str, T]`、`Optional[T]` / `T | None`、`datetime.date/datetime/time`、`pathlib.Path` 推断类型，并会把 `schema` / `item_schema` 写入 manifest lock。

## 运行期依赖

模块自己的 `pyproject.toml` 应该是：

```toml
[project]
dependencies = [
  "crawler4j-contracts>=0.4.0,<0.5.0",
]

[dependency-groups]
dev = [
  "crawler4j-sdk>=0.4.0,<0.5.0",
  "pytest>=9.0.2",
  "pytest-asyncio>=1.3.0",
]
```

CLI 脚手架生成的 `pyproject.toml` 会默认写入同样的兼容范围。

## 开发辅助

SDK 仍保留 `crawler4j_sdk.context.DefaultHttpClient` 作为本地开发辅助。模块运行时代码不得依赖 `crawler4j-sdk`；资源池等非数据库宿主能力继续通过 `ctx.tools.has_tool(...)` / `ctx.tools.call(...)` 调用，数据库唯一入口为 `ctx.db`。
