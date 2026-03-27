# 6.3 TaskContext（执行上下文与能力注入）

TaskContext 是 SDK 的“能力总线”（capability bus）：脚本不直接依赖运行时内部对象，而是只依赖 `TaskContext` 提供的稳定能力。

## 6.3.1 需求说明

- MUST 为 TaskScript/TaskFlow 提供统一的运行时能力入口。
- MUST 可序列化/可诊断：至少包含 `env_id/task_name/config/state` 等可用于定位问题的字段。
- SHOULD 支持浏览器自动化：提供 `page`/`context`（Playwright 对象）能力。
- SHOULD 支持网络访问：提供 `http`（异步 HTTP 客户端）能力。
- SHOULD 支持数据访问：提供 `db`（聚合数据服务）能力，并允许在缺省情况下为 None。
- SHOULD 支持调试：提供截图、等待、配置读取等工具方法。
- SHOULD 支持复合任务：提供 `run_subtask()` 作为子任务执行入口（由运行时注入执行器）。

## 6.3.2 能力面清单（以当前实现为准）

实现参考：`crawler4j_sdk/context.py`

### 6.3.2.1 基础字段

- `env_id: int`：环境 ID（用于日志前缀、数据隔离等）
- `task_name: str`：当前任务名（TaskScript.name）
- `config: dict`：任务配置（JSON 解析后的 dict）

### 6.3.2.2 浏览器能力（Playwright）

- `page: Page | None`：页面对象（可为 None，取决于运行模式）
- `context: BrowserContext | None`：浏览器上下文

约束：

- MUST：脚本在访问 `page/context` 前应当允许其为 None（或在契约中声明该脚本必须运行在 Browser 模式）。

### 6.3.2.3 日志能力

- `logger: logging.Logger`

约束：

- MUST：脚本用 `ctx.logger` 输出业务日志；不得假设全局 logger 名称。
- SHOULD：日志信息包含关键标识（如账号、订单号等）时必须脱敏（见 6.3.3）。

### 6.3.2.4 HTTP 能力

- `http: HttpClient`：提供 `get/post` 等方法（当前实现基于 aiohttp）

约束：

- SHOULD：调用方显式传入 timeout、headers 等；不得无限等待。

### 6.3.2.5 数据能力

- `db: DataService | None`
- `DataService` 聚合了 `accounts/storage/tasks` 等子服务（以 Protocol 形式定义）

补充说明：仓库当前实现中可能还会在 `TaskContext` 上注入一些“领域特定”字段（例如某些业务的 account 对象）。

- SHOULD：此类字段视为 **non-stable 扩展**，不应作为通用 SDK 契约依赖；通用脚本只依赖本章列出的字段/方法。

约束：

- MUST：脚本在访问 `ctx.db` 前判空或调用 `ctx.db.is_available()`（若存在）。

### 6.3.2.6 共享状态与数据

- `state: dict`：跨方法/跨子任务共享的“工作内存”。
- `captured_data: list`：抓取/提取的原始数据集合（用于结果汇总或持久化）。

约束：

- SHOULD：`state` 仅保存运行态临时信息；可恢复信息建议同步写入 db/storage（见 6.7）。
- SHOULD：`captured_data` 中包含敏感信息时必须脱敏或仅存引用。

### 6.3.2.7 子任务执行（复合任务）

- `async run_subtask(task_name: str, **kwargs) -> Any`

语义（与当前实现一致）：

- kwargs 会合并到 `ctx.state`（共享给后续子任务）。
- 返回值优先为子任务结果的 `result.data`。

约束：

- MUST：当 `_subtask_executor` 未注入时，`run_subtask` 抛出 RuntimeError；脚本作者不得自行注入。

### 6.3.2.8 停止/取消

- `request_stop()`：设置停止标志
- `should_stop() -> bool`：查询停止标志

约束：

- SHOULD：长循环工作流必须周期性检查 `should_stop()`。

### 6.3.2.9 工具方法

- `wait(seconds)`：异步等待
- `screenshot(name) -> str`：截图并返回保存路径
- `get_config(key, default=None)`：读取配置项（便捷）

## 6.3.3 安全与最小权限

### 6.3.3.1 最小权限原则

- MUST：TaskContext 只注入脚本“需要的最小能力集合”。例如：无浏览器任务可不给 page/context。
- SHOULD：敏感能力（如数据库写、账号明文）应可通过运行模式/环境开关控制。

### 6.3.3.2 机密与 PII 处理

- MUST：日志中不得输出账号密码、Cookie、Token 等机密。
- SHOULD：对手机号、身份证等 PII 进行脱敏（如 `138****8000`）。
- SHOULD：`TaskResult.data` 与 `captured_data` 中的敏感字段应在写入前脱敏。

## 6.3.4 功能级规格（按模板）

当某个能力需要扩展（例如新增 `ctx.metrics`、`ctx.files`）时，应按模板输出：

- 需求动机与使用场景
- 字段/方法签名（含类型提示）
- 运行时注入责任（谁注入、何时注入、失败行为）
- 安全与权限边界
- 兼容性与迁移策略（是否 Breaking）

模板参考：`docs/archive/reference-srs/templates/feature.md` / `docs/archive/reference-srs/templates/api-contract.md`
