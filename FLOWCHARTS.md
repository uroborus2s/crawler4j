# 系统流程图 (System Architecture & Flows)

## 1. 自动任务调度流程 (Automatic Scheduling Flow)
描述 `TaskScheduler` 如何管理并发、获取环境并分发任务。

```mermaid
graph TD
    Start([调度器启动]) --> Init[清理旧锁/重置状态]
    Init --> Loop{主循环 Running?}
    
    Loop -- No --> Stop([停止])
    Loop -- Yes --> CheckLimit{并发数 < Limit?}
    
    CheckLimit -- No --> Wait[等待间隔 TaskInterval]
    Wait --> Loop
    
    CheckLimit -- Yes --> FindEnv[获取可用环境]
    
    subgraph EnvironmentManager [环境管理器]
        FindEnv --> CheckIdle{有空闲环境?}
        CheckIdle -- Yes --> GetIdle[获取空闲环境]
        CheckIdle -- No --> CreateNew{能创建新环境?}
        
        CreateNew -- Yes --> AssignCtrip[分配携程账号]
        AssignCtrip --> CheckCool{API账号冷却中?}
        CheckCool -- Yes --> Skip[跳过/换号]
        CheckCool -- No --> CreateProf[创建浏览器配置]
        CreateProf --> DBRec[写入environments表]
        DBRec --> NewEnv[返回新环境]
        
        CreateNew -- No --> Wait
    end
    
    GetIdle --> RunTask
    NewEnv --> RunTask
    
    RunTask[启动 TaskRunner] --> UpdateStatus[状态 -> Running]
    UpdateStatus --> ExecWork[执行工作流]
    ExecWork --> Finish
    
    Finish --> UpdateIdle[状态 -> Idle]
    UpdateIdle --> Wait
```

## 2. 环境生命周期管理 (Environment Lifecycle)
描述手动模式与自动模式下环境的创建与销毁差异。

```mermaid
stateDiagram-v2
    [*] --> Creation
    
    state Creation {
        [*] --> AssignCtrip: 分配携程账号
        AssignCtrip --> ConfigProxy: 配置代理(可选)
        ConfigProxy --> CreateProfile: 调用浏览器API创建配置
        CreateProfile --> DBInsert: 写入数据库(Status=Idle)
    }
    
    Creation --> Idle: 创建成功
    
    state "Running (手动)" as ManualRun
    state "Running (自动)" as AutoRun
    
    Idle --> ManualRun: 用户点击启动
    Idle --> AutoRun: 调度器分配任务
    
    ManualRun --> Idle: 关闭浏览器
    AutoRun --> Idle: 任务完成/失败
    
    state Destruction {
        [*] --> UpdateStatus: 标记为 Destroyed
        UpdateStatus --> DeleteProfile: 删除浏览器配置
        DeleteProfile --> ReleaseCtrip: 释放携程账号(Active->Idle)
        ReleaseCtrip --> [*]
    }
    
    Idle --> Destruction: 手动删除 / 自动清理
    ManualRun --> Destruction: 异常终止
    AutoRun --> Destruction: 致命错误
```

## 3. 统一工作流执行 (Unified Workflow Execution)
描述 `execute_environment_workflow` 的内部逻辑，包含动态劳保账号获取。

```mermaid
sequenceDiagram
    participant S as Scheduler/User
    participant E as WorkflowExecutor
    participant B as Browser
    participant C as CtripWorkflow
    participant L as LaborRepo
    participant W as LaborWorkflow
    
    S->>E: execute_environment_workflow(env)
    E->>E: 加载携程账号
    E->>B: 打开浏览器 (Open Browser)
    
    %% 携程登录阶段
    E->>C: 执行登录 (Login)
    C->>C: 检查登录状态
    alt 未登录
        C->>B: 输入手机号/验证码
        B-->>C: 登录成功
        C->>E: 返回结果
        
        E->>E: 记录登录时间
        opt API账号首次登录
            E->>E: 记录注册时间
            E-->>S: 终止任务 (进入冷却期)
        end
    end
    
    %% 劳保账号获取阶段 (关键变更)
    E->>L: 动态获取并锁定账号 (Lock Account)
    L-->>E: 返回可用 LaborAccount
    
    %% 劳保任务阶段
    E->>W: 劳保登录 (Login)
    W->>B: 执行登录操作
    W-->>E: 登录成功
    
    E->>W: 执行做题循环 (Run Tasks)
    loop 任务循环
        W->>B: 领题 -> 做题 -> 交题
    end
    
    %% 清理阶段
    E->>L: 释放账号锁定 (Unlock)
    E->>B: 关闭浏览器
    E-->>S: 返回执行结果
```
