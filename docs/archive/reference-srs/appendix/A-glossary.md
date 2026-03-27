# 附录 A：术语表与对象字典

本附录用于统一本文档与实现中的关键术语含义，并列出常用标识与字段的语义解释。

## A.1 术语表（Glossary）

| 术语        | 英文                                        | 说明                                                                                            |
| ----------- | ------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 模块        | Module                                      | 一组可安装/可升级/可禁用的能力集合，以“标准模块包”交付；可包含 workflows/tasks/ui 等。          |
| 标准模块包  | Standard Module Package                     | Modules 的唯一交付物形态（目录或归档），根目录包含 `module.yaml`。                              |
| 模块清单    | Manifest                                    | 模块元信息与声明的集合（本项目约定为 `module.yaml`）。                                          |
| 模块注册表  | Module Registry                             | Core 侧维护的模块索引与状态集合（enabled/disabled/incompatible/invalid 等），供调度与 UI 查询。 |
| 运行环境    | Execution Environment / Runtime Environment | 任务运行所依赖的可操作对象集合（浏览器、HTTP 会话、外部进程等）。                               |
| 环境提供者  | Environment Provider                        | 面向某一类运行环境的适配器，负责 spawn/keepalive/kill/healthcheck。                             |
| 环境池      | Environment Pool                            | 用于复用与限流的一组环境实例及其状态机。                                                        |
| 环境租约    | Environment Lease（EnvLease）               | 将一个环境实例绑定到一次任务运行的临时凭证；用于跟踪、超时与兜底回收。                          |
| TaskScript  | TaskScript                                  | 单个“任务”的可执行脚本/单元；通过 SDK 暴露 `run(ctx)` 等接口（见 6.1）。                        |
| TaskFlow    | TaskFlow                                    | 工作流定义，编排多个 TaskScript 与条件/分支/重试等（见 6.2）。                                  |
| TaskContext | TaskContext                                 | 任务执行上下文（运行参数、环境租约信息、日志/事件句柄等，见 6.3）。                             |
| TaskResult  | TaskResult                                  | 任务输出结果模型（成功/失败/可重试/产物等，见 6.4）。                                           |
| UI Host     | UI Host / Micro-frontend Host               | 承载系统管理 UI 与模块 UI 扩展的统一外壳，提供路由隔离、命令通道与事件总线（见 5.5）。          |
| 声明式 UI   | Declarative UI                              | 通过 JSON/YAML 描述 UI；UI Host 仅渲染描述，不执行模块代码。                                    |
| micro-app   | Micro App / Micro-frontend                  | 以可执行前端代码交付的模块 UI；必须受信并受能力边界限制。                                       |
| 设置存储    | Settings Store                              | 保存模块级/工作流级配置（JSON 可序列化），供 UI 与运行时读取。                                  |
| 能力        | Capability                                  | 对环境或 UI 扩展可执行动作的抽象（例如 `page`、`http`、`files`）。                              |
| 配额        | Quota                                       | 对环境实例数/租约数/并发等资源的上限控制。                                                      |
| 降级        | Fallback                                    | 当模块 UI 或能力不可用时回退到通用页面/通用能力的策略。                                         |

## A.2 对象字典（Object Dictionary）

### A.2.1 标识与命名

| 字段/标识      | 类型（建议） | 说明                                                          |
| -------------- | ------------ | ------------------------------------------------------------- |
| module_name    | string       | 模块名（全局唯一）。                                          |
| workflow_name  | string       | 工作流名（模块内唯一）。                                      |
| task_name      | string       | 任务名（模块内唯一）。                                        |
| fq_task_id     | string       | 三段式全局标识：`{module_name}/{workflow_name}/{task_name}`。 |
| env_id         | int / string | 运行环境实例标识。                                            |
| lease_id       | string       | 环境租约标识。                                                |
| task_run_id    | string       | 一次任务/工作流运行实例标识，用于日志、事件与排障关联。       |
| correlation_id | string       | 跨组件调用链路关联标识（UI↔Core、Core↔Ops 等）。              |

### A.2.2 常用状态枚举（示例）

| 名称         | 取值示例                                       | 说明                       |
| ------------ | ---------------------------------------------- | -------------------------- |
| module_state | enabled/disabled/incompatible/invalid          | 模块在 Registry 中的状态。 |
| env_state    | CREATING/READY/BUSY/UNHEALTHY/TERMINATING/DEAD | 环境实例生命周期状态。     |
| ui_type      | none/declarative/micro_app                     | 模块 UI 扩展类型。         |
