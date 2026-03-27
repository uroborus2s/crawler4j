# 质量门与文档导航规则

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** Tech Lead | Dev | QA | 发布负责人
**上游输入：** `docs/04-delivery/implementation-plan.md` | `.factory/workitems/implementation/TASK-005-normalize-lint-and-docs-gates.md`
**下游输出：** `.factory/process/quality-check-report.md` | `docs/traceability/document-index.md`
**关联 ID：** `TASK-005`, `CR-002`, `REQ-005`, `NFR-003`
**最后更新：** 2026-03-28

## 1. 目标

- 固化当前仓库可复验的默认质量门
- 明确哪些文件属于持续维护范围，哪些文件仅作为历史调试参考
- 给 `docs/` 的单树导航策略一个正式、稳定的说明

## 2. 默认质量门

| 质量门 | 命令/方式 | 目标 |
|---|---|---|
| 单元/集成测试 | `uv run pytest -q` | 验证当前维护范围内的核心能力、SDK 契约和集成链路 |
| Lint | `uv run ruff check .` | 对维护范围内代码执行静态检查 |
| UI smoke | `uv run python scripts/smoke_test_ui.py` | 验证桌面入口最小可运行链路 |
| 根应用构建 | `uv build --out-dir /tmp/crawler4j-build-check` | 验证根包可产出 wheel/sdist |
| SDK / Contracts 构建 | `cd crawler4j_sdk && uv build` / `cd crawler4j_contracts && uv build` | 验证外部分发物可构建 |

## 3. Ruff 范围规则

当前默认 `ruff` gate 覆盖：

- `src/`
- `crawler4j_sdk/`
- `crawler4j_contracts/`
- `scripts/` 中仍作为维护资产的脚本
- `tests/unit/`、`tests/integration/` 中的常规自动化测试

当前默认 `ruff` gate 不覆盖以下历史人工辅助脚本：

- `tests/analyze_*.py`
- `tests/debug_*.py`
- `tests/manual_*.py`
- `tests/verify_*.py`

这些文件仍保留为排障、人工验证或历史研究资料，但不作为持续集成质量门的一部分。若后续要把其中某个脚本提升为正式自动化资产，应先重构为稳定测试，再移出上述排除规则。

## 4. 文档导航规则

- `docs/index.md` 只暴露三个入口层：`项目过程文档`、`Model 开发指南`、`历史归档`
- `docs/project-process/index.md` 是 Core 维护者入口；模块作者入口是 `docs/08-handover/module-developer-guide/index.md`
- `docs/00-governance/` 到 `docs/07-operations/`、`docs/09-evolution/` 与 `docs/traceability/` 仍是当前正式正文层
- `docs/archive/` 是历史参考层，不是默认事实入口
- 任何包含 Markdown 页面的人类文档目录，都必须提供自己的 `index.md`
- `.obsidian/` 和纯资产目录不属于正式文档入口要求范围
- `docs/08-handover/index.md` 与 `docs/08-handover/user-guide.md` 只保留跨角色接手职责，不再承载旧 Quick Start 或旧用户说明
- 冲突时，以代码、已验证命令结果和当前编号文档为准
- `.factory/` 记录工厂控制面状态；`docs/` 负责面向人的正式说明

## 5. 当前基线结论

截至 2026-03-26，当前仓库的默认质量门结论为：

- `uv run pytest -q`：通过
- `uv run ruff check .`：通过
- `uv run python scripts/smoke_test_ui.py`：通过
- 根包、SDK、Contracts 构建：通过

这意味着当前仓库已经具备一套可复用、可解释的默认开发质量门；后续若新增 gate 或调整范围，应同步更新本文件和 `.factory/process/quality-check-report.md`。
