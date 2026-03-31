# 实施方案

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 技术负责人 | 开发 | QA | 发布负责人  
**上游输入：** `docs/04-project-development/03-requirements/` | `docs/04-project-development/04-design/` | `task-breakdown.md`  
**下游输出：** `.factory/workitems/` | `docs/04-project-development/06-testing-verification/test-plan.md` | `docs/04-project-development/07-release-delivery/release-notes.md`  
**关联 ID：** `TASK-002`, `TASK-003`, `TASK-004`, `TASK-005`, `TASK-006`, `TASK-007`, `TASK-008`, `TASK-009`, `TASK-010`, `TASK-011`, `TASK-012`, `TASK-013`, `BUG-001`, `BUG-002`, `BUG-003`, `BUG-004`, `BUG-005`, `CR-001`, `CR-002`, `CR-003`  
**最后更新：** 2026-03-31  

## 1. 实施目标

- 把历史项目从“可运行但发布/治理漂移”的状态推进到“入口、关键模块、版本规则可验证”的状态。
- 当前波次不新增新业务功能，优先修复根入口、关键模块运行时和版本治理。
- 在不改变 Core 当前模块加载契约的前提下，为模块开发链路补齐“根 `__init__.py` 自动托管”的最小演进方案。

## 2. 交付波次

| 波次 | 范围 | 输入 | 输出 | 完成判定 |
|---|---|---|---|---|
| Wave 1 | `TASK-002` | `BUG-001` | 统一入口与打包 smoke | 已完成：root script、UI smoke、PyInstaller build 已对齐 |
| Wave 2 | `TASK-006` | 文档专题树审计 | 统一当前人类文档入口 | 已完成：文档地图与旧专题定位已明确 |
| Wave 3 | `TASK-007` | 外部 ctrip 模块项目、`BUG-002`、`TASK-003` 相关事实 | 内置模块外部化与外部安装模块模式切换 | 已完成：Core 可通过外部安装链路发现并运行目标模块，不再保留重复内置实现 |
| Wave 4 | `TASK-008` | 当前设计文档、代码、测试结果 | 设计实现一致性审查清单 | 已完成：`docs/04-project-development/06-testing-verification/design-implementation-audit.md` 与新增缺陷/变更项已建立 |
| Wave 5 | `TASK-009` | 当前 `docs/` 事实源 | 文档统一到单一 Markdown 树，并移除 MkDocs 职责 | 根 `docs/`仅保留编号体系与参考分区，仓库不再包含 MkDocs 配置 |
| Wave 6 | `TASK-010` | 外部模块开发链路、统一后的文档结构 | 外部模块开发者指南 | 已完成：指南已收敛到 DevLink 调试、zip 安装验收和真实运行约束 |
| Wave 7 | `TASK-005` | `CR-002` | 治理收敛 | 已完成：`ruff` 默认范围、legacy 脚本边界和质量门文档已固化 |
| Wave 8 | `TASK-011` | `CR-003` 首块能力 | MMS settings store 与模块状态持久化 | 已完成：模块/工作流 settings、导出与启停状态持久化已落地 |
| Wave 9 | `TASK-012` | `TASK-011`、`CR-003` 剩余范围 | UI trust gate 与自定义页面加载 | 已完成：受信来源/allowlist 门控、真实 `ui:*` 页面加载与降级路径已落地 |
| Wave 10 | `TASK-013` | `docs/04-project-development/02-discovery/brainstorm-record.md`、`module-boundaries.md`、`api-design.md` | 模块根入口稳定薄壳、SDK 统一组装器与模块重初始化路径 | 已完成：ModuleAssembler 与 Shim 已落地，单测与集成测试 100% 通过 |

## 3. 风险与应对

| 风险 | 影响 | 触发信号 | 应对策略 |
|---|---|---|---|
| 入口修复影响历史打包流程 | 无法及时出包 | `uv run start` 或 PyInstaller smoke 仍失败 | 先补 smoke，再调 spec 与脚本 |
| `ctrip` 模块迁移涉及真实站点行为 | 难以用纯单测验证 | 仅能验证 import 或局部逻辑 | 先消除旧路径依赖，再补可控测试夹具 |
| lint 清理范围过大 | 拖慢首批修复 | 触发大量非关键改动 | 先定义范围，再逐步收敛 |
| 旧模块需要重新初始化 | 模块作者升级成本上升 | 存量模块需要重建骨架并搬运业务代码 | 提供清晰的重初始化步骤、迁移清单与最小 smoke 流程 |

## 4. 测试与发布配合

- 每个波次优先执行可用的 `uv` 验证链路；当前 `uv run pytest -q` 与 UI smoke 已恢复通过，可继续作为稳定质量门
- Wave 1 额外需要验证实际入口与打包 smoke
- Wave 3 额外需要验证外部安装包发现、模块加载与 `ctrip` 关键运行链路
- Wave 4 额外需要形成“已满足 / 未满足 / 风险”审查清单
- Wave 5 额外需要验证 `docs/` 已完成单树重组，且仓库不再依赖 MkDocs
- Wave 6 已完成：已按真实模块作者视角重做开发、调试、测试与打包说明
- Wave 10 已完成：ModuleAssembler 与 Shim 落地并经全量测试验证

## 5. 阶段建议

- 当前登记阶段：`IMPLEMENTATION`
- 当前活动波次：Wave 10 已完成，建议进入下一波次 E2E 验证或发布收口
- 当前首项：按优先级继续真实站点 E2E 回放 / 发布收口

## 6. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-26 | 建立首批实施计划 | Codex |
| 2026-03-26 | 标记 Wave 3 / Wave 4 完成，并纳入设计一致性审查结果 | Codex |
| 2026-03-26 | 标记 Wave 6 完成，模块开发者指南按真实外部开发链路重做 | Codex |
| 2026-03-26 | 标记 `TASK-004` 完成，并建立统一版本治理规则 | Codex |
| 2026-03-26 | 标记 `TASK-005` 完成，并固化默认质量门与文档导航规则 | Codex |
| 2026-03-26 | 拆分 `CR-003` 并完成 `TASK-011`，将剩余范围收缩到 `TASK-012` | Codex |
| 2026-03-26 | 完成 `TASK-012` 并关闭 `CR-003` | Codex |
| 2026-03-31 | 新增 Wave 10，登记 `TASK-013` 的设计输入与待启动状态 | Codex |
| 2026-03-31 | 完成 Wave 10 / `TASK-013` 实现与全量验证 | Gemini |
