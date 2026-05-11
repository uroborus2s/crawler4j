# 常见问题

> 版本绑定：本文只排查 0.4.x SDK / Contracts 与 Core 0.4.0。0.4.x 工具链不会兼容 0.3.x 命令、模板或开发模式。

这页按 `core-native-v2` 主线排查。先判断问题在装饰器扫描、对象装配、数据契约、页面，还是交付安装。

## 最短定位顺序

1. CLI 不通过：跑 `uv run crawler4j check full`
2. Core 拒绝加载：看 `module.yaml.runtime_api`
3. 运行模板没有对象树：看 workflow inject 和 component implements
4. workflow 构造失败：看构造函数参数名
5. 数据扫描失败：看保留字段诊断
6. 页面不出来：看 `pages/*.py`、`@page(...)` 和 manifest lock
7. 安装失败：看 ZIP 结构和 manifest lock

## Core 拒绝加载模块

确认：

- `module.yaml.runtime_api` 存在且值为 `core-native-v2`
- `.crawler4j/manifest.lock.json` 存在
- lock 没有过期
- DevLink 注册诊断通过

0.4.0 不会把 v0.3.0 的 `TaskSpec/WorkflowSpec/module.yaml.data` 当成新协议自动运行。

## `check full` 不通过

优先确认：

- 当前目录下有 `module.yaml`
- `module.yaml.version` 是合法语义化版本
- `module.yaml.upgrade_source.repo` 是合法 `owner/repo`
- 装饰器名称使用 snake_case
- interface、component、workflow、data table、data view 名称唯一
- workflow inject 目标存在
- component inject 目标存在
- 对象图无环
- workflow 没有 `parameters`
- `module.yaml` 没有 v2 禁止字段
- 运行时代码没有 import `crawler4j-sdk`

处理方式：

- 先修扫描和对象图，再继续写业务逻辑
- 不要带着 gate 错误去跑宿主联调

## 运行模板看不到参数

这是 0.4.0 的正常变化。workflow 没有参数。

如果你需要配置 API 地址、超时、账号策略等普通值：

1. 找到真正需要这个值的 component
2. 在 `@component(parameters=[...])` 声明，或用 `Annotated[..., object_param(...)]` 写到 component 类属性 / `__init__` 参数
3. 让运行模板在对象节点下渲染参数表单

不要恢复 `module.yaml.workflows[].parameters[]`。

## 对象实现无法选择

确认：

1. 是否声明了 `@interface(name="labor")`
2. 是否至少有一个 `@component(implements="labor")`
3. component 名称是否唯一
4. 运行模板绑定是否引用了真实 component

如果只有一个实现，UI 可以默认选择并折叠。多个实现才需要下拉选择。

## workflow 构造失败

确认：

- `inject.name` 与 `__init__` 参数名一致
- component `parameters[].name` 与 `__init__` 参数名一致
- 使用注解 helper 时，类属性名或 `__init__` 参数名会作为默认 `inject.name` / parameter name
- 必填参数已在运行模板填写
- workflow 构造函数没有普通业务参数
- 构造函数里没有直接依赖 `ctx`

需要 `ctx` 时，把它传给 `run(ctx)` 或业务方法。

## 数据字段被阻断

如果错误提示命中下面字段，改字段名：

- `created_at`
- `updated_at`
- `create_at`
- `update_at`

这些是宿主保留或混淆字段。使用业务名：

- `source_created_at`
- `business_updated_at`

同时检查：

- `@data_table.schema`
- 类注解字段
- indexes
- `@data_view.schema`

## 表格没有数据

确认：

1. `@data_table(name="accounts", storage_mode=...)` 是否被扫描进 lock；旧快照表需要显式 `managed_dataset`
2. `DataTable.data_source.resource_id` 是否写 `accounts`
3. handler 是否通过 `ctx.db.from_("accounts")` 查询
4. 只读视图是否通过 `ctx.db.from_("view_id")` 调用，且视图来源是 `custom_table`
5. 运行时代码是否还在走 `ctx.tools.call("db.*")`

## 页面是空白

确认：

1. 页面文件是否使用 `@page(...)`
2. `@page.name` 是否唯一
3. `@page.schema` 顶层是否是 `Page`
4. 被 `@page` 装饰的 `load_handler` 是否存在且签名正确
5. 表格 `query_handler` 是否存在且签名为 `context, HostedDataTableQuery`，返回 `HostedDataTableQueryResult`
6. 页面动作是否引用已扫描的 `@page_action`

## 安装或升级失败

确认：

1. ZIP 是否只有一个根目录
2. 根目录是否有 `module.yaml`
3. 根目录是否有 `.crawler4j/manifest.lock.json`
4. `runtime_api` 是否为 `core-native-v2`
5. lock 是否与源码一致
6. ZIP 是否混入 v0.3.0 旧结构

必要时先执行：

```bash
uv run crawler4j package verify dist/<module>-<version>.zip
```

桌面宿主安装失败弹窗会展示 `message / stage / hint / traceback`。macOS 持久化日志默认在：

```text
~/Library/Application Support/Crawler4j/logs/crawler4j.log
```
