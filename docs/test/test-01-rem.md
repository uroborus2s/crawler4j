# 测试设计文档：[Module-01] 运行时环境管理 (REM)

## 1. 测试范围与目标

本测试文档覆盖《需求规格说明书 5.2》及《详细设计文档 Module-01》中定义的所有功能需求 (FR) 和非功能需求 (NFR)。
目标是验证环境管理器 (EnvironmentManager) 能正确管理 Browser/HTTP 等环境的声明周期，并能处理各种异常情况。

**测试对象**: `src.core.rem` 包
**核心类**: `EnvironmentManager`, `EnvPool`, `LeaseManager`

## 2. 功能需求测试 (FR Testing)

### FR-CORE-ENV-001 环境创建 (Environment Spawning)

| 用例ID | 场景描述 | 前置条件 | 输入数据 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_REM_001 | **标准浏览器环境创建 (Success)** | Playwright 安装正常 | `req={kind: "browser", provider: "playwright"}` | 1. 启动新 Browser 进程<br>2. Env 对象创建成功<br>3. 状态变为 READY | P0 |
| TC_REM_002 | **带标签的特定环境创建** | 无 | `req={tags: ["headless", "pixel-8"]}` | 创建的环境 metadata 包含指定 tags | P1 |
| TC_REM_003 | **不支持的 Provider 类型** | 无 | `req={provider: "unknown_provider"}` | 抛出 `ProviderNotFoundError` 或 `InvalidConfigError` | P2 |
| TC_REM_004 | **Provider 创建异常** (Sad Path) | 模拟 Provider 内部抛出异常 | `req={...}` | 1. 捕获 Provider 异常<br>2. 向上抛出 `SpawnError`<br>3. 不残留僵尸 Env 对象 | P1 |

### FR-CORE-ENV-002 环境租用 (Environment Acquisition)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_REM_005 | **租用空闲环境 (Reuse)** | Pool 中有 1 个 READY 环境 | 调用 `acquire` 匹配该环境 | 1. 返回该 Env 的 Lease<br>2. Env 状态变更为 BUSY<br>3. 不触发 Spawn | P0 |
| TC_REM_006 | **租用特定 Capability 环境** | Pool 中有多种 capability 环境 | 调用 `acquire` 请求特定 cap | 返回匹配 Cap 的环境，而非随机返回 | P1 |
| TC_REM_007 | **无空闲环境时触发创建** | Pool 为空 | 调用 `acquire` | 1. 触发 Spawn 流程<br>2. 等待创建完成后返回 Lease<br>3. 池大小 +1 | P0 |
| TC_REM_008 | **多线程并发租用** (Concurrency) | Pool 为空，global_max=1 | 2 个线程同时调用 `acquire` | 1. 只有一个成功获得 Lease<br>2. 另一个根据策略排队或失败<br>3. 池大小严格为 1 | P1 |

### FR-CORE-ENV-003 环境释放 (Environment Release)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_REM_009 | **正常释放 (Clean Release)** | 环境 BUSY，Lease 有效 | 调用 `release` | 1. Provider.reset 被调用<br>2. Env 状态变更为 READY<br>3. Lease 失效 | P0 |
| TC_REM_010 | **脏释放 (Dirty Release)** | 环境 BUSY | 调用 `release(dirty=True)` | 1. Env 状态变更为 TERMINATING/DEAD<br>2. 触发 Provider.destroy | P1 |
| TC_REM_011 | **无效 Lease 释放** (Sad Path) | 无 | 使用伪造/过期的 Lease ID 释放 | 抛出 `InvalidLeaseError`，环境状态不受影响 | P2 |
| TC_REM_012 | **重复释放** | 环境已 READY | 再次调用 `release` | 抛出 `LeaseExpiredError` 或静默忽略（需明确定义） | P2 |

### FR-CORE-ENV-004 环境健康检查 (Health Check)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_REM_013 | **释放时自动体检 (Pass)** | 环境 BUSY | 释放环境，Mock HealthCheck=True | 环境回到 READY 池 | P1 |
| TC_REM_014 | **释放时自动体检 (Fail)** | 环境 BUSY | 释放环境，Mock HealthCheck=False | 1. 环境标记为 UNHEALTHY/DEAD<br>2. 触发销毁流程 | P1 |
| TC_REM_015 | **周期性巡检** | Pool 中有 READY 环境 | 触发后台健康检查任务 | 对所有空闲环境执行 check，踢除失效环境 | P2 |

### FR-CORE-ENV-005 兜底回收 (Fail-safe Reaping)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_REM_016 | **进程级僵尸回收** | DB 中有 BUSY 记录，但重启后无内存对象 | 系统启动 (Startup) | 1. DB 记录更新为 DEAD<br>2. 尝试根据 PID (如有) Kill 进程 | P0 |
| TC_REM_017 | **Lease 超时回收** | 环境 BUSY，Lease 设置 TTL=5s | 等待 6s | 1. 系统强制回收环境<br>2. 标记环境为 DIRTY 并销毁<br>3. 触发 LeaseExpired 事件 | P1 |

### FR-CORE-ENV-006 配额与上限 (Quota & Limits)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_REM_018 | **达到最大实例数** | Pool 实例数 = max_instances | 调用 `acquire` (Pool 无 READY) | 1. 不触发 Spawn<br>2. 抛出 `ResourceExhaustedError` | P1 |
| TC_REM_019 | **空闲环境 TTL 自动缩容** | 环境 READY，idle_ttl=10s | 等待 11s | GC 线程回收该环境，池大小 -1 | P2 |

## 3. 非功能需求测试 (NFR Testing)

### NFR-CORE-ENV-001 稳定性 (Stability)

*   **TC_REM_STABILITY_001**: 连续进行 100 次 `acquire` -> `random sleep` -> `release` 循环，观察内存泄漏情况和句柄残留数。
*   **TC_REM_STABILITY_002**: 模拟 Provider 随机崩溃（Chaos Monkey），验证系统能否将受影响的任务隔离，而不影响后续任务。

### NFR-CORE-ENV-002 可观测性 (Observability)

*   **TC_REM_OBS_001**: 验证每次状态变更（READY->BUSY, BUSY->READY）是否都产生了标准格式的日志。
*   **TC_REM_OBS_002**: 验证 Metrics 指标 `active_environments_count` 是否准确反映当前池大小。
