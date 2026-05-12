# crawler4j-contracts

`crawler4j-contracts` 是 Core、SDK 与外部模块共享的稳定运行时契约包，当前源码版本基线为 `0.4.0`。

## 包含内容

- 提供 `TaskContext` / `TaskResult` / `TaskOutcome` / `WorkflowLifecycleInfo` 等模块运行和生命周期契约
- 提供 `ToolsCapability` / `ToolSpec` / `HttpClient` 等宿主扩展能力契约
- 提供 `DatabaseClient`，模块数据唯一正式入口为 `TaskContext.db`
- 提供 Hosted UI 页面 schema 类型 `PageSchema` 及组件/action/CRUD TypedDict，并提供表格查询契约 `HostedDataTableQuery`、泛型 `HostedDataTableQueryResult[RowT]`、`HostedDataTableSortSpec` 与 `QueryCallback`，`HostedDataTableQuery.to_query_callback(...)` 可把搜索、排序、分页和导航参数转换为 `ctx.db.from_(...)` 查询回调，`to_count_query_callback(...)` 可生成不带排序和分页的 count 过滤回调；`query_handler` 不接收 `table_id`，返回值不使用普通 `dict`
- 提供 `core-native-v2` 装饰器：`@interface`、`@component`、`@workflow`、`@page`、`@page_action`、`@ui_action`、`@data_table`、`@data_view`、`@env_candidates`、`@env_cleanup_candidates`
- 提供 `EnvCandidates` 链式环境候选查询 DSL，支持 `filter()`、`exclude()`、`intersect()`、`union()`、`minus()`、`order()`、`limit()` 与 `list(ctx)`
- 提供对象装配注解 helper：`object_param(...)`、`object_inject(...)`。它们可用于 component 类属性或 `__init__` 参数注解，最终归一为 `ParameterSpec` / `InjectSpec`
- `object_param(...)` 支持 `string/text/integer/number/boolean/enum/array/object/json/date/datetime/time/url/path/secret`，并可通过 `schema` / `item_schema` 描述 `object` 与 `array` 的结构；`Literal[...]`、`list[T]`、`dict[str, T]`、`Optional[T]`、`datetime` 类型和 `pathlib.Path` 可被运行时注解推断
- `TaskSpec` / `WorkflowSpec` / `EnvSelectorSpec` / `PageSpec` 已从 contracts 包移除；0.4.x 模块只能使用 v2 装饰器声明运行能力和页面
- 不内置调度器、执行器、环境管理器、HTTP 客户端或其他第三方宿主适配器
- `TaskSignal` / `TaskSignalAction` / `EnvAction` 已从 contracts 移除；模块代码不得导入或发送这些流程/环境控制对象
- `TaskContext` 只保留少量与契约紧耦合的辅助方法（如等待、停止状态记录、`run_page_action` 执行器入口）；截图等浏览器副作用由 Core 或宿主工具提供
- `TaskContext.http` 为可选注入能力；contracts 包本身不再内置 aiohttp 风格默认实现
- 供 `crawler4j`、`crawler4j-sdk` 与标准模块共同依赖

模块运行时代码只应依赖本包。`crawler4j-sdk` 只作为开发依赖提供 CLI、脚手架、校验和打包辅助，不提供运行时 owner、`TaskScript` / `TaskFlow`、旧环境选择器或资源池 helper。

Hosted UI 用户按钮、CRUD handler 和表单提交使用 `@ui_action`；Hosted UI schema 不接受 `Button.action.type="page_action"`。DataTable CRUD handler 的 create/update/delete 入参必须是确定签名，`payload` 应使用模块自定义 `TypedDict` / dataclass 风格输入类型，不要用 `Mapping[str, Any]` 或裸 `dict`。浏览器页面自动化使用 `@page_action`，并由 workflow/component 通过 `ctx.run_page_action(...)` 调用。`@page_action` 不是内部拆分单元，不能在另一个 `@page_action` 中嵌套调用。

非数据库类宿主能力继续通过 `TaskContext.tools` 调用。环境选择统一声明为 `candidates/*.py` 中的 `@env_candidates` 同步纯函数，账号状态、黑号、注册时间和会员等级等过滤由候选函数实时读取模块数据表完成，不使用资源池同步快照。需要被宿主识别为“已认领环境”的业务表必须通过 `@data_table(..., env_binding_field="env_id")` 声明绑定字段。批量环境清理候选统一声明为 `cleanups/*.py` 中的 `@env_cleanup_candidates` 同步纯函数，复用 `EnvCandidates` 查询 DSL，但只表达已绑定且业务上可丢弃的 env id，实际删除由宿主环境管理页预览确认和安全校验后执行；模块 workflow 不能通过运行结果指定环境处置。workflow/component 可选实现 `setup(ctx, workflow)` 做运行前准备，可选实现 `cleanup(ctx, outcome)` 做终态收尾；`workflow` 为当前 workflow 元信息，`outcome.workflow` 保存同一份信息，`outcome.status` 为 `succeeded`、`failed`、`timed_out` 或 `cancelled`。
