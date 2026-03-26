# 文档索引

**项目名称：** crawler4j  
**负责人：** 当前仓库维护者  
**最后更新：** 2026-03-26  

## 1. 当前正式人类文档入口

| 当前文档 | 作用 | 主要读者 |
|---|---|---|
| `docs/00-governance/project-charter.md` | 项目边界、目标、风险 | 管理者 / Tech Lead |
| `docs/01-discovery/input.md` | 事实输入与验证证据 | 架构 / 开发 / QA |
| `docs/01-discovery/current-state-analysis.md` | 当前真实状态 | 全体维护者 |
| `docs/01-discovery/legacy-doc-audit.md` | 旧文档收敛策略 | 文档维护者 / Tech Lead |
| `docs/02-requirements/*` | 当前需求与校验 | 产品 / 架构 / 开发 / QA |
| `docs/03-solution/*` | 当前方案、边界、接口 | 架构 / 开发 |
| `docs/04-delivery/*` | 当前实施与任务拆解 | Tech Lead / Dev / QA |
| `docs/05-quality/test-plan.md` | 当前测试基线 | QA / Dev |
| `docs/05-quality/quality-gates.md` | 默认质量门与文档导航规则 | Tech Lead / Dev / QA / 发布负责人 |
| `docs/05-quality/design-implementation-audit.md` | 当前设计实现一致性审查结果 | Tech Lead / Dev / QA |
| `docs/06-release/release-notes.md` | 当前发布状态 | 发布负责人 |
| `docs/06-release/version-governance.md` | 当前版本治理规则 | 发布负责人 / Tech Lead |
| `docs/07-operations/deployment-guide.md` | 当前运行与部署说明 | 运维 / Dev |
| `docs/08-handover/user-guide.md` | 当前接手入口 | 新维护者 |
| `docs/08-handover/module-developer-guide.md` | 当前模块开发主入口 | 外部模块开发者 / Dev |
| `docs/traceability/requirements-matrix.md` | 需求追踪 | 架构 / QA |

## 2. 旧专题文档到当前体系的映射

| 旧专题目录/文件 | 当前主要承接位置 | 状态 |
|---|---|---|
| `docs/02-requirements/reference-srs/` | `docs/02-requirements/` + `docs/03-solution/` | 保留为详细参考 |
| `docs/03-solution/reference-design/` | `docs/03-solution/` | 保留为详细参考 |
| `docs/05-quality/reference-tests/` | `docs/05-quality/test-plan.md` | 保留为详细参考 |
| `docs/08-handover/reference-user-guide/build-release.md` | `docs/06-release/release-notes.md` + `docs/06-release/version-governance.md` + `docs/07-operations/deployment-guide.md` | 已建立承接 |
| `docs/08-handover/reference-user-guide/configuration.md` | `docs/03-solution/` + `docs/05-quality/design-implementation-audit.md` | 已纳入审查 |
| `docs/08-handover/module-developer-guide.md` | 当前模块开发主入口 | 已按外部模块作者真实链路重做 |
| `docs/03-solution/reference-sdk/` | `docs/03-solution/api-design.md` + 旧 SDK 详细参考 | 保留 |
| `docs/03-solution/reference-architecture/` | `docs/03-solution/system-architecture.md` | 保留 |

## 3. 阅读顺序建议

### 新接手维护者

1. `docs/index.md`
2. `docs/01-discovery/current-state-analysis.md`
3. `docs/04-delivery/task-breakdown.md`
4. `docs/07-operations/deployment-guide.md`

### 架构 / 开发

1. `docs/02-requirements/`
2. `docs/03-solution/`
3. `docs/04-delivery/`
4. 按需回读 `docs/02-requirements/reference-srs/` 与 `docs/03-solution/reference-design/`

### QA / 发布

1. `docs/05-quality/test-plan.md`
2. `docs/05-quality/quality-gates.md`
3. `docs/06-release/release-notes.md`
4. `docs/07-operations/deployment-guide.md`
5. 按需回读 `docs/05-quality/reference-tests/` 与 `docs/08-handover/reference-user-guide/`

## 4. 规则

- 当前正式人类文档体系优先。
- 详细参考层已并入同一套编号文档树。
- 冲突时以代码、可重复验证结果和当前编号文档为准。

## 5. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-26 | 建立当前文档索引与旧专题映射 | Codex |
| 2026-03-26 | 补充质量门规则文档入口与 QA / 发布阅读顺序 | Codex |
