# 4.6 模块开发最佳实践

本页汇总了在开发 Crawler4j 模块时，为了确保稳定性、高性能和可维护性而推荐的设计模式。

## 1. 数据存储选型：Records vs. State

新手最容易混淆 `db.replace_records` 和 `db.set_state`。请遵循以下准则：

| 维度 | 数据集 (Records) | 运行时状态 (State) |
|---|---|---|
| **适用场景** | 抓取到的业务结果（如酒店列表、订单号） | 运行辅助数据（如 Cookie、翻页 Cursor、最后同步时间） |
| **存储量级** | 支持较大规模数据列表 | 建议控制在 KB 级别 |
| **持久化语义** | Core 可能会将其导出为 Excel/CSV | 仅供模块逻辑内部读取，通常不直接展示给用户 |
| **写入频率** | 建议批量写入 | 随进度实时写入 |

**❌ 错误示例**：把 1000 条采集结果序列化后塞进 `set_state`，这会导致状态库迅速膨胀。
**✅ 正确示例**：采集结果存入 `records`；将 `{"last_page": 5}` 存入 `state`。

---

## 2. 处理并发：幂等与互斥锁

如果你的模块可能被多个作业同时调用（例如多个采集任务同时同步一个账号），请务必使用锁。

```python
# 推荐的加锁模式
lock_scope = "account_sync"
lock_key = ctx.get_config("account_id")

if ctx.tools.call("db.acquire_lock", scope=lock_scope, key=lock_key, ttl=300):
    try:
        # 执行关键逻辑
        do_sensitive_work()
    finally:
        ctx.tools.call("db.release_lock", scope=lock_scope, key=lock_key)
else:
    ctx.logger.warning(f"账号 {lock_key} 正在同步中，跳过本次执行")
```

---

## 3. 长任务的优雅停止

Core 可能会因为用户手动点击“停止”或系统关闭而发出停止信号。

**❌ 错误示例**：`for i in range(10000): ...` 没有任何检查，导致任务杀不掉，残留进程。
**✅ 正确示例**：在长循环中主动检查 `should_stop()`。

```python
async def execute(self, ctx):
    for page in range(1, 100):
        if ctx.should_stop():
            ctx.logger.info("检测到停止信号，正在保存进度...")
            ctx.tools.call("db.set_state", key="resume_page", value=page)
            break
        
        await self.crawl_page(page)
```

---

## 4. 异常处理：Result vs. Raise

*   **使用 `return TaskResult(success=False)`**：当错误是“预料之中”的业务失败时（如：账号密码错误、验证码识别失败）。这会让工作流按计划处理失败分支。
*   **使用 `raise`**：当错误是“不可恢复”的系统故障时（如：SDK 版本完全不兼容、数据库连接中断）。这会触发 Core 的全局捕获，并标记任务为“异常”。

---

## 5. 依赖管理：不要假设 Core 的环境

虽然 Core 的运行环境已经安装了许多包，但请始终在模块的 `pyproject.toml` 中声明你直接依赖的库（如 `pydantic`, `aiohttp`）。
不要假设 Core 一定会永远内置某个特定版本的包。
