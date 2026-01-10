# Crawler4j SRS/FSD（拆分版）总览

本目录为 Crawler4j《系统需求与功能规格说明书》（SRS/FSD）的**多文件拆分版**，用于在 MkDocs 中按章节组织并支持持续演进。

## 文档结构

### 项目级 (Project Level)
- [01 文档控制](01-document-control.md)
- [02 项目概述](02-project-overview.md)
- [03 需求分析](03-requirements-analysis.md)
- [04 总体架构](04-architecture.md)

### 系统级 (System Level)

#### 05 Framework Core (核心框架)
- [5.1 模块管理 (MM)](05-framework-core/05-1-module-management.md)
- [5.2 运行环境管理 (REM)](05-framework-core/05-2-runtime-environment-management.md)
- [5.3 任务策略管理 (TSM)](05-framework-core/05-3-task-strategy-management.md)
- [5.4 自动化任务管理 (ATM)](05-framework-core/05-4-automation-task-management.md)
- [5.5 UI 框架与微前端](05-framework-core/05-5-ui-host-microfrontend.md)
- [5.6 横切关注点 (Observability/Error)](05-framework-core/05-6-crosscutting.md)
- [5.7 测试与验收](05-framework-core/05-7-testing-acceptance.md)
- [5.8 部署与运维](05-framework-core/05-8-operations-release.md)

#### 06 SDK (开发工具包)
- [6.1 TaskScript 契约](06-sdk/06-1-taskscript.md)
- [6.2 TaskFlow 契约](06-sdk/06-2-taskflow.md)
- [6.3 TaskContext 能力](06-sdk/06-3-taskcontext.md)
- [6.4 TaskResult 模型](06-sdk/06-4-taskresult.md)
- [6.5 CLI 工具链](06-sdk/06-5-cli.md)
- [6.6 数据模型](06-sdk/06-6-data-model.md)
- [6.7 错误与可靠性](06-sdk/06-7-error-reliability.md)

#### 07 Modules (业务模块)
- [7.1 模块通用规范](07-modules/07-1-general-spec.md)
- [7.2 模块开发模板](07-modules/07-2-module-template.md)
- [7.3 Ctrip 模块规格](07-modules/07-3-ctrip.md)

### 附录 (Appendix)
- [附录与索引](appendix/index.md)

## 编写规则

- **规范性关键词**：MUST/SHOULD/MAY (RFC 2119)
- **需求编号**：统一使用 `FR-<System>-<Module>-<ID>` 格式
- **功能点要素**：每个功能点必须包含 功能说明、流程图/时序图、数据/类设计、交互设计。
