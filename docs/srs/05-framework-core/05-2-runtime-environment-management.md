# 5.2 运行环境管理（Runtime Environment Management）

本章定义 Framework Core 中“运行环境管理”的职责边界与能力集合，用于为任务执行提供可复用、可隔离、可回收的 **Execution Environment**。

## 5.2.1 需求说明

### 5.2.1.1 概念与范围

Execution Environment 指任务运行所依赖的可操作对象集合，可能是：浏览器实例、HTTP 客户端会话、桌面自动化会话、外部进程/容器等。

运行环境管理系统（以下简称 EnvMgr）负责：

- 统一抽象多种环境的创建、租用、释放与回收
- 为调度/执行侧提供可声明的环境能力（capabilities）与约束匹配
- 对环境实例进行健康检查、失效隔离与兜底回收
- 提供配额、上限、并发控制，避免资源耗尽

边界约束（MUST NOT）：

- MUST NOT 执行任务脚本（TaskScript/TaskFlow 的执行属于 5.4）
- MUST NOT 承担模块发现/加载/校验（属于 5.1）

### 5.2.1.2 对外承诺

EnvMgr 的核心承诺是：**为每一次任务运行提供满足约束的环境租约（EnvLease），并在任务结束后保证资源可回收**。

## 5.2.2 需求分析分解

### 5.2.2.1 功能性需求（FR）

- FR-CORE-ENV-001 环境创建：按环境类型与参数创建新的环境实例（spawn）。
- FR-CORE-ENV-002 环境租用：根据任务请求（kind/capabilities/labels）分配可用环境并返回租约（acquire lease）。
- FR-CORE-ENV-003 环境释放：任务结束后释放租约并执行必要清理（release）。
- FR-CORE-ENV-004 环境健康检查：周期性或按需检测环境是否可用，不可用时标记隔离（health check）。
- FR-CORE-ENV-005 兜底回收：在任务异常退出、进程崩溃或超时情况下回收环境（fail-safe reap）。
- FR-CORE-ENV-006 配额与上限：限制每类环境的最大实例数、最大并发租约数与等待队列策略。

### 5.2.2.2 非功能性需求（NFR）

- NFR-CORE-ENV-001 稳定性：单个环境异常不得影响其他环境与调度主循环。
- NFR-CORE-ENV-002 可观测性：关键事件必须可追踪（创建/分配/释放/隔离/回收）。

## 5.2.3 模块整体设计

### 5.2.3.1 结构

EnvMgr 推荐拆分为三层：

1. **Environment Provider**：面向具体技术栈（例如 BrowserProvider/HttpProvider），负责实际 spawn/keepalive/kill/healthcheck。
2. **Environment Pool**：维护实例池与状态机，负责挑选可用实例、并发控制与回收策略。
3. **Lease Manager**：为任务运行发放租约，关联 task_run_id，处理超时与异常兜底。

### 5.2.3.2 数据模型（语义级）

- `EnvKind`（MUST）：`browser | http | desktop | external`
- `EnvMeta`（SHOULD）：
  - `env_id`：环境实例唯一标识
  - `kind`：环境类型
  - `provider`：提供者标识
  - `external_id`：外部系统环境 ID（用于状态同步）
  - `labels`：静态标签（例如 browser=chromium、os=mac）
  - `capabilities`：能力集合（例如 page/http/files）
  - `state`：CREATING | READY | BUSY | PAUSED | UNHEALTHY | TERMINATING | DEAD
  - `last_used_at`：最后使用时间戳（用于策略匹配）
  - `daily_usage_count`：当天使用次数（用于策略匹配）
  - `proxy_config`：代理配置（静态代理或 IP 池）
  - `fingerprint_config`：指纹配置（Provider 特定）
- `EnvLease`（MUST）：
  - `lease_id`
  - `env_id`
  - `task_run_id`
  - `acquired_at`
  - `expires_at?`（可选，用于强制回收）
- `IPPool`（SHOULD）：
  - `pool_id`：IP 池唯一标识
  - `name`：池名称
  - `provider`：提供商（local/api）
  - `entries`：IP 条目列表

与执行侧的关联：TaskContext 中应携带租约信息（至少 env_id/lease_id/kind/capabilities），用于日志与诊断串联。

### 5.2.3.3 核心流程

#### Acquire（租用）

1. 执行侧提交环境请求：`kind + capabilities + labels(可选)`。
2. Pool 在 READY 实例中挑选匹配项；如无匹配，按策略 spawn 新实例或进入等待队列。
3. Provider 完成创建后返回 EnvMeta；Pool 将其置为 READY。
4. LeaseManager 发放 EnvLease，并将实例置为 BUSY。

#### Release（释放）

1. 执行侧归还 EnvLease。
2. Provider 执行清理（例如关闭页面、清空会话/缓存、删除临时文件）。
3. 若清理成功则回到 READY；若失败或健康检查失败则标记 UNHEALTHY 并进入回收。

#### Fail-safe（兜底回收）

- 当任务崩溃/超时/强制取消时，LeaseManager 必须触发回收：
  - 优先尝试 Provider 的“软清理”
  - 失败则执行 kill，并将实例置为 DEAD

### 5.2.3.4 错误处理与降级

EnvMgr 对外错误应可诊断，建议包含：`stage`（ACQUIRE/CREATE/CLEANUP/KILL/HEALTHCHECK）与 `hint`。

常见错误：

- ENV_UNAVAILABLE：无可用实例且无法创建（达到配额/Provider 不可用）
- ENV_UNHEALTHY：创建成功但健康检查失败
- ENV_CLEANUP_FAILED：释放时清理失败，环境已被隔离

## 5.2.4 功能清单

- 环境池生命周期管理：spawn/keepalive/kill
- 健康检查与隔离：UNHEALTHY 实例不得再次分配
- 回收兜底（fail-safe）：超时/崩溃/取消触发强制回收
- 配额与上限：按 EnvKind/Provider 配置 max_instances/max_leases/queue_policy
