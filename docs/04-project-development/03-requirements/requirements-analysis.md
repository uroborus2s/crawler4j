# 需求分析

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 发布负责人  
**上游输入：** `prd.md` | `current-state-analysis.md`  
**下游输出：** `requirements-verification.md` | `docs/04-project-development/04-design/` | `docs/04-project-development/05-development-process/`  
**关联 ID：** `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`, `REQ-006`, `REQ-007`, `REQ-008`, `REQ-009`, `BUG-001`, `CR-001`, `CR-002`, `CR-004`, `CR-008`, `CR-009`
**最后更新：** 2026-04-19

## 1. 需求实现现状判断

| ID | 摘要 | 当前状态 | 依据 |
|---|---|---|---|
| `REQ-001` | 桌面 Core 可启动且入口一致 | 满足 | `start` 脚本已对齐 `src.ui.app:main`，headless smoke 与 PyInstaller 出包通过 |
| `REQ-002` | 模块可执行目标工作流 | 基本满足 | 登录工作流可执行，`labor_workflow` 已恢复基础运行时兼容，但真实站点 E2E 未验证 |
| `REQ-003` | SDK / Contracts / CLI 可用 | 基本满足 | SDK/Contracts build 成功，CLI help 可运行 |
| `REQ-006` | 模块根入口可由工具托管 | 满足 | 根 `__init__.py` 已收敛为稳定薄壳，`ModuleAssembler` 负责默认发现与分发，旧模块升级路径统一为按最新模板重新初始化 |
| `REQ-007` | 信号驱动的结构化确认面板 | 本次完成 | `TaskSignal` 已持久化到任务快照，ATM 详情页可按 `payload.confirmation` 弹出确认面板，并回调既有确认服务 |
| `REQ-008` | 模块审计事件独立存储 | 本次完成 | 宿主已新增 `module_audit_events` 与 `db.append_event` / `db.query_events`，快照 dataset 继续保留原语义 |
| `REQ-009` | 固定环境池 Service Job 等待队列 | 本次完成 | 当前宿主已实现固定环境池 Service Job 的 `PENDING` 等待、FIFO 补位、资源池隔离、等待席位自动超时收口，以及资源池资格 helper / REM 筛选入口 |
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

- 根 `__init__.py` 已固定为托管薄壳，运行时组装逻辑收敛到 SDK 的 `ModuleAssembler`。
- 默认工作流解析顺序已经稳定为 `context.runtime["workflow"] -> module_runtime.DEFAULT_WORKFLOW -> module.yaml.workflows[0].name`。
- `module_runtime.py` 已收敛为标准模块文件，默认脚手架会生成；环境选择能力通过其中的 `@env_selector(...)` 回调声明，ATM“选择环境”模式不再接受规则树。
- 本轮不再把“兼容旧模块模板”作为目标，旧模块升级路径统一为按最新脚手架重新初始化。

### `REQ-007`

- 当前 `TaskSignal.wait_for_confirmation` 只解决“让任务停住”，没有解决“客户端应该展示什么、从哪里读、如何确认”。
- 原有缺口集中在三层：任务表没有持久化 signal payload、事件总线没有信号专用事件、ATM 详情页没有结构化确认面板。
- 最小可落地方案是保持 `TaskSignal.payload` 为通用字典，但把 `payload.confirmation` 固化为正式 UI 展示协议，同时保留对旧 payload 的键值回退显示。
- 继续复用 `confirm_task_success/confirm_task_failure` 作为唯一确认入口，可以避免再引入一条新的任务收尾路径。

### `REQ-008`

- 现有 `db.list_records` / `db.replace_records` 与 `module_datasets.records_json` 天然是“当前快照”模型，不适合承载 append-only 的审计事件。
- 如果模块把 `account_events` 这类历史事件继续当普通 dataset 全量覆盖写回，运行时间越长，单条 `records_json` 越大，写放大和并发覆盖风险越高。
- 本轮最小可落地方案不是改写快照接口，而是补一条平行的事件通道：`module_audit_events` + `db.append_event` / `db.query_events`。
- 当前实现刻意保持边界收敛：快照型数据继续服务 `core:data_table` 和当前列表型 UI，事件型数据只提供追加与查询，不在本轮引入 retention / archive 与通用查询页面。

### `REQ-009`

- 当前 V1 已把固定环境池 Service Job 中“当前轮没命中环境”的核心语义从硬失败收敛为等待，并由宿主按 `wait_timeout` 对长期等待席位做自动超时收口。
- 当目标并发大于当前可用环境数时，宿主现已能把容量不足收敛为稳定候场队列，而不是制造失败风暴和反复补单。
- 当前实现边界是：宿主维护等待席位，模块只维护资源池资格卡片，宿主按 FIFO 和容量变化补位。
- 该需求的核心不是“再起更多模块实例”，而是把并发目标收敛为服务席位，把资源不足收敛为“等待环境”这一条正式业务状态。
- 当前 REM 分配入口已经收口为 `EnvironmentManager.list_allocatable_envs(module_name, pool_name)`；它只从“当前模块 + 当前资源池 + `eligible=true` + `READY` + 未租约占用”的环境集合里挑选候选。
- 黑号/封禁场景的当前正式收口是“先用 `mark_resource_pool_ineligible(...)` 停发号，再按需 `destroy_env`”；环境记录删除后，对应 `env_metadata` 会随外键级联自动清理。
- 这轮不应让宿主直接读取模块私有业务表；更稳的边界是模块通过 SDK helper `bind_resource_pool(...)`、`mark_resource_pool_eligible(...)`、`mark_resource_pool_ineligible(...)`、`remove_resource_pool(...)`、`replace_resource_pool_snapshot(...)` 把资格快照同步到宿主 `env_metadata`。

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
| P1 | `REQ-009` / `TASK-023` 固定环境池 Service Job 等待队列 | 影响固定环境池服务的稳定性、保活并发语义与宿主/模块责任边界 |

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
