# 需求校验

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 发布负责人  
**上游输入：** `prd.md` | `requirements-analysis.md` | 本地验证结果  
**下游输出：** `docs/04-project-development/04-design/` | `docs/04-project-development/05-development-process/` | `.factory/process/stage-check-report.md`  
**关联 ID：** `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`, `REQ-006`, `REQ-007`, `REQ-008`, `REQ-009`, `NFR-001`, `NFR-002`, `NFR-003`, `NFR-004`
**最后更新：** 2026-04-30

## 1. 校验清单

| ID | 校验内容 | 结果 | 证据 |
|---|---|---|---|
| `REQ-001` | 是否存在真实可导入的 UI 入口 | 通过 | `from src.ui.app import main` 成功 |
| `REQ-001` | 是否存在可直接使用的 workspace 启动入口 | 通过 | `uv run python -m src.ui.app` 可直接启动 `packages/crawler4j` 中的真实入口 |
| `REQ-001` | 打包规格是否与真实入口一致 | 通过 | 修正后的 `packages/crawler4j/crawler4j.spec` 已成功 PyInstaller 出包 |
| `REQ-002` | 登录工作流是否具备基础可执行形态 | 通过 | `tests/unit/test_core/test_mms/test_removed_runtime_surface.py` 覆盖登录路径 |
| `REQ-002` | 完整 labor_workflow 是否已脱离旧依赖 | 通过 | 旧 `src.automation.*` 兼容包已移除；手动创建环境与模块执行统一走 MMS + ModuleAssembler 正式链路 |
| `REQ-003` | SDK / Contracts 是否可本地 build | 通过 | 子包 build 成功 |
| `REQ-003` | SDK CLI 是否可运行帮助页 | 通过 | `uv run python -m crawler4j_sdk.cli.commands --help` |
| `REQ-006` | 模块根入口是否已收敛为工具托管的稳定薄壳 | 通过 | `ModuleAssembler` 与 `Shim` 落地，经 `test_assembler.py` 与 `test_cli_scaffold.py` 验证通过 |
| `REQ-007` | 等待确认信号是否可持久化并重新读取 | 通过 | `test_repository_roundtrip_preserves_task_signal` |
| `REQ-007` | ATM 详情页是否会展示结构化确认面板 | 通过 | `test_task_confirmation_dialog_renders_structured_payload`、`test_job_detail_dialog_presents_waiting_confirmation_task` |
| `REQ-007` | 确认面板是否回调既有确认服务 | 通过 | `test_job_detail_dialog_confirms_waiting_task_after_dialog_accept` |
| `REQ-008` | 宿主是否为模块提供独立的审计事件存储表 | 通过 | `test_module_data_store_appends_and_queries_audit_events` |
| `REQ-008` | `ctx.db` 是否暴露独立审计事件 API | 通过 | `test_runtime_tools_register_expected_surface`、`test_runtime_ctx_db_audit_uses_independent_audit_table`、`test_task_context_db_supports_audit_event_plan` |
| `REQ-008` | 模块清理时是否同时清理快照数据、审计事件和数据表 schema | 通过 | `test_module_data_store_clear_module_data_removes_data_db_rows_only` |
| `REQ-009` | 是否已存在正式的需求、设计与工作项挂接 | 通过 | `prd.md`、`atm-resource-pool-queue-design.md`、`implementation-plan.md`、`TASK-023` |
| `REQ-009` | 环境候选 Service Job 是否已具备“运行中 + 等待中 = 目标并发”的正式行为 | 通过 | 当前已由本地单测验证 `@env_candidates` 候选纯函数、等待语义、FIFO 补位、模块环境授权、租约后复核、等待席位自动超时收口与旧 `resource_pool/selector_name/env_selector` 字段拒绝 |
| `REQ-004` | 发布链路版本信号是否一致 | 通过 | 根应用工作区版本、运行时版本服务、最近正式 tag 与 release 文档关系已明确 |
| `REQ-005` | 工厂控制面是否已补齐 | 通过 | 本次已新增 `AGENTS.md`、`GEMINI.md`、`.factory/`、编号文档 |
| `NFR-001` | 是否统一使用 `uv` | 通过 | 现有运行方式与本次验证均基于 `uv` |
| `NFR-002` | 入口与版本一致性 | 通过 | `BUG-001` 与 `CR-001` 已关闭 |
| `NFR-003` | 质量门是否稳定 | 通过 | 测试、UI smoke、build 与默认 `ruff` gate 当前均通过 |
| `NFR-004` | 是否具备可交接基线 | 通过 | 本次已完成 |

## 2. 阶段判断

### 已满足

- 基于当前仓库事实重建 requirements / solution / delivery 最小文档包
- 明确首批工作项
- 明确当前已验证能力与未关闭风险
- `REQ-006` 模块入口薄壳化已完成实现与验证

### 未满足

- `ctrip` 真实站点 E2E 仍未形成正式验证结论
- `REQ-009` 已完成本地实现与单测验证；当前剩余工作是 PR 收口、真实业务模块接入和更高层验证

## 3. 建议结论

- 当前项目已进入软件工厂 `IMPLEMENTATION`
- `TASK-013`、`TASK-021`、`TASK-022` 已关闭，相关契约已进入回归维护阶段
- `TASK-023` 已完成本地实现，下一步应先完成 PR 收口，再继续真实站点 E2E 与发布收口
- `UAT-028` 已进入当前本地实现；后续只需补更高层集成与真实业务接入验证

## 4. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-30 | 同步 `REQ-009` 为“环境候选纯函数、等待队列、FIFO 补位、模块环境授权与等待超时收口已本地实现并验证”；资源池同步方案退出正式契约 | Codex |
| 2026-04-19 | 历史记录：曾同步 `REQ-009` 为固定资源池等待队列；该口径已被 2026-04-30 环境候选方案替代 | Codex |
| 2026-04-18 | 新增 `REQ-008` / `TASK-022` 的模块审计事件独立存储验证结论 | Codex |
| 2026-03-26 | 初始需求校验结论 | Codex |
| 2026-03-26 | 同步 `TASK-005` 完成后的质量门结论 | Codex |
| 2026-03-31 | 新增 `REQ-006` 待实现校验项与 `TASK-013` 设计状态 | Codex |
| 2026-03-31 | 同步 `TASK-013` 完成后的验证结论 | Gemini |
| 2026-04-16 | 新增 `REQ-007` / `TASK-021` 的结构化确认面板与客户端确认闭环验证结论 | Codex |
