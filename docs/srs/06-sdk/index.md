# 第 6 章 系统二：SDK（crawler4j_sdk）

> 本章描述 **Crawler4j SDK**（Python 包：`crawler4j-sdk`）的需求与功能规格。
> SDK 的核心职责是：为“任务脚本/工作流编排”的开发者提供 **稳定、可测试、可发布** 的契约层。

## 6.0 范围与定位

### 6.0.1 目标（Goals）

- **唯一契约边界**：Modules 与 Core/Runtime 之间，必须只通过 SDK 的类型与约定交互。
- **可独立发布**：SDK 作为独立 Python 包发布（语义化版本），外部脚本项目可单独安装/升级。
- **可本地调试**：提供最小 CLI 能力与调试入口（脚手架、列举、快速生成）。
- **可观测/可诊断**：统一日志、错误语义、最小的诊断信息承载方式（TaskResult）。

### 6.0.2 非目标（Non-Goals）

- SDK **不负责** GUI、调度、环境生命周期管理、模块安装等（这些属于 Core/Framework）。
- SDK **不承诺** 对任意第三方站点的稳定性；其稳定性承诺仅针对 SDK 自身 API。

### 6.0.3 代码与制品落点（实现参考）

- 代码目录：`crawler4j_sdk/`
- 关键类型：`TaskScript`、`TaskFlow`、`TaskContext`、`TaskResult`、`DataService`
- CLI：`crawler4j_sdk.cli.commands:main`（命令名：`crawler4j`）

### 6.0.4 严格稳定契约（Freeze List）

本节是 **SDK 对外稳定面（Stable Surface）的唯一权威清单**。

- **同一 MAJOR 版本内**，本清单中的 API/字段/语义 **MUST 保持兼容**。
- 本清单之外（含“非稳定扩展”）的内容：**不做兼容承诺**，可在 MINOR/PATCH 中调整。

#### 6.0.4.1 Stable（同 MAJOR 冻结）

1. `crawler4j_sdk.TaskScript`（实现：`crawler4j_sdk/base.py`）

   - 类属性（MUST 存在）：`name/display_name/description/default_config`
   - 方法（签名与 async 语义 MUST 稳定）：
     - `async execute(self, ctx: TaskContext) -> TaskResult`
     - `async on_init(self, ctx: TaskContext) -> None`
     - `async on_error(self, ctx: TaskContext, error: Exception) -> None`
     - `async on_cleanup(self, ctx: TaskContext) -> None`

2. `crawler4j_sdk.TaskFlow`（实现：`crawler4j_sdk/workflow.py`）

   - 类属性（MUST 存在）：`name/display_name/description`
   - 方法（签名与 async 语义 MUST 稳定）：
     - `async run(self, ctx: TaskContext) -> None`
     - `async on_error(self, ctx: TaskContext, error: Exception) -> None`
     - `async on_complete(self, ctx: TaskContext) -> None`

3. `crawler4j_sdk.TaskContext`（实现：`crawler4j_sdk/context.py`）

   - 字段（字段名与“是否可为空”的语义 MUST 稳定）：
     - `env_id: int`、`task_name: str`、`config: dict`
     - `page: Page | None`、`context: BrowserContext | None`
     - `logger: logging.Logger`、`http: HttpClient`、`db: DataService | None`
     - `captured_data: list`、`state: dict`
   - 方法（签名与返回语义 MUST 稳定）：
     - `wait(seconds: float) -> None`
     - `screenshot(name: str) -> str`（返回保存路径字符串）
     - `get_config(key: str, default=None) -> Any`
     - `request_stop() -> None`、`should_stop() -> bool`
     - `run_subtask(task_name: str, **kwargs) -> Any`（共享 `ctx.state`；默认返回 `TaskResult.data`）

4. `crawler4j_sdk.TaskResult`（实现：`crawler4j_sdk/result.py`）

   - 字段（字段名/类型/序列化键 MUST 稳定）：`success/tasks_completed/message/data/error`
   - 工厂方法（签名 MUST 稳定）：
     - `TaskResult.ok(tasks_completed: int = 1, message: str = "成功", data: dict | None = None, **kwargs)`
     - `TaskResult.fail(message: str, error: str | None = None, data: dict | None = None, **kwargs)`

5. SDK CLI（实现：`crawler4j_sdk/cli/commands.py`）

   - 命令名（MUST 稳定）：`crawler4j`
   - v1.0 已实现命令（命令名与关键副作用 MUST 稳定）：`init/add/new/list`
   - 退出码（MUST 稳定）：`0`=成功，`1`=可预期失败（见 6.5.3）

#### 6.0.4.2 Non-stable（非稳定扩展）

当前实现中存在但 **不纳入稳定面** 的能力/字段（示例，见 6.3）：

- `TaskContext.ctrip_account` / `TaskContext.labor_account`
- `TaskContext.input_callback`

#### 6.0.4.3 Breaking Change 判定（MUST 触发 MAJOR）

满足任意一条即视为 Breaking Change：

- Stable 清单中的符号/字段/方法 **被删除、重命名、移动模块路径**
- Stable 方法签名改变（含参数名、默认值导致行为改变、sync/async 语义变化）
- Stable 字段语义改变（例如从“可能为 None”变为“永不为 None”，或反之）
- `TaskResult` 的字段/序列化结构改变（JSON key 变化、字段含义变化）
- `TaskContext.run_subtask` 的共享状态/返回语义改变
- CLI 命令名、关键参数含义、退出码含义改变

> 说明：本章以“**规范优先** + **实现对齐**”方式撰写：
>
> - 标记为 **MUST/SHOULD/MAY** 的条目属于规范；
> - 对实现细节的引用用于帮助理解，但不应被当作不可变实现。

## 6.1 需求概述（面向使用者）

SDK 使用者分两类：

1. **模块/脚本作者（任务开发者）**：

   - 编写 `TaskScript`（原子任务）与 `TaskFlow`（编排工作流）
   - 通过 `TaskContext` 获取浏览器、HTTP、日志、数据服务等能力
   - 通过 `TaskResult` 返回结构化结果

2. **框架/运行时作者（Core/Runtime）**：
   - 注入 `TaskContext` 的能力与资源
   - 执行脚本并收集 `TaskResult`、实现重试/恢复/取消等策略

SDK 对外必须提供：

- 类型：`TaskScript/TaskFlow/TaskContext/TaskResult`
- 约定：生命周期、并发语义、错误语义、配置合并策略
- 工具：最小 CLI（脚手架/列举）与调试建议

## 6.2 章节导航

- 6.1 TaskScript（原子任务契约）
- 6.2 TaskFlow（工作流编排契约）
- 6.3 TaskContext（执行上下文与能力注入）
- 6.4 TaskResult（结果模型）
- 6.5 CLI（脚手架与校验）
- 6.6 数据模型与持久化（SDK 视角）
- 6.7 错误处理与可靠性（SDK 视角）
- 6.8 非功能需求（SDK）
- 6.9 测试/运维/附录（SDK）
