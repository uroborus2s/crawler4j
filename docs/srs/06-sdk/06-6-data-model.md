# 6.6 数据模型与持久化（SDK 视角）

本节从 SDK 视角定义“脚本可见的数据模型”与“可持久化边界”，用于保障：

- TaskResult/TaskContext/state 等数据可被稳定消费（UI/日志/存储/回放）
- 可恢复执行（断点恢复）与幂等重试具备最小数据基础
- 数据合规（脱敏/最小化）

## 6.6.1 需求说明

- MUST：TaskResult 必须可 JSON 序列化（字段稳定，见 6.4）。
- MUST：TaskContext.config/state 必须是“可序列化结构”（dict/list/标量），避免塞入不可序列化对象。
- SHOULD：对“可恢复执行”所需的关键游标（cursor/last_id/phase）有明确落点（state + 持久化）。
- SHOULD：SDK 提供一个稳定的数据访问聚合入口 `ctx.db`（允许为空），脚本不直接绑定具体数据库实现。

## 6.6.2 数据契约与版本兼容

### 6.6.2.1 数据分类（边界）

1. **运行态数据（In-memory）**

- 位置：`TaskContext.state`、`TaskContext.captured_data`
- 特点：生命周期仅限一次执行；可用于子任务之间传参、阶段标记、临时缓存

2. **结果数据（Result）**

- 位置：`TaskResult`
- 特点：一次执行的对外输出；运行时将其采集并决定是否持久化

3. **持久化数据（Persistent）**

- 位置：由 Core/Runtime 提供的数据服务（`ctx.db`）落库
- 特点：跨进程/跨重试存在；支持恢复与追溯

### 6.6.2.2 ctx.state 的约束（推荐规范）

- MUST：仅存放 JSON 可序列化值。
- SHOULD：约定保留键（建议前缀或命名空间），避免不同脚本键冲突：
  - `state["phase"]`：当前阶段
  - `state["cursor"]`：游标/分页信息
  - `state["artifacts"]`：输出物引用（截图路径等）
  - `state["inputs"]`：关键输入快照（脱敏后）
- SHOULD：不要把 Playwright Page/Context、Logger、DB 连接等对象塞入 state。

### 6.6.2.3 DataService（SDK 稳定入口）

实现参考：`crawler4j_sdk/db.py`

SDK 侧仅约定：

- `ctx.db` 为 `DataService | None`
- `DataService` 聚合多个子服务（Protocol）：
  - `accounts`：账号/身份类数据访问（读多写少）
  - `storage`：全局 KV（轻量状态/游标/开关）
  - `tasks`：任务记录（提交结果/状态变更/流水）

约束：

- MUST：脚本对 `ctx.db` 判空，或调用 `ctx.db.is_available()` 再使用。
- SHOULD：写操作尽量幂等（例如按唯一键 upsert），避免重试导致重复写。

### 6.6.2.4 数据版本与向后兼容

- MUST：SDK 对外字段变更遵循语义化版本（见 6.8）。
- SHOULD：对持久化记录引入 `schema_version`（由 Core/Runtime 落库），便于迁移。
- SHOULD：TaskResult.data 中的数据结构尽量保持向后兼容（只新增键，不改语义）。

## 6.6.3 典型持久化场景（建议）

1. **断点恢复**：

- 将 `cursor/phase/last_id` 写入 `ctx.db.storage.set_kv(...)`
- 重试/恢复时读回并回填到 `ctx.state`

2. **业务结果记录**：

- 将关键输出（脱敏后的结构化字段）写入 `ctx.db.tasks.record_submission(...)`

3. **输出物（Artifacts）**：

- 截图/日志片段等大对象不入 TaskResult.data，保存到文件/对象存储后仅回填引用

## 6.6.4 合规与脱敏（强制要求）

- MUST：任何持久化数据不得包含明文密码、Cookie、Token 等机密。
- MUST：PII（手机号、证件号等）在持久化/结果返回前必须脱敏或最小化。
