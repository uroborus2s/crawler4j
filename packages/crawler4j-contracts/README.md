# crawler4j-contracts

`crawler4j-contracts` 是 Core、SDK 与外部模块共享的稳定运行时契约包，当前源码版本基线为 `0.4.0`。

## 包含内容

- 提供 `TaskContext` / `TaskResult` 等契约类型
- 提供 `TaskSignal` / `TaskSignalAction` / `EnvAction` 等流程控制信号
- 提供 `ToolsCapability` / `ToolSpec` / `HttpClient` 等宿主扩展能力契约
- 提供 `DatabaseClient`，模块数据唯一正式入口为 `TaskContext.db`
- 提供 `core-native-v2` 装饰器：`@interface`、`@component`、`@workflow`、`@page_action`、`@data_table`、`@data_query`
- 提供对象装配注解 helper：`object_param(...)`、`object_inject(...)`。它们可用于 component 类属性或 `__init__` 参数注解，最终归一为 `ParameterSpec` / `InjectSpec`
- `TaskSpec` / `WorkflowSpec` / `EnvSelectorSpec` 已从 contracts 包移除；0.4.x 模块只能使用 v2 装饰器声明运行能力
- 不内置调度器、执行器、环境管理器、HTTP 客户端或其他第三方宿主适配器
- `TaskContext` 仍保留少量与契约紧耦合的辅助方法（如等待、截图、停止/信号状态记录）
- `TaskContext.http` 为可选注入能力；contracts 包本身不再内置 aiohttp 风格默认实现
- 供 `crawler4j`、`crawler4j-sdk` 与标准模块共同依赖

模块运行时代码只应依赖本包。`crawler4j-sdk` 只作为开发依赖提供 CLI、脚手架、校验和打包辅助，不提供运行时 owner、`TaskScript` / `TaskFlow` 或资源池 helper。

非数据库类宿主能力继续通过 `TaskContext.tools` 调用。资源池资格卡片由宿主 `env.*` tools 维护；模块如果需要便捷函数，应在模块仓内自行封装本地薄 helper。
