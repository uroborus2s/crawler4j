# crawler4j-contracts

`crawler4j-contracts` 是 Core、SDK 与外部模块共享的稳定运行时契约包，当前源码版本基线为 `0.4.0`。

## 包含内容

- 提供 `TaskContext` / `TaskResult` 等契约类型
- 提供 `TaskSignal` / `TaskSignalAction` / `EnvAction` 等流程控制信号
- 提供 `ToolsCapability` / `ToolSpec` / `HttpClient` 等宿主扩展能力契约
- 提供 `DatabaseClient`，模块数据唯一正式入口为 `TaskContext.db`
- 提供 `core-native-v2` 装饰器：`@interface`、`@component`、`@workflow`、`@page`、`@page_action`、`@data_table`、`@data_query`、`@env_candidates`、`@env_cleanup_candidates`
- 提供 `EnvCandidates` 链式环境候选查询 DSL，支持 `filter()`、`exclude()`、`intersect()`、`union()`、`minus()`、`order()`、`limit()` 与 `list(ctx)`
- 提供对象装配注解 helper：`object_param(...)`、`object_inject(...)`。它们可用于 component 类属性或 `__init__` 参数注解，最终归一为 `ParameterSpec` / `InjectSpec`
- `object_param(...)` 支持 `string/text/integer/number/boolean/enum/array/object/json/date/datetime/time/url/path/secret`，并可通过 `schema` / `item_schema` 描述 `object` 与 `array` 的结构；`Literal[...]`、`list[T]`、`dict[str, T]`、`Optional[T]`、`datetime` 类型和 `pathlib.Path` 可被运行时注解推断
- `TaskSpec` / `WorkflowSpec` / `EnvSelectorSpec` / `PageSpec` 已从 contracts 包移除；0.4.x 模块只能使用 v2 装饰器声明运行能力和页面
- 不内置调度器、执行器、环境管理器、HTTP 客户端或其他第三方宿主适配器
- `TaskContext` 仍保留少量与契约紧耦合的辅助方法（如等待、截图、停止/信号状态记录）
- `TaskContext.http` 为可选注入能力；contracts 包本身不再内置 aiohttp 风格默认实现
- 供 `crawler4j`、`crawler4j-sdk` 与标准模块共同依赖

模块运行时代码只应依赖本包。`crawler4j-sdk` 只作为开发依赖提供 CLI、脚手架、校验和打包辅助，不提供运行时 owner、`TaskScript` / `TaskFlow`、旧环境选择器或资源池 helper。

非数据库类宿主能力继续通过 `TaskContext.tools` 调用。环境选择统一声明为 `candidates/*.py` 中的 `@env_candidates` 同步纯函数，账号状态、黑号、注册时间和会员等级等过滤由候选函数实时读取模块数据表完成，不使用资源池同步快照。批量环境清理候选统一声明为 `cleanups/*.py` 中的 `@env_cleanup_candidates` 同步纯函数，复用 `EnvCandidates` 查询 DSL，但只表达待清理 env id，实际删除由宿主预览确认和安全校验后执行。
