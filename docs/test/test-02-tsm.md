# 测试设计文档：[Module-02] 任务策略管理 (TSM)

## 1. 测试范围与目标

本测试文档覆盖《需求规格说明书 5.3》及《详细设计文档 Module-02》中定义的所有功能需求 (FR)。
目标是验证策略管理器 (StrategyManager) 能正确解析 YAML 策略，并通过准入控制器 (AdmissionController) 和资源撮合器 (ResourceMatcher) 实现任务调度的核心逻辑。

**测试对象**: `src.core.tsm` 包
**核心类**: `StrategyManager`, `AdmissionController`, `ResourceMatcher`

## 2. 功能需求测试 (FR Testing)

### FR-TSM-001 策略编辑器与解析 (Strategy Editor & Parsing)

| 用例ID | 场景描述 | 前置条件 | 输入数据 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_TSM_001 | **解析合法 YAML 策略** | 无 | 标准 `strategy.yaml` 字符串 | 1. 成功解析为 StrategyProfile 对象<br>2. 各字段值正确映射 | P0 |
| TC_TSM_002 | **YAML 语法错误** | 无 | 包含非法缩进或字符的 YAML | 抛出 `StrategyParseError`，含错误行号提示 | P1 |
| TC_TSM_003 | **Schema 数据验证失败** | 无 | `global_max: -5` (非法负数) | 抛出 `ValidationError` (Pydantic)，拒绝加载 | P1 |
| TC_TSM_004 | **多层级策略合并 (Override)** | 定义了 Global, Module, Task 级策略 | Task 提交时携带 `override` | 最终 Effective Policy 取 Task > Module > Global 的值 | P0 |
| TC_TSM_005 | **默认策略回退** | 未定义 Module 策略 | Task 提交无 override | 最终 Effective Policy 回退使用 Global 默认值 | P1 |

### FR-TSM-002 环境自动化配置 (Environment Automator / Matching)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_TSM_006 | **静态池模式匹配** (mode=static) | 此模式下不许自动创建 | Pool 无可用环境 | Matcher 应直接报错 `ResourceUnavailable` 或建议排队，不调用 spawn | P1 |
| TC_TSM_007 | **动态创建模式匹配** (mode=dynamic) | Pool 为空 | 调用 Matcher | 生成包含 Template 的 EnvRequirement，指示 Core 做 Spawn | P0 |
| TC_TSM_008 | **混合模式优先复用** (mode=hybrid) | Pool 有 1 个可用 | 调用 Matcher | 生成指向该 Env 的 Lease Request，而不指示 Spawn | P0 |
| TC_TSM_009 | **模板参数渲染** | 策略含 `browser_context_options` | 这里包含 `{proxy: "${PROXY_JP}"}` | 生成的 Env Config 中变量被正确替换 (如替换为具体代理 URL) | P2 |

### FR-TSM-003 动态配额桶 (Dynamic Buckets / Admission)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_TSM_010 | **全局并发未满准入** | Active=5, Max=10 | 提交任务 | Admission 返回 `GRANTED`，计数器变为 6 | P0 |
| TC_TSM_011 | **全局并发已满拒绝** | Active=10, Max=10 | 提交任务 | Admission 返回 `DENIED_GLOBAL_QUOTA` (或入队) | P0 |
| TC_TSM_012 | **分组桶配额限制** | `module:A` limit=2, active=2 | 提交 Module A 任务 | Admission 返回 `DENIED_BUCKET_QUOTA` (原因: module:A 满) | P1 |
| TC_TSM_013 | **分组桶未定义** | Module B 未定义 bucket | 提交 Module B 任务 | 只受 Global Max 限制，不受 Bucket 限制 | P2 |
| TC_TSM_014 | **并发计数器释放** | 任务结束 | 调用 `release_quota` | 计数器 -1，若有排队任务则尝试唤醒 | P0 |

## 3. 场景测试

### SC_TSM_001 策略热更新 (Hot Reload)
1. 系统运行中，将 `global_max` 从 10 修改为 20 并保存。
2. 验证：
   - DB 中的策略记录已更新。
   - `EventBus` 广播 `STRATEGY_UPDATED`。
   - `AdmissionController` 的内存配置实时更新。
   - 原本因为 Quota=10 排队的任务，现在因配额增加而被调度执行。

### SC_TSM_002 优先级抢占 (Priority Preemption) - *可选特性*
1. 策略配置 `priority_queues: true`。
2. 提交 10 个低优先级任务占满 Quota。
3. 提交 1 个高优先级任务 (P0)。
4. 验证：高优先级任务是否能插队（取决于设计是否支持抢占或只是简单排队头）。*注：当前设计为非抢占式排队* -> 验证 P0 任务被放入 Pending 队列头部，一旦有资源释放立即执行。
