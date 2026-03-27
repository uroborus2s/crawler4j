# 历史归档

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 需要追溯历史背景的维护者 | 架构 | QA  
**上游输入：** 旧 SRS / 设计 / 测试 / 用户说明专题文档  
**下游输出：** 当前过程文档的背景解释与历史对照  
**最后更新：** 2026-03-28  

## 1. 归档目录的定位

本目录统一存放旧专题文档和历史辅助材料。它解决的是“需要追溯背景时去哪里找”的问题，不负责声明当前事实。

冲突裁决顺序固定为：

1. 当前代码与可重复验证结果
2. 当前过程文档与模块开发指南
3. `docs/archive/` 中的历史资料

## 2. 当前归档内容

| 归档目录 | 内容 | 当前承接位置 |
|---|---|---|
| `reference-srs/` | 旧需求 / 架构 / 规格细节 | `docs/02-requirements/`、`docs/03-solution/` |
| `reference-design/` | 旧技术设计专题 | `docs/03-solution/` |
| `reference-architecture/` | 旧架构补充说明 | `docs/03-solution/system-architecture.md` |
| `reference-sdk/` | 旧 SDK 参考说明 | `docs/03-solution/api-design.md`、模块开发指南 |
| `reference-tests/` | 旧测试专题 | `docs/05-quality/test-plan.md` |
| `reference-user-guide/` | 旧用户 / 运维说明 | `docs/06-release/`、`docs/07-operations/`、`docs/08-handover/user-guide.md` |
| `reference-module-dev/` | 旧模块开发辅助素材 | `docs/08-handover/module-developer-guide/` |

## 3. 使用规则

- 默认不把归档文档加入新的阅读路径。
- 只有当当前文档没有覆盖、需要解释历史决策或需要追踪旧路径时，才回读归档内容。
- 如果从归档中抽取了仍然有效的事实，应把结论回写到当前文档，而不是继续堆在归档层。
