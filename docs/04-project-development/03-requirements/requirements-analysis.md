# 需求分析

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 发布负责人  
**上游输入：** `prd.md` | `current-state-analysis.md`  
**下游输出：** `requirements-verification.md` | `docs/04-project-development/04-design/` | `docs/04-project-development/05-development-process/`  
**关联 ID：** `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`, `REQ-006`, `REQ-007`, `REQ-008`, `REQ-009`, `BUG-001`, `CR-001`, `CR-002`, `CR-004`, `CR-008`, `CR-009`
**最后更新：** 2026-04-30

## 1. 需求实现现状判断

| ID | 摘要 | 当前状态 | 依据 |
|---|---|---|---|
| `REQ-001` | 桌面 Core 可启动且入口一致 | 满足 | `start` 脚本已对齐 `src.ui.app:main`，headless smoke 与 PyInstaller 出包通过 |
| `REQ-002` | 模块可执行目标工作流 | 基本满足 | 登录工作流可执行，`labor_workflow` 已恢复基础运行时兼容，但真实站点 E2E 未验证 |
| `REQ-003` | SDK / Contracts / CLI 可用 | 基本满足 | SDK/Contracts build 成功，CLI help 可运行 |
| `REQ-006` | 模块运行能力由 Core 扫描托管 | 满足 | 0.4.0 已切到 `core-native-v2`，运行能力事实源来自 `tasks/`、`workflows/`、`candidates/`、`cleanups/`、`pages/` 等装饰器扫描；旧 `hooks/` 不再是运行契约，旧模块升级路径统一为按最新模板重新初始化 |
| `REQ-007` | 信号驱动的结构化确认面板 | 本次完成 | `TaskSignal` 已持久化到任务快照，ATM 详情页可按 `payload.confirmation` 弹出确认面板，并回调既有确认服务 |
| `REQ-008` | 模块审计事件独立存储 | 本次完成 | 宿主已新增 `module_audit_events` 与 `ctx.db.audit(...).append/query`，快照 dataset 继续保留原语义 |
| `REQ-009` | 环境候选 Service Job 等待队列 | 本次完成 | 当前宿主已实现 `@env_candidates` 候选纯函数实时求值、`PENDING` 等待、FIFO 补位、模块环境授权、租约后复核和等待席位自动超时收口；资源池同步方案已退出正式契约 |
| `REQ-004` | 发布与文档链路可追溯 | 满足 | 根应用工作区版本、运行时版本服务、最近正式 tag 与 release 文档口径已明确分层 |
| `REQ-005` | 软件工厂治理基线存在 | 本次建立 | `AGENTS.md`、`GEMINI.md`、`.factory/`、编号文档已新增 |

## 2. 需求影响分析

### `REQ-001`

- 该需求已在本轮实现中闭环：声明入口、headless smoke、PyInstaller 出包已经对齐。
- 后续仍需保留这组验证，避免入口再次漂移。

### `REQ-002`

- `ctrip` 是仓库中最像真实业务模块的 builtin module。
- 目前 `modules/ctrip/__init__.py` 已显式写出迁移期 fallback 行为，说明维护者已经意识到完整链路未完成。
- 因此该问题不属于“文档与实现不一致”，而是“实现处于兼容性退化状态”。

### `REQ-003`

- SDK/Contracts 是当前仓库最健康的分发链路。
- 因为 SDK CLI 已能提供脚手架入口，所以这部分更适合作为后续规范化的正向样板。

### `REQ-006`

- 0.4.0 已切到 `core-native-v2`，运行能力事实源来自装饰器扫描和 manifest lock，不再由根 `__init__.py`、`ModuleAssembler` 或 `module_runtime.py` 承载。
- 默认工作流解析顺序稳定为 `ctx.runtime["workflow"] -> 单 workflow 自动选择 -> main_workflow`。
- 环境选择能力通过 `candidates/*.py` 中的 `@env_candidates` 同步纯函数声明；ATM“选择环境”模式只接受固定 `env_id` 或候选函数名。
- 本轮不再把“兼容旧模块模板”作为目标，旧模块升级路径统一为按 0.4.0 脚手架重新初始化。

### `REQ-007`

- 当前 `TaskSignal.wait_for_confirmation` 只解决“让任务停住”，没有解决“客户端应该展示什么、从哪里读、如何确认”。
- 原有缺口集中在三层：任务表没有持久化 signal payload、事件总线没有信号专用事件、ATM 详情页没有结构化确认面板。
- 最小可落地方案是保持 `TaskSignal.payload` 为通用字典，但把 `payload.confirmation` 固化为正式 UI 展示协议，同时保留对旧 payload 的键值回退显示。
- 继续复用 `confirm_task_success/confirm_task_failure` 作为唯一确认入口，可以避免再引入一条新的任务收尾路径。

### `REQ-008`

- 现有 `db.list_records` / `db.replace_records` 与 `module_datasets` 天然是“当前快照”模型，不适合承载 append-only 的审计事件。
- 即便 `module_datasets` 已改为“一条 record 一行”持久化，只要模块把 `account_events` 这类历史事件继续当普通 dataset 全量覆盖写回，运行时间越长，整包重写成本和并发覆盖风险仍会持续放大。
- 本轮最小可落地方案不是改写快照接口，而是补一条平行的事件通道：`module_audit_events` + `ctx.db.audit(...).append/query`。
- 当前实现刻意保持边界收敛：快照型数据继续服务 `core:data_table` 和当前列表型 UI，事件型数据只提供追加与查询，不在本轮引入 retention / archive 与通用查询页面。

### `REQ-009`

- 当前 0.4.0 已把候选 Service Job 中“当前轮没命中环境”的核心语义从硬失败收敛为等待，并由宿主按 `wait_timeout` 对长期等待席位做自动超时收口。
- 当目标并发大于当前可用候选环境数时，宿主现已能把容量不足收敛为稳定候场队列，而不是制造失败风暴和反复补单。
- 当前实现边界是：宿主维护等待席位、环境授权、租约和 FIFO 补位；模块只维护业务数据表和 `@env_candidates` 候选纯函数。
- 该需求的核心不是“再起更多模块实例”，而是把并发目标收敛为服务席位，把资源不足收敛为“等待环境”这一条正式业务状态。
- 当前 REM 分配入口不再维护模块资源池资格快照；ATM 每次调度通过 MMS 执行当前模块声明的 `@env_candidates` 同步纯函数，并在候选结果上叠加“已绑定当前模块 + `READY` + 浏览器 + 未租约占用”的宿主约束。
- 黑号/封禁、账号注册时间、会员等级等业务状态由模块写入自身数据表，候选函数实时读取这些数据并返回可用 env id 列表或 `EnvCandidates` 链式查询结果；不引入资源池同步工作流。
- 这轮不让宿主读取模块私有业务表，也不让模块同步宿主资源池快照；唯一边界是模块纯函数产出候选集合，宿主负责授权、租约、FIFO 等待与超时收口。

### `REQ-004`

- `CR-001` 已完成：根应用版本事实源、运行时版本读取和最近正式 tag 的关系已经写清。
- SDK / Contracts 继续保留独立版本线，不再要求与根应用共用版本号。

### `REQ-005`

- 工厂基线已经建立，并已开始执行第一轮基于 workitem 的实施。
- 当前阶段应视为 `IMPLEMENTATION`，而不是停留在 `PLAN`。

## 3. 风险与优先级

| 优先级 | 项目 | 原因 |
|---|---|---|
| P1 | `REQ-006` / `TASK-013` 模块根入口自动托管 | 影响模块开发体验、模板稳定性与后续契约演进成本 |
| P1 | `REQ-007` / `TASK-021` 信号驱动结构化确认面板 | 影响人工复核场景可用性、任务可观测性与 ATM/模块契约完整性 |
| P1 | `REQ-008` / `TASK-022` 模块审计事件独立存储 | 影响模块数据契约清晰度、长期运行写放大风险与后续扩展空间 |
| P1 | `REQ-009` / `TASK-023` 环境候选 Service Job 等待队列 | 影响候选环境服务的稳定性、保活并发语义与宿主/模块责任边界 |

## 4. 结论

该仓库当前已经进入实现阶段，但仍不适合直接跳到“继续开发新功能”的节奏。  
更合理的路径是：

1. 以 `IMPLEMENTATION` 作为当前工厂阶段
2. 维持当前默认质量门与文档导航规则
3. 将 `REQ-006` / `TASK-013` 视为已闭环能力，后续只做回归维护
4. 将 `REQ-007` / `TASK-021` 与 `REQ-008` / `TASK-022` 视为已闭环能力，后续只做回归维护与边界补充
5. 将 `REQ-009` / `TASK-023` 视为已完成本地实现：当前下一步是 PR 收口、真实业务模块接入与更高层验证
6. 将 `UAT-028` 视为当前已落地事实，后续只补真实业务模块接入与更高层验证
7. 然后再处理真实站点 E2E 与发布收口阶段
