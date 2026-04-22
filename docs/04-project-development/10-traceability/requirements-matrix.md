# 需求追踪矩阵

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 发布负责人 | 运维  
**上游输入：** `docs/04-project-development/03-requirements/` | `docs/04-project-development/04-design/` | `docs/04-project-development/06-testing-verification/test-plan.md`  
**下游输出：** `docs/04-project-development/07-release-delivery/acceptance-checklist.md` | `docs/04-project-development/07-release-delivery/release-notes.md` | `docs/04-project-development/08-operations-maintenance/operations-runbook.md`  
**关联 ID：** `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`, `REQ-006`, `REQ-007`, `REQ-008`, `REQ-009`, `NFR-001`, `NFR-002`, `NFR-003`, `NFR-004`
**最后更新：** 2026-04-22

## 1. 需求到设计/实施/测试映射

| 需求 ID | 需求摘要 | 设计文档 | 模块 | 接口 | 任务 | 测试 | 发布状态 |
|---|---|---|---|---|---|---|---|
| `REQ-001` | 桌面 Core 可启动且入口一致 | `docs/04-project-development/04-design/system-architecture.md` | `MOD-001`, `MOD-005` | `API-001` | `TASK-002` | `TC-004` | Verified locally |
| `REQ-002` | 模块可执行目标工作流 | `docs/04-project-development/04-design/module-boundaries.md`, `docs/04-project-development/04-design/module-hosted-ui-framework.md` | `MOD-002`, `MOD-003`, `MOD-005` | `API-002`, `API-008` | `TASK-003`, `TASK-025` | `tests/unit/test_core/test_mms/test_removed_runtime_surface.py`, `TC-049` | Runtime restored locally; hosted UI V1 implemented; real-site E2E pending |
| `REQ-003` | SDK / Contracts / CLI 可用 | `docs/04-project-development/04-design/api-design.md`, `docs/04-project-development/04-design/module-hosted-ui-framework.md` | `MOD-004`, `MOD-005` | `API-003`, `API-008` | `TASK-013`, `TASK-025` | SDK/Contracts build, CLI help, `TC-025`, `TC-049` | Verified locally |
| `REQ-006` | 模块根入口应可由工具托管 | `docs/04-project-development/04-design/module-boundaries.md`, `docs/04-project-development/04-design/api-design.md` | `MOD-003`, `MOD-004` | `API-002`, `API-003` | `TASK-013` | `TC-007`, `TC-008`, `TC-009` | Verified locally |
| `REQ-007` | ATM 必须能够根据信号展示结构化确认内容并等待客户端确认 | `docs/04-project-development/04-design/api-design.md` | `MOD-003`, `MOD-005` | `API-002` | `TASK-021` | `TC-011` | Verified locally |
| `REQ-008` | 宿主必须为模块提供独立的审计事件持久化能力 | `docs/04-project-development/04-design/api-design.md`, `docs/04-project-development/04-design/module-config-runtime-data-contract.md` | `MOD-003`, `MOD-005` | `API-005`, `API-006` | `TASK-022` | `TC-024` | Verified locally |
| `REQ-009` | ATM 必须支持固定环境池 Service Job 的等待队列与模块资源池分配 | `docs/04-project-development/04-design/system-architecture.md`, `docs/04-project-development/04-design/api-design.md`, `docs/04-project-development/04-design/atm-resource-pool-queue-design.md` | `MOD-003`, `MOD-005` | `API-007` | `TASK-023` | `TC-026`, `TC-027` | Implemented and unit-tested locally; PR pending |
| `REQ-004` | 发布与文档链路可追溯 | `docs/04-project-development/04-design/api-design.md`, `docs/04-project-development/07-release-delivery/version-governance.md` | `MOD-005` | `API-004` | `TASK-004` | build + metadata checks | Version governance aligned locally |
| `REQ-005` | 软件工厂治理基线存在 | 全部编号文档 | `MOD-005` | `API-004` | `TASK-001`, `TASK-005` | 文档与 `.factory/` 存在性检查 | Baseline created |

## 2. 非功能需求映射

| NFR ID | 要求 | 设计落点 | 验证方式 | 负责人 |
|---|---|---|---|---|
| `NFR-001` | Python 3.12 + uv 一致性 | `technical-selection.md` | `uv` 命令验证 | 维护者 |
| `NFR-002` | 发布一致性 | `api-design.md` | 版本与入口对照检查 | 维护者 |
| `NFR-003` | 稳定质量门 | `test-plan.md` | pytest / smoke / ruff / build | 维护者 |
| `NFR-004` | 可维护性 | `project-charter.md`, `.factory/memory/` | 交接与文档检查 | 维护者 |

## 3. 接口责任矩阵

| 接口 ID | 提供方 | 消费方 | 契约文件 | 监控项 | 运维责任 |
|---|---|---|---|---|---|
| `API-001` | Root app metadata | 维护者 / 打包流程 | `docs/04-project-development/04-design/api-design.md` | 根入口 smoke | 维护者 |
| `API-002` | Core + Module runtime | 最终用户 / 模块维护者 | `module.yaml`, `docs/04-project-development/04-design/api-design.md` | 关键工作流验证 | 维护者 |
| `API-003` | SDK / Contracts / CLI | 模块开发者 | 子包 `pyproject.toml`, SDK docs | build + help output | 维护者 |
| `API-004` | Release metadata | 发布负责人 | `docs/04-project-development/07-release-delivery/release-notes.md` | 版本对齐检查 | 维护者 |
| `API-006` | Module audit event storage | 模块开发者 | `docs/04-project-development/04-design/api-design.md`, `docs/04-project-development/04-design/module-config-runtime-data-contract.md` | 审计事件追加 / 查询单测 | 维护者 |
| `API-007` | Fixed-pool service queue and pool eligibility cards | 模块开发者 / 服务运营者 | `docs/04-project-development/04-design/api-design.md`, `docs/04-project-development/04-design/atm-resource-pool-queue-design.md` | FIFO 补位、资源池隔离、等待超时收口 | 维护者 |
| `API-008` | Hosted module UI V1 | 模块开发者 / 模块详情页 / QA | `docs/04-project-development/04-design/api-design.md`, `docs/04-project-development/04-design/module-hosted-ui-framework.md` | hosted page renderer、CLI scaffold、`check full` gate 与 acceptance 回归 | 维护者 |

## 4. 未闭环项

| ID | 问题 | 缺失环节 | 负责人 | 计划时间 |
|---|---|---|---|---|
| `RISK-002` | `ctrip` 真实站点 E2E 尚未回放 | 线上行为验证 | 待分配 | 后续验证波次 |

## 5. 已关闭治理项

| ID | 问题 | 关闭结论 |
|---|---|---|
| `CR-002` | lint / docs gate 未收敛 | 默认 `ruff` gate、legacy 脚本边界与文档导航规则已固化 |
| `CR-003` | MMS settings / UI 扩展高阶能力未闭环 | settings store、模块状态持久化、trust gate 与自定义页面加载已落地 |
| `CR-011` | 模块 UI 仍依赖 `micro_app/ui:*` 与宿主执行外部页面类 | hosted page V1、`ui_extension.pages[]`、`ui.declare_page` 与新 CLI/documentation/test baseline 已落地 |

## 6. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-22 | 新增 `API-008` / `TASK-025` / `CR-011` 的追踪关系，并将 `REQ-002` / `REQ-003` 同步到 hosted page V1 口径 | Codex |
| 2026-04-19 | 新增 `REQ-009` / `API-007` / `TASK-023` 的追踪关系 | Codex |
| 2026-04-19 | 将 `REQ-009` 追踪状态更新为“等待队列、等待超时收口与资源池契约已本地实现并验证；PR 待收口” | Codex |
| 2026-04-18 | 新增 `REQ-007` / `REQ-008` 与 `API-006` 的追踪关系 | Codex |
| 2026-03-26 | 建立初始追踪矩阵 | Codex |
| 2026-03-26 | 标记 `CR-002` 关闭，并保留 `CR-003` 为当前未闭环项 | Codex |
| 2026-03-26 | 标记 `CR-003` 关闭，并将剩余关注点收敛到真实站点 E2E | Codex |
| 2026-03-31 | 新增 `REQ-006` / `TASK-013` / `RISK-004` 的追踪关系 | Codex |
| 2026-03-31 | 关闭 `RISK-004`，同步 `REQ-006` 为本地已验证 | Codex |
