# 第 4 章 项目架构设计（Architecture）

本章给出蛛行演略（crawler4j）的顶层架构与依赖边界，作为后续 05/06/07 三个子系统规格的总纲。

## 4.1 三层架构与依赖方向

蛛行演略（crawler4j）采用三层架构：**Modules（业务插件）/ SDK（契约层）/ Framework Core（运行时与治理底座）**。

### 4.1.1 分层职责

- **Modules（任务模块体系）**
  - 承载业务语义：站点流程、字段解析、领域规则、风控对抗策略等。
  - 交付形态为“标准模块包”（见 7.1）：包含 manifest、TaskFlow/TaskScript、可选 UI 扩展。
- **SDK（crawler4j_sdk）**
  - 提供稳定契约：`TaskScript/TaskFlow/TaskContext/TaskResult` 与最小 CLI。
  - 目标是让模块“可独立开发/测试/发布”，并使 Core 能以统一方式执行模块。
- **Framework Core（框架核心）**
  - 治理与编排：模块加载、调度、运行环境管理、任务执行、状态持久化、崩溃恢复。
  - UI Host：承载 GUI 与模块 UI 扩展，汇聚日志/事件/诊断。

### 4.1.2 依赖方向与边界（MUST）

1. **依赖方向 MUST：** `Modules → SDK → Core(可选)`。
2. **Modules MUST NOT** 直接导入/调用 Core 内部实现（例如 `src.*`、运行时管理器、数据库实现）。
3. **SDK MUST NOT** 反向依赖 Core：SDK 作为独立包发布，不能通过“偷依赖”绑定 Core 的实现细节。
4. **Core MUST NOT** 包含业务语义：Core 只做资源治理、执行编排、存储与 UI 承载。

> 解释：该边界用于保证“模块升级/替换”不牵动 Core，也避免业务把核心运行时变成不可维护的巨石。

### 4.1.3 执行环境抽象（Execution Environment）

系统把“任务跑在哪里”抽象为 **Execution Environment**（见 5.2），其关键点是：

- Execution Environment **不等同于浏览器**；浏览器只是其中一种形态。
- 环境由 **Environment Provider** 提供（可插拔）：例如 Playwright、本地浏览器、指纹浏览器服务、HTTP Client、桌面自动化驱动等。
- 模块侧通过 `TaskContext` 获取能力（capability），而不是直接操纵 Provider/进程。

## 4.2 微前端/微应用 UI Host 模式

UI 侧采用“Host 承载 + 模块扩展”的模式：核心提供统一 Shell，模块可选提供 UI 扩展，但默认优先 **声明式 UI**。

### 4.2.1 Shell & Routing

- UI Host MUST 提供统一导航与路由，并对模块路由做命名空间隔离：`/modules/{module_name}/...`。
- UI Host SHOULD 提供通用的模块页：配置、启动/停止、运行历史、日志/事件、诊断摘要。

### 4.2.2 Module UI 扩展两种形态

- **声明式 UI（推荐，零代码执行）**
  - 模块交付 YAML/JSON 清单与页面描述，UI Host 在不导入模块代码的前提下渲染。
  - 优点：安全、易审计、失败可回退；缺点：交互复杂度受限。
- **代码 micro-app（受信扩展）**
  - 模块交付可执行 UI 插件（micro-app），由 UI Host 按信任策略装载。
  - 必须经过信任门控与能力白名单控制；装载失败必须回退到通用模块页。

### 4.2.3 命令通道 & 事件总线

- UI→Core 的写操作 MUST 以“命令（command）”提交，并接受同步校验回执（accepted/rejected）。
- Core→UI 的状态变化 MUST 以“事件（event）”广播，UI 以事件作为最终状态依据。

## 4.3 运行时主链路

系统运行时的主链路（宏观）如下：

1. 启动：初始化 Core、状态存储、日志系统；扫描并注册模块。
2. 调度：根据策略（并发/优先级/配额）选取待执行工作流。
3. 撮合：根据工作流需求申请 Execution Environment（租约/并发槽）。
4. 执行：Core 注入 `TaskContext` 能力并执行 TaskFlow/TaskScript。
5. 回收：释放租约、回收环境（或归还到池），清理残留资源。
6. 推送：持久化运行记录，向 UI 推送事件/日志/诊断。
7. 恢复：崩溃重启后进行“残留环境清理 + 运行记录收敛”，恢复可运行状态。

## 4.4 数据与状态域

为保证可恢复与可追溯，系统的状态域划分如下：

- **Core 状态域**：环境注册表与租约、任务运行记录、调度队列快照、错误/告警、审计事件。
- **Module 状态域**：模块自身配置、领域数据缓存/映射（经 DataService 统一入口）。
- **SDK 契约域**：对外稳定的类型与错误语义；任何跨层通信都必须可序列化。

关键标识体系（应贯穿日志/事件/存储）：

- `module_name`：模块唯一标识
- `workflow_name`：工作流唯一名（模块内或全局范围按规范约束）
- `task_name`：原子任务唯一名（模块内必须唯一）
- `env_id`：执行环境标识
- `run_id`：一次运行实例的唯一标识
