# 工作分解结构（WBS）

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** Tech Lead | Dev | QA | 项目经理  
**上游输入：** `docs/02-requirements/` | `docs/03-solution/`  
**下游输出：** `task-breakdown.md` | `implementation-plan.md` | `.factory/workitems/`  
**关联 ID：** `TASK-001`, `TASK-002`, `TASK-003`, `TASK-004`, `TASK-005`, `TASK-006`, `TASK-007`, `TASK-008`, `TASK-009`, `TASK-010`  
**最后更新：** 2026-03-26  

## WBS-1 工厂基线接管

- `TASK-001` 建立 `AGENTS.md`、`GEMINI.md`、编号文档、`.factory/`

## WBS-2 根应用运行与打包修复

- `BUG-001` 识别根入口与 PyInstaller 规格漂移
- `TASK-002` 修复根脚本入口、PyInstaller 规格与 smoke 验证

## WBS-3 `ctrip` 模块运行时修复

- `BUG-002` 识别 `labor_workflow` 对旧 `src.automation.*` 的依赖
- `TASK-003` 将完整工作流迁回当前模块运行时

## WBS-4 版本与发布治理

- `CR-001` 统一版本事实源、发布说明与 Tag 语义
- `TASK-004` 实施版本与 release 规则收敛

## WBS-5 质量门收敛

- `CR-002` 明确 lint 范围、遗留脚本策略与文档导航治理
- `TASK-005` 建立可执行的 lint / docs gate 基线

## WBS-6 文档体系统一

- `TASK-006` 统一旧文档到当前人类文档体系

## WBS-7 外部模块化

- `TASK-007` 删除内部组件并切换到外部开发模式
- 本阶段先吸收 `BUG-002` / `TASK-003` 中与 `ctrip` 当前运行时恢复直接相关的内容

## WBS-8 设计实现一致性审查

- `TASK-008` 审查设计与开发实现的一致性并输出问题清单

## WBS-9 文档统一与静态站移除

- `TASK-009` 统一 `docs/` 文档体系并移除 MkDocs 静态站职责

## WBS-10 模块开发者指南重做

- `TASK-010` 重做模块开发者指南
