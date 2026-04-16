# 需求校验

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 发布负责人  
**上游输入：** `prd.md` | `requirements-analysis.md` | 本地验证结果  
**下游输出：** `docs/04-project-development/04-design/` | `docs/04-project-development/05-development-process/` | `.factory/process/stage-check-report.md`  
**关联 ID：** `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`, `REQ-006`, `REQ-007`, `NFR-001`, `NFR-002`, `NFR-003`, `NFR-004`  
**最后更新：** 2026-04-16  

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

## 3. 建议结论

- 当前项目已进入软件工厂 `IMPLEMENTATION`
- `TASK-013` 已关闭，建议进入下一波次 E2E 验证或发布收口
- `TASK-021` 已完成，ATM 信号驱动确认面板与客户端确认闭环已建立，后续仅需按模块场景继续补展示字段

## 4. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-26 | 初始需求校验结论 | Codex |
| 2026-03-26 | 同步 `TASK-005` 完成后的质量门结论 | Codex |
| 2026-03-31 | 新增 `REQ-006` 待实现校验项与 `TASK-013` 设计状态 | Codex |
| 2026-03-31 | 同步 `TASK-013` 完成后的验证结论 | Gemini |
| 2026-04-16 | 新增 `REQ-007` / `TASK-021` 的结构化确认面板与客户端确认闭环验证结论 | Codex |
