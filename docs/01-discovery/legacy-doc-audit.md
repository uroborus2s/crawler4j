# 旧文档审计与收敛策略

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 发布负责人 | 文档维护者  
**上游输入：** 现有 `docs/` 专题树 | 当前代码与已验证结果  
**下游输出：** `docs/traceability/document-index.md` | 当前编号人类文档体系 | `TASK-006`  
**关联 ID：** `TASK-006`, `DOC-001`, `DOC-002`, `REQ-005`  
**最后更新：** 2026-03-26  

## 1. 结论先行

crawler4j 当前的人类文档体系以以下目录为正式入口：

- `docs/00-governance/`
- `docs/01-discovery/`
- `docs/02-requirements/`
- `docs/03-solution/`
- `docs/04-delivery/`
- `docs/05-quality/`
- `docs/06-release/`
- `docs/07-operations/`
- `docs/08-handover/`
- `docs/traceability/`

旧专题文档根目录已经并入编号目录下的 `reference-*` 子目录，作为“详细参考层”继续保留，不再作为默认事实入口。

## 2. 目录分层策略

| 目录 | 当前角色 | 处理策略 |
|---|---|---|
| `docs/00-08`, `docs/traceability` | 当前正式人类文档体系 | 作为默认入口，持续演进 |
| `docs/02-requirements/reference-srs/` | 旧需求 / 架构 / 规格细节库 | 保留为深度参考，事实冲突时以后者校准 |
| `docs/03-solution/reference-design/` | 旧技术设计细节库 | 保留为深度参考，逐步吸收核心结论 |
| `docs/05-quality/reference-tests/` | 旧测试设计细节库 | 保留为深度参考，当前测试结论以 `docs/05-quality/` 为准 |
| `docs/08-handover/reference-user-guide/` | 旧用户/运维专题文档 | 暂保留，逐步映射到 `06-08` |
| `docs/08-handover/reference-module-dev/` | 旧模块开发专题文档 | 暂保留，现已由新的模块开发者指南承接主入口 |
| `docs/03-solution/reference-sdk/`, `docs/03-solution/reference-architecture/` | 补充说明层 | 暂保留，按需引用 |

## 3. 当前已识别的主要不一致

| 区域 | 现象 | 当前处理 |
|---|---|---|
| `docs/index.md` | 仍偏旧专题入口，不足以体现当前编号体系 | 本轮改为当前文档门户 |
| `docs/02-requirements/reference-srs/index.md` / `docs/03-solution/reference-design/index.md` / `docs/05-quality/reference-tests/index.md` | 容易被误读成当前主入口 | 本轮明确标记为旧专题参考 |
| `docs/08-handover/reference-user-guide/build-release.md` | 仍保留旧专题发布细节 | 已由当前版本治理规则与 release notes 承接主口径 |
| `docs/08-handover/module-developer-guide.md` | 当前模块开发主入口 | 已按外部模块作者真实链路完成重做 |
| `docs/08-handover/getting-started.md` / `docs/08-handover/reference-user-guide/configuration.md` | 仍需进一步做代码级一致性审查 | 放入 `TASK-008` 继续审查 |

## 4. 冲突裁决规则

当“旧专题文档”和“当前代码/验证结果/编号文档”冲突时，按以下优先级裁决：

1. 当前代码与可重复验证结果
2. 当前编号文档体系（`00-08` + `traceability`）
3. 旧专题文档

## 5. 迁移规则

- 不一次性重写所有旧文档。
- 先建立“入口统一 + 索引清晰 + 冲突裁决规则”。
- 再按任务逐步把有效内容吸收到当前编号体系。
- 当前仓库内 `docs/` 就是唯一事实源，不再依赖外部文档中心或静态站发布。

## 6. 下一步

- 本轮完成 `TASK-006` 后，继续执行 `TASK-007` 外部模块化。
- `TASK-008` 负责逐项审查旧专题内容与代码是否仍一致。
- 模块开发者指南的深度重做已经完成，后续仅需按真实代码演进持续维护。

## 7. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-26 | 建立旧文档审计与收敛策略 | Codex |
