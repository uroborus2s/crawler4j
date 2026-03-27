# 文档索引

**项目名称：** 蛛行演略（crawler4j）  
**负责人：** 当前仓库维护者  
**最后更新：** 2026-03-27  

## 1. 当前正式文档树

当前正式的人类文档体系由 `docs/index.md` 统领，按阶段组织为 `00-governance/` 到 `09-evolution/`，并由 `traceability/` 负责入口映射与追踪。

| 目录 | 目录入口 | 作用 | 主要读者 |
|---|---|---|---|
| `docs/00-governance/` | [index.md](../00-governance/index.md) | 项目边界、治理规则 | 管理者 / Tech Lead |
| `docs/01-discovery/` | [index.md](../01-discovery/index.md) | 输入证据、现状分析、旧文档审计 | 架构 / 开发 / QA |
| `docs/02-requirements/` | [index.md](../02-requirements/index.md) | 当前需求、分析、校验 | 产品 / 架构 / 开发 / QA |
| `docs/03-solution/` | [index.md](../03-solution/index.md) | 当前架构、边界、接口和设计规则 | 架构 / 开发 |
| `docs/04-delivery/` | [index.md](../04-delivery/index.md) | 实施计划、任务拆解、WBS | Tech Lead / Dev / QA |
| `docs/05-quality/` | [index.md](../05-quality/index.md) | 测试计划、质量门、一致性审查 | QA / Dev / 发布负责人 |
| `docs/06-release/` | [index.md](../06-release/index.md) | 发布说明、版本治理 | 发布负责人 / Tech Lead |
| `docs/07-operations/` | [index.md](../07-operations/index.md) | 部署与运行说明 | 运维 / Dev |
| `docs/08-handover/` | [index.md](../08-handover/index.md) | 接手、使用、模块开发 | 新维护者 / 外部模块开发者 |
| `docs/09-evolution/` | [index.md](../09-evolution/index.md) | 流程与文档演进入口 | Tech Lead / 文档维护者 |
| `docs/traceability/` | [index.md](index.md) | 文档入口映射与需求追踪 | 架构 / QA / 文档维护者 |

说明：

- 当前所有包含 Markdown 页面的人类文档目录都已经补齐 `index.md`。
- `docs/.obsidian/` 和纯资产目录不属于正式文档树，不纳入目录入口要求。

## 2. 当前主入口文档

| 当前文档 | 作用 | 主要读者 |
|---|---|---|
| `docs/index.md` | 文档总入口与阅读路径 | 全体维护者 |
| `docs/01-discovery/current-state-analysis.md` | 当前真实状态 | 全体维护者 |
| `docs/03-solution/system-architecture.md` | 系统结构总览 | 架构 / 开发 |
| `docs/04-delivery/task-breakdown.md` | 当前任务主线 | Tech Lead / Dev / QA |
| `docs/05-quality/quality-gates.md` | 默认质量门与文档导航规则 | Dev / QA / 发布负责人 |
| `docs/06-release/version-governance.md` | 当前版本规则 | 发布负责人 / Tech Lead |
| `docs/07-operations/deployment-guide.md` | 部署与运行说明 | 运维 / Dev |
| `docs/08-handover/module-developer-guide.md` | 外部模块开发主入口 | 外部模块开发者 / Dev |
| `docs/traceability/requirements-matrix.md` | 需求追踪 | 架构 / QA |

## 3. 参考层映射

| 参考层目录/文件 | 当前承接位置 | 当前状态 |
|---|---|---|
| `docs/02-requirements/reference-srs/` | `docs/02-requirements/` + `docs/03-solution/` | 保留为旧 SRS 参考层 |
| `docs/03-solution/reference-design/` | `docs/03-solution/` | 保留为设计参考层 |
| `docs/03-solution/reference-architecture/` | `docs/03-solution/system-architecture.md` | 保留为补充架构层 |
| `docs/03-solution/reference-sdk/` | `docs/03-solution/api-design.md` | 保留为 SDK 补充说明层 |
| `docs/05-quality/reference-tests/` | `docs/05-quality/test-plan.md` | 保留为测试参考层 |
| `docs/08-handover/reference-user-guide/` | `docs/06-release/` + `docs/07-operations/` + `docs/08-handover/` | 保留为用户说明参考层 |
| `docs/08-handover/reference-module-dev/` | `docs/08-handover/module-developer-guide.md` | 仅保留截图资产与历史辅助说明 |

## 4. 阅读顺序建议

### 新接手维护者

1. [文档中心](../index.md)
2. [当前真实状态分析](../01-discovery/current-state-analysis.md)
3. [系统架构](../03-solution/system-architecture.md)
4. [任务分解](../04-delivery/task-breakdown.md)
5. [部署与运行说明](../07-operations/deployment-guide.md)

### 架构 / 开发

1. [需求目录](../02-requirements/index.md)
2. [方案目录](../03-solution/index.md)
3. [交付目录](../04-delivery/index.md)
4. 按需回读 `reference-srs/`、`reference-design/` 和 `reference-sdk/`

### QA / 发布

1. [质量目录](../05-quality/index.md)
2. [发布目录](../06-release/index.md)
3. [运行目录](../07-operations/index.md)
4. 按需回读 `reference-tests/` 与 `reference-user-guide/`

## 5. 维护规则

- 文档目录有新增、删除或移动时，先更新所属目录 `index.md`，再更新本文件。
- 当前编号文档优先；参考层仅用于补充历史细节。
- 冲突时，以代码、可重复验证结果和当前编号文档为准。

## 6. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-27 | 补齐阶段目录与参考层目录入口页，重写文档索引为当前真实文档树 | Codex |
| 2026-03-26 | 建立当前文档索引与旧专题映射 | Codex |
