# Strategy Configuration V2 & Environment Acquisition Design

## 1. 概述 (Overview)

本设计旨在重构 `Strategy` (策略) 配置模型，以适配 [Task Engine V2](task-engine-v2.md) 的四种运行模式，并重点解决 **环境获取 (Environment Acquisition)** 的灵活性问题。

核心目标：
1.  解耦 **任务逻辑** (Module) 与 **运行环境** (Environment)。
2.  支持两种环境获取模式：
    *   **Match (复用模式)**: 从现有环境池中筛选（如“使用任何空闲的美国节点”）。
    *   **Create (创建模式)**: 按需调用 Provider API 创建新环境（如“调用 BitBrowser 接口创建一个新窗口”），并在任务结束后销毁或保留。

---

## 2. 策略模型定义 (Strategy Schema)

策略 (Strategy) 是连接 `Job` (作业) 和 `Resources` (资源) 的静态配置模板。

### 2.1 数据结构

```yaml
name: "strategy-dynamic-spider"
display_name: "动静结合采集策略"
description: "优先复用，不够则创建"

# 1. 执行规范 (Execution Spec): 决定跑什么代码
execution:
  module_name: "example_module"  # 关联 Module
  entry_point: "main"           # 入口函数
  default_params:               # 默认参数 (可被 Job 覆盖)
    max_pages: 100

# 2. 资源规范 (Resource Spec): 决定在哪跑
resource:
  provider: "bitbrowser"        # 指定底层 Provider (bitbrowser, virtual_browser, local)
  
  # 获取模式: 'match' | 'create' | 'hybrid' (可选高级模式)
  acquisition:
    mode: "create" 
    
    # [Match 模式配置] 筛选现有环境
    selector:
      tags:
        region: "us"
        platform: "amazon"
      status: "ready"           # 默认为 ready
      
    # [Create 模式配置] 动态创建参数
    creation:
      # 生命周期: 'ephemeral' (任务结束即销毁) | 'persistent' (保留复用)
      lifecycle: "ephemeral"
      
      # 创建参数 (传递给 Provider.create)
      params:
        group_id: "idxxxxx"     # BitBrowser 分组 ID
        fingerprint:
          os: "Windows"
          version: "130"
          randomize: true
        proxy:                  # 代理配置策略
          mode: "pool"          # 使用代理池
          pool_id: "pool-us-01"

# 3. 容错与并发规范 (Resilience & Scaling)
policy:
  concurrency:
    limit: 50                   # 策略级硬上限
  retry:
    max_attempts: 3
    retry_on_error: true
```

---

## 3. 环境获取流程 (Acquisition Logic)

Dispatcher 在接收到 Job 的 Task 生成请求时，根据 Strategy 解析环境。

### 3.1 流程图 (Mermaid)

```mermaid
flowchart TD
    Start[Task Created] --> CheckMode{Acquisition Mode?}
    
    %% Macth Mode
    CheckMode -- Match --> QueryDB[Query DB for Idle Env]
    QueryDB --> Found{Found?}
    Found -- Yes --> LockEnv[Atomic Lock (Lease)]
    Found -- No --> WaitOrFail[PendingQueue / Timeout]
    LockEnv --> BindTask[Bind Task to Env]
    
    %% Create Mode
    CheckMode -- Create --> CallProvider[Call Provider.create()]
    CallProvider --> APISuccess{API Success?}
    APISuccess -- Yes --> SaveDB[Insert Env Record]
    SaveDB --> BindTask
    APISuccess -- No --> FailTask[Task Failed]
    
    %% Execution
    BindTask --> Run[Execute Module Script]
    Run --> Finish[Task Finished]
    
    %% Cleanup
    Finish --> CheckLifecycle{Lifecycle?}
    CheckLifecycle -- Ephemeral --> Destroy[Call Provider.destroy()]
    CheckLifecycle -- Persistent --> Release[Release Lock (Set Ready)]
    Destroy --> End
    Release --> End
```

### 3.2 模式详解

#### 模式 A: Match (复用模式)
*   **场景**: 只有固定数量的指纹环境（如 100 个账号窗口），任务轮转使用。
*   **逻辑**:
    1.  根据 `resource.selector` 构建 SQL 查询条件。
    2.  `SELECT ... FOR UPDATE SKIP LOCKED` 锁定空闲环境。
    3.  若无可用环境，Task 进入 `PENDING` 状态，等待资源释放。
*   **适用 Job**: `Manual Parallel`, `Continuous Concurrency` (在固定资源池内)。

#### 模式 B: Create (创建模式)
*   **场景**: 临时性抓取，需要全新的指纹环境，用完即弃。
*   **逻辑**:
    1.  直接调用 `Provider.create(strategy.resource.creation.params)`。
    2.  Provider 调用外部 API (如 BitBrowser `/browser/update` 或 `/create`) 生成新窗口 ID。
    3.  在本地 DB 插入一条新 Environment 记录。
    4.  任务结束时，根据 `lifecycle: ephemeral` 调用 `Provider.destroy()` 删除远程窗口和本地记录。
*   **适用 Job**: `One-off`, `Cron Job` (每次全新环境)。

---

## 4. 接口变更 (Architecture Changes)

### 4.1 Provider 接口扩充

`src/core/rem/provider.py`:

```python
class BaseProvider(ABC):
    @abstractmethod
    async def create(self, config: dict) -> Environment:
        """
        config 参数将直接透传 Strategy 中的 creation.params
        """
        pass

    async def destroy(self, env: Environment) -> None:
        """
        必须实现：物理删除远程环境
        """
        pass
```

### 4.2 Resource Environment Manager (REM)

需要新增 `EnvironmentFactory`:
*   负责统一处理 Strategy 的 `creation` 配置。
*   处理代理策略解析（如从 `pool_id` 获取真实代理 IP 填充到创建参数中）。

### 4.3 Task Dispatcher

*   需要识别 Strategy 的 mode。
*   对于 Match 模式，走 `EnvAllocator` (资源分配器)。
*   对于 Create 模式，走 `EnvironmentFactory` (资源工厂)，成功后再分配。

---

## 5. 针对 Task Engine V2 4种运行模式的支持

| 运行模式 | 推荐 Strategy 配置 | 行为分析 |
| :--- | :--- | :--- |
| **Manual / One-off** | Mode: Create, Lifecycle: Ephemeral | 点击运行 -> 创建新环境 -> 执行 -> 销毁。最干净。 |
| **Cron / Interval** | Mode: Create, Lifecycle: Ephemeral | 每天定时启动新环境执行。 |
| **Manual Parallel** | Mode: Match (推荐) | 并发跑脚本，复用现有的一批号。 |
| **Continuous** | Mode: Match (推荐) 或 Create | 维持并发。如果是 Match，类似于 Worker 抢单；如果是 Create，则不断生灭容器。 |

## 6. 总结
本设计通过增强 `Strategy` 的表达能力，将环境的“生产”与“消费”逻辑纳入统一配置管理，完美契合 Task Engine V2 的控制器模式。
