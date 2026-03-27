# 测试设计文档：[Module-05] SDK 核心契约 (SDK)

## 1. 测试范围与目标

本测试文档覆盖《需求规格说明书 5.6/6.0》及《详细设计文档 Module-05》中定义的所有 SDK 接口契约。
目标是验证 SDK (crawler4j-sdk) 能够为 Module 提供稳定、易用的开发接口，并正确桥接 Core 的能力。

**测试对象**: `crawler4j-sdk` 包
**核心类**: `TaskContext`, `TaskScript`, `TaskResult`

## 2. 功能需求测试 (FR Testing)

### FR-SDK-001 任务脚本执行契约 (TaskScript Contract)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_SDK_001 | **继承检测** | 定义 MyTask 但不继承 TaskScript | 尝试注册 | 报错提示类型错误 | P2 |
| TC_SDK_002 | **run 方法签名检查** | 子类 run 方法参数不对 | 静态检查/运行时调用 | 抛出 TypeError | P1 |
| TC_SDK_003 | **生命周期回调执行** | 实现 `on_init`, `run`, `on_cleanup` | 执行任务 | 调用顺序严格为：init -> run -> cleanup | P0 |
| TC_SDK_004 | **Cleanup 总是执行** | `run` 抛出异常 | 执行任务 | `on_cleanup` 仍被调用 | P0 |

### FR-SDK-002 上下文能力注入 (TaskContext Injection)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_SDK_005 | **Page 对象访问** | 环境为 Browser | 在任务中访问 `ctx.page` | 非空，且可调用 Playwright API (如 goto) | P0 |
| TC_SDK_006 | **Logger 注入** | 无 | 调用 `ctx.log.info("msg")` | 日志被 Core 捕获并存储/显示 | P0 |
| TC_SDK_007 | **HTTP Client** | 无 | 调用 `ctx.http.get()` | 发送请求，返回 JSON 结果 | P1 |
| TC_SDK_008 | **Storage API 桥接** | Core 实现了 StorageAdapter | 调用 `ctx.storage.state.set()` | Core 的 DB 中存在该记录 | P0 |

### FR-SDK-003 结果与异常 (Result & Error)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_SDK_009 | **返回成功结果** | 无 | `return TaskResult.ok(data={a:1})` | Core 收到 success=True, data={a:1} | P0 |
| TC_SDK_010 | **返回失败结果** | 无 | `return TaskResult.fail("reason")` | Core 收到 success=False, message="reason" | P0 |
| TC_SDK_011 | **未捕获异常传递** | 无 | `raise ValueError` | Core 捕获异常，将 TaskRun 标记为 FAILED，堆栈清晰 | P0 |

### FR-SDK-004 Mock 与单测支持 (Mocking)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_SDK_012 | **Mock Context 创建** | 无 Core 环境 | `ctx = MockTaskContext()` | 创建成功，且 page/storage 均为 Mock 对象 | P1 |
| TC_SDK_013 | **单元测试编写** | MyTask | 编写 pytest 用例调用 `task.run(mock_ctx)` | 可以在不启动 Core 的情况下验证业务逻辑 | P0 |

## 3. 场景测试

### SC_SDK_001 子任务调用 (Subtask) - *高级特性*
1. 在 Workflow 中调用 `await ctx.run_subtask("sub_task_name", arg1=1)`。
2. 验证：
   - Core 找到对应子任务代码。
   - 子任务被执行，且 `ctx.state` 共享。
   - 子任务返回值被正确传回父任务。
