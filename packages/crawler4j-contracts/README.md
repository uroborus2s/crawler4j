# crawler4j-contracts

`crawler4j-contracts` 是 Core、SDK 与外部模块共享的稳定契约包，当前源码版本基线为 `0.2.0`。

## 包含内容

- 提供 `TaskContext` / `TaskResult` 等契约类型
- 提供 `TaskSignal` / `TaskSignalAction` / `EnvAction` 等流程控制信号
- 提供 `ToolsCapability` / `ToolSpec` / `HttpClient` 等宿主扩展能力契约
- 不内置调度器、执行器、环境管理器、HTTP 客户端或其他第三方宿主适配器
- `TaskContext` 仍保留少量与契约紧耦合的辅助方法（如等待、截图、停止/信号状态记录）
- `TaskContext.http` 为可选注入能力；contracts 包本身不再内置 aiohttp 风格默认实现
- 供 `crawler4j`、`crawler4j-sdk` 与标准模块共同依赖

大多数模块开发者应优先依赖 `crawler4j-sdk`；只有需要单独复用纯契约层时，才直接依赖本包。
