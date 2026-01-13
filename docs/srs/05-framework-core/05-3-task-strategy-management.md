# 5.3 任务策略管理 (TSM)

## 5.3.1 定义
TSM (Task Strategy Management) 是框架的**智能决策中枢**。它从"简单的配置容器"升级为"动态规则引擎"，负责解决**用什么跑 (Resource)**、**不够怎么办 (Scaling)**、**运行时异常怎么办 (Resilience)** 以及 **用完怎么处理 (Teardown)** 四大核心问题。

TSM 不直接管理基础设施，而是通过**策略 (Policy)** 指挥 REM (资源管理) 和 MMS (模块执行) 协同工作。

### 核心价值
1. **弹性伸缩**: 从静态资源分配转变为按需动态供给，支持削峰填谷。
2. **精细化调度**: 基于标签 (Label) 和表达式 (Expression) 的多维资源匹配。
3. **故障自愈**: 自动隔离不健康环境，提供任务级和环境级双重容错。
4. **生命周期管理**: 不仅仅是开关，更包含状态保持 (KeepAlive)、回收 (Recycle) 和销毁 (Destroy) 的智能决策。

---

## 5.3.2 策略模型设计 (V2)

### 1. 资源选择策略 (Resource Selector)
解决 **"找到最合适的环境"**。
- **环境类型 (Type)**: 基础过滤 (e.g. `chrome`, `android`).
- **标签匹配 (Match Labels)**: 硬性约束 (e.g. `region: cn`, `isp: telecom`).
- **表达式筛选 (Match Expressions)**: 动态逻辑 (e.g. `cookies.health > 0.8`, `uptime < 2h`).
- **排序策略 (Ranking)**: 
    - `FIFO`: 优先使用最早空闲的环境 (减少冷启动).
    - `BestFit`: 优先使用健康度最高的环境.
    - `Random`: 有意随机化以分散风险.

### 2. 弹性伸缩策略 (Scaling Policy)
解决 **"资源不足时的决策"**。
- **模式 (Mode)**:
    - `Strict`: 严格模式。资源不足则排队/报错，不自动创建。适用于人工维护的稀缺资源。
    - `Elastic`: 弹性模式。自动调用 REM 创建新环境。
- **阈值 (Limits)**: `min_idle` (最小空闲/预热), `max_concurrency` (最大并发).
- **初始化 (Init Workflow)**: 新环境创建后，自动执行的初始化任务 (如自动登录、注入 Cookies).

### 3. 执行与容错策略 (Execution & Resilience)
解决 **"运行时的稳定性"**。
- **任务级重试**: 业务报错 (如验证码) 是否重试？
- **环境级重试**: 环境崩溃或不健康时，是否更换环境重试？
- **超时控制**: 细分 `wait_timeout` (等资源), `init_timeout` (初始化), `exec_timeout` (业务执行).

### 4. 生命周期清理策略 (Teardown Policy)
解决 **"任务结束后的环境处置"**。
- **触发条件**: 区分 `OnSuccess` 和 `OnFailure`.
- **处置动作**:
    - `Destroy`: 彻底销毁 (一次性环境).
    - `Recycle`: 清理会话后放回池中 (高复用).
    - `Hibernate`: 挂起进程 (省资源但保活).
    - `KeepAlive`: 保持现场 (用于排查问题).

---

## 5.3.3 数据结构 (YAML Schema)

```yaml
id: "strategy_ctrip_hotel_detail_elastic"
name: "携程酒店详情抓取-弹性策略"
description: "优先复用高健康度账号，不足时自动注册新环境"

# 1. 资源选择
selector:
  env_type: "chrome"
  match_labels:
    region: "cn"
  match_expressions:
    - "status == 'active'"
    - "cookies.health >= 80"
  sort_strategy: "best_fit"
  wait_timeout: 30

# 2. 弹性伸缩
scaling:
  mode: "elastic"       # strict | elastic
  max_concurrency: 50
  min_idle: 5           # 保持 5 个预热环境
  init_workflow: "ctrip/login_flow"  # 新环境自动登录
  creation_timeout: 180

# 3. 目标执行
execution:
  module: "ctrip"
  workflow: "collect_hotel_detail"
  timeout: 300

# 4. 容错控制
retry:
  max_attempts: 3
  retry_on_condition: ["CaptchaError", "NetworkTimeout"]
  new_env_on_retry: true  # 失败换环境

# 5. 清理策略
teardown:
  on_success: "recycle"     # 成功则回收复用
  on_failure: "keep_alive"  # 失败则保留现场
```

---

## 5.3.4 运行时逻辑

TSM 编排器 (Orchestrator) 的执行流：

1. **Find Resource**: 根据 `selector` 向 REM 查询候选环境。
2. **Analysis**:
    - 若有候选 -> 按 `sort_strategy` 选一个 -> `Lease` (租用)。
    - 若无候选 -> 检查 `scaling.mode`。
3. **Scaling (Elastic)**:
    - 检查 Quota < `max_concurrency` ?
    - 调用 REM `Provision` 创建新环境。
    - 调用 MMS `Execute` 运行 `init_workflow`。
    - 初始化成功 -> `Lease`。
4. **Execute**:
    - 在租用的环境中运行目标 `workflow`。
5. **Handle Result**:
    - **Success**: 执行 `teardown.on_success` 动作 (如 Recycle)。
    - **Failure**: 
        - 检查 `retry` 策略。若可重试 -> (可能换环境) -> Goto Step 1/4。
        - 不可重试 -> 执行 `teardown.on_failure` 动作 (如 KeepAlive)。

---

## 5.3.5 接口定义

### Python 原型

```python
class StrategyOrchestrator:
    async def execute(self, strategy: TaskStrategy, task_input: dict):
        # 核心编排逻辑
        pass
```
