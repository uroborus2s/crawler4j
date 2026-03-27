# ATM 核心引擎优化建议报告

依据最新的 `design-job-task-engine.md` 架构蓝图，对 `src.core.atm` 下的代码进行了静态审查。
审查发现：虽然核心的数据流与关系定义（Job -> Task -> Controller -> Dispatcher）是合理的单次批处理模型，并且调度与执行完全解耦，但在**退出收尾机制 (Graceful Shutdown)** 与 **异常恢复 (Crash Recovery)** 的实现上仍处于缺失状态。

## 🔴 高优先级问题 (功能缺失与完整性风险)

### 1. 缺失 Crash Recovery 开机自检机制
*   **现象**：程序重启时，数据库里遗留的上一轮处于 `RUNNING` 状态的任务，会被永远丢在那里成为“僵尸”。系统目前没有机制将它们收敛。
*   **建议方案**：
    在 `JobController.start()` 方法中（或启动的 Hook 中），新增一次自检。如果发现库内存在 `RUNNING` 的 Task，立即批量更新其状态为 `FAILED` (附带错误信息 "Engine Crashed / Power-off")，并调用 `rem.manager.force_gc()` 这类机制彻底清理潜在残留环境。

### 2. 缺失 Graceful Shutdown (优雅退出) 与 运行态 Task 追踪
*   **现象**：`TaskDispatcher.dispatch` 采用 `asyncio.create_task(self._run_safe)` 直接把协程扔进了事件循环 (Fire & Forget)。`Dispatcher` 并没有任何地方记录这些正在执行的 `Future/Task` 对象。
*   **后果**：当 UI 退出、核心服务收到 `SIGTERM` 准备停止时，由于没人持有这些运行中 `Task` 的句柄，也没有类似 `asyncio.gather(*active_tasks)` 的等待逻辑，进程会被系统暴力 Kill 掉，导致“等待当前任务安全执行完毕再回收”的架构承诺完全落空，并大概率产生脏数据或浏览器残留。
*   **建议方案**：
    在 `TaskDispatcher` 中维护一个 `self._active_tasks = set()`。每新建一个 asyncio 协程，就加进去，在 `finally` 块里移除它。当收到 `stop()` 信号时，使用 `await asyncio.gather(*self._active_tasks, return_exceptions=True)` 安全等待它们结束后再放行主进程退出。

## 🟡 中/低优先级问题 (规范与健壮性)

### 3. 未被消费的 `CANCELLED` 状态
*   **现象**：`TaskStatus` 中有 `CANCELLED` 枚举，但当前代码路径无法手动触发取消一个处于队列中 (`PENDING`) 或正在执行的过程。
*   **建议**：在 `JobController` 中增加能力，当 `Job` 被暂停 (PAUSED) 或被删除时，找出与其关联但还没拿到底层资源的 `PENDING` 任务，将它们 `CANCELLED` 掉不再执行。

---

> **架构合规性声明**: Current codebase is cleanly separated, maintaining `Module -> SDK -> Core` dependency limits. However, the runtime orchestration (ATM Lifecycle control) currently fails the "safe state termination" criteria defined in `01-general-architecture.md` and `design-job-task-engine.md`.

等待确认报告后实施修改。
