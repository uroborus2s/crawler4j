# 6.4 TaskResult（结果模型）

TaskResult 是原子任务（TaskScript）的标准输出模型，用于：

- 让运行时统一采集成功/失败状态
- 让 UI/日志/监控可以稳定解析
- 为后续持久化与追溯提供结构化载体

## 6.4.1 需求说明

- MUST 可序列化为 JSON（字段语义稳定）
- MUST 支持“成功/失败 + 消息 + 可选错误详情”
- SHOULD 支持携带结构化业务数据（data）
- SHOULD 支持“部分成功/进度”表达（tasks_completed 等）
- SHOULD 支持脱敏与合规（PII/机密字段不得外泄）

## 6.4.2 数据契约（可序列化/可持久化/脱敏）

### 6.4.2.1 稳定字段（以当前实现为准）

实现参考：`crawler4j_sdk/result.py`

- `success: bool`：是否成功
- `tasks_completed: int`：完成的任务数量/条目数量（用于进度/吞吐统计）
- `message: str`：人类可读的结果信息
- `data: dict`：结构化输出（业务数据、诊断字段、统计信息等）
- `error: str | None`：错误信息（失败时可填）

### 6.4.2.2 JSON 形态（建议）

```json
{
  "success": true,
  "tasks_completed": 1,
  "message": "成功",
  "data": { "foo": "bar" },
  "error": null
}
```

约束：

- MUST：字段名保持稳定；新增字段只能向后兼容
- SHOULD：`data` 仅包含 JSON 可序列化值（dict/list/str/number/bool/null）
- SHOULD：大对象（HTML/图片/二进制）不直接塞入 `data`，而是存储后放引用（path/url/id）

### 6.4.2.3 脱敏规则（建议）

- MUST：`data` 与 `error` 中不得出现密码、Cookie、Token 等机密
- SHOULD：手机号/身份证/订单号等敏感信息按规则掩码
- SHOULD：如果需要携带诊断信息，优先使用“错误码 + 追踪 ID”，而不是全量 dump

## 6.4.3 错误与部分成功语义

### 6.4.3.1 失败语义

- 业务失败：使用 `TaskResult.fail(message, error=..., data={...})` 返回（允许在失败时携带部分产出/诊断字段）
- 运行异常：允许抛异常，运行时兜底转换为失败 TaskResult，并记录异常栈（见 6.7）

### 6.4.3.2 部分成功语义

当任务是“批处理/循环抓取”类时，可能出现“部分成功”：

- 建议：`success=True` 但 `tasks_completed < 预期`，并在 `message/data` 中说明剩余原因
- 失败但产出部分数据：`success=False`，但允许在 `data` 中携带已完成部分（需注意脱敏）

### 6.4.3.3 结果可观测字段（建议扩展，向后兼容）

以下键建议放在 `data` 中（可选）：

- `error_code`：稳定错误码（见 6.7）
- `retryable`：是否建议重试
- `duration_ms`：耗时
- `artifacts`：输出物引用（截图路径、日志片段 ID 等）
