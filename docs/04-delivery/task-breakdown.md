# 任务分解

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** Tech Lead | Dev | QA  
**上游输入：** `wbs.md` | `docs/02-requirements/` | `docs/03-solution/`  
**下游输出：** `.factory/workitems/` | `implementation-plan.md`  
**关联 ID：** `TASK-001`, `TASK-002`, `TASK-003`, `TASK-004`, `TASK-005`, `TASK-006`, `TASK-007`, `TASK-008`, `TASK-009`, `TASK-010`, `TASK-011`, `TASK-012`  
**最后更新：** 2026-03-26  

## 1. 任务清单

| `TASK` | 状态 | 内容 | 对应需求 | 前置依赖 | 估算（人/天） |
|---|---|---|---|---|---|
| `TASK-001` | DONE | 历史项目工厂基线接管 | `REQ-005` | 无 | 1.0 |
| `TASK-002` | DONE | 修复根应用入口与 PyInstaller 规格，并补 smoke 验证 | `REQ-001`, `REQ-004` | `BUG-001` | 1.0 |
| `TASK-003` | DONE | 恢复 `ctrip labor_workflow` 的当前运行时实现 | `REQ-002` | `BUG-002` | 2.0 |
| `TASK-004` | DONE | 统一版本事实源、release notes 与文档口径 | `REQ-004` | `CR-001` | 1.0 |
| `TASK-005` | DONE | 收敛 ruff / docs gate，划清 legacy 脚本边界 | `REQ-005`, `NFR-003` | `CR-002` | 1.0 |
| `TASK-006` | DONE | 统一旧文档到当前人类文档体系 | `REQ-005` | `TASK-002` | 1.0 |
| `TASK-007` | DONE | 删除内部组件并切换到外部安装模块模式 | `REQ-002` | `TASK-006` | 2.0 |
| `TASK-008` | DONE | 审查设计与开发实现的一致性并输出问题清单 | `REQ-002`, `REQ-004`, `REQ-005` | `TASK-007` | 1.5 |
| `TASK-009` | DONE | 统一 `docs/` 文档体系并移除 MkDocs 静态站职责 | `REQ-005` | `TASK-006` | 1.0 |
| `TASK-010` | DONE | 重做模块开发者指南 | `REQ-003`, `REQ-005` | `TASK-007`, `TASK-009` | 1.5 |
| `TASK-011` | DONE | 建立 MMS settings store 与模块状态持久化 | `REQ-002`, `REQ-005` | `CR-003` | 1.0 |
| `TASK-012` | DONE | 补齐 MMS trust gate 与自定义页面加载 | `REQ-002`, `REQ-005` | `TASK-011` | 1.0 |

## 2. 首批执行顺序

1. 当前编号任务已全部完成，后续进入真实站点 E2E 或发布收口阶段

## 3. 说明

- `TASK-002` 已完成，根入口与打包 smoke 已对齐。
- `TASK-006` 已完成，旧专题文档已被收敛到当前人类文档体系入口之下。
- 当前主线顺序按用户确认执行：已完成外部化、一致性审查、文档统一、MkDocs 移除与模块开发者指南重做，下一步转入治理项收口。
- `TASK-007` 以 `TASK-006` 完成后的当前文档体系为入口，并在实施时吸收 `TASK-003` 中与 `BUG-002` 直接相关的运行时修复，避免把已知失效能力迁移到外部仓库。
- `TASK-004` 与 `TASK-005` 已完成；当前编号任务主线已闭环。
- `CR-003` 已拆分为 `TASK-011` 与 `TASK-012`，且两项均已完成；当前编号任务主线再次闭环。
