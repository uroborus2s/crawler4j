# Crawler4j SDK

`crawler4j-sdk` 0.4.x 只面向 `core-native-v2` 模块开发，不兼容 0.3.x 的 `TaskSpec` / `WorkflowSpec` / `EnvSelectorSpec` 模式。

运行时 owner 只有 Core。模块运行时代码只依赖 `crawler4j-contracts`，`crawler4j-sdk` 只作为开发依赖提供 CLI、脚手架、扫描、校验、manifest lock、打包与发布辅助。

## 包边界

模块运行时代码从 `crawler4j-contracts` 导入：

- `TaskContext`
- `TaskResult`
- `TaskOutcome`
- `WorkflowLifecycleInfo`
- `interface`
- `component`
- `workflow`
- `object_param`
- `object_inject`
- `page`
- `page_action`
- `ui_action`
- `data_table`
- `data_view`
- `env_candidates`
- `env_cleanup_candidates`
- `EnvCandidates`
- `crawler4j_contracts.hosted_ui` 中的 Hosted UI schema/helper

`TaskSignal`、`TaskSignalAction`、`EnvAction` 已退出模块运行时代码入口；SDK scanner 会阻断模块导入这些名字。`crawler4j-sdk` 不导出运行时 owner、`TaskScript`、`TaskFlow`、`ModuleAssembler`、旧环境选择器或资源池 helper。

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
├── candidates/
├── cleanups/
└── pages/
```

固定扫描规则：

- `interfaces/*.py` 声明 `@interface`
- `objects/*.py` 声明 `@component`
- `workflows/*.py` 声明 `@workflow`
- `tasks/*.py` 声明 workflow/component 调用的 `@page_action`
- `data/*.py` 声明 `@data_table` / `@data_view`
- `candidates/*.py` 声明 `@env_candidates`
- `cleanups/*.py` 声明 `@env_cleanup_candidates`
- `pages/*.py` 或 `pages/<group>/*.py` 声明 `@page(...)` 与 Hosted UI 用户操作 `@ui_action`

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
uv run crawler4j ui-action create create_account_from_ui
uv run crawler4j data table create accounts
uv run crawler4j data view create account_overview --source accounts
uv run crawler4j candidate create ready_accounts
uv run crawler4j cleanup create unused_accounts
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

workflow 和 component 可选实现 `setup(ctx, workflow)` 做运行前准备，可选实现 `cleanup(ctx, outcome)` 释放资源、打印终态日志或写审计事件。Core 会在对象图构造完成后按 component 组合顺序再到 workflow 调用 `setup`，然后调用 `workflow.run(ctx)`；终态时按 component 依赖反向顺序再到 workflow 调用 `cleanup`。`workflow` 是当前 workflow 元信息，`outcome.workflow` 保存同一份信息，`outcome.status` 只可能是 `succeeded`、`failed`、`timed_out` 或 `cancelled`。旧 `aclose()` / `close()` 不再是对象生命周期契约，`check full` 会阻断这两个旧方法名。

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

SDK 仍保留 `crawler4j_sdk.context.DefaultHttpClient` 作为本地开发辅助。模块运行时代码不得依赖 `crawler4j-sdk`；数据库唯一入口为 `ctx.db`。标准页面交互走 `ctx.tools.call("browser.*", ...)`，例如 `browser.goto`、`browser.click`、`browser.type`、`browser.drag`、`browser.scroll`；`ctx.page` 主要保留给读取标题、HTML、locator 状态或宿主尚未抽象的浏览器能力。环境选择统一写成 `candidates/` 下的 `@env_candidates` 同步纯函数，可以直接返回 env id 列表，也可以返回 `EnvCandidates` 链式查询；不要维护资源池同步快照。模块账号或业务表若要认领环境，必须在 `@data_table(..., env_binding_field="env_id")` 中声明绑定字段。批量环境清理候选写在 `cleanups/` 下的 `@env_cleanup_candidates` 同步纯函数中，复用同一个 `EnvCandidates` DSL，但不复用运行候选入口；模块只声明已绑定且业务上可丢弃的 env id，宿主负责预览、确认、二次校验和删除。单次 workflow 结束、失败、超时或被用户中止后的环境统一由宿主回收，模块不得发送环境处置指令。
