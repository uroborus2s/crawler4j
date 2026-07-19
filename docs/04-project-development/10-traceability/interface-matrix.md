# 接口追踪矩阵

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 架构 | 开发 | QA | 发布负责人 | 运维
**上游输入：** `docs/04-project-development/04-design/api-design.md` | `requirements-matrix.md` | `docs/04-project-development/06-testing-verification/test-plan.md` | `docs/04-project-development/07-release-delivery/version-governance.md`
**下游输出：** `docs/04-project-development/07-release-delivery/acceptance-checklist.md` | `docs/04-project-development/08-operations-maintenance/operations-runbook.md`
**关联 ID：** `API-001`, `API-002`, `API-003`, `API-004`, `API-008`, `API-012`, `API-013`, `API-019`, `API-021`, `API-024`, `TASK-019`, `TASK-030`, `TASK-031`, `TASK-032`, `TASK-033`, `TASK-034`, `TASK-036`, `TASK-043`, `TASK-0400`, `TASK-0401`
**最后更新：** 2026-07-19

## 1. 接口责任矩阵

| 接口 ID | 契约内容 | 提供方 | 消费方 | 版本 / 来源 | 验证方式 | 运维责任 |
|---|---|---|---|---|---|---|
| `API-001` | Root App Entry Contract | Root app metadata | 维护者 / 打包流程 | `packages/crawler4j/pyproject.toml`、`src.ui.app:main` | workspace 入口检查、UI smoke、PyInstaller build | Core 维护者 |
| `API-002` | Module Runtime Contract | Core + Module runtime | 最终用户 / 模块维护者 | `module.yaml(runtime_api=core-native-v2)`、代码装饰器、`.crawler4j/manifest.lock.json`、模块根 `__init__.py` | 单元/集成测试、关键工作流验证；真实站点 E2E 仍待完成 | Core 维护者 |
| `API-003` | SDK / Contracts Package Contract | `crawler4j_sdk`、`crawler4j_contracts` | 模块开发者 | `packages/crawler4j-sdk/pyproject.toml`、`packages/crawler4j-contracts/pyproject.toml`、CLI 入口 | build、CLI help、脚手架测试 | SDK / Core 维护者 |
| `API-004` | Release Metadata Contract | Release metadata | 发布负责人 / 维护者 | `packages/crawler4j/pyproject.toml`、运行时版本服务、Git tag、子包版本 | 版本对照检查、release notes 校验 | 发布负责人 |
| `API-008` | Hosted Module UI Contract（V2） | Core MMS + SDK + `pages/` 页面注册 | 模块开发者 / 模块详情页 / QA | `pages/*.py`、`pages/<group>/*.py`、`@page(menu=True)`、`module-hosted-ui-framework.md` | CLI / 宿主页集成测试、模块详情页二级页回归 | Core / SDK 维护者 |
| `API-019` | Hosted UI Batch Import Contract | Core MMS + SDK + Contracts + Hosted UI renderer | 模块开发者 / 模块详情页 / QA / 运营支持 | `Page.toolbar.actions[]`、`DataTable.toolbar.actions[]`、`open_import_dialog`、标准 import payload、`hosted-ui-batch-import-design.md` | `TC-060`：schema、解析限制、脱敏、`@ui_action` / workflow 分发、结果展示和明细页跳转 | Core / SDK / Contracts 维护者 |
| `API-021` | Hosted UI DataTable Current-page Bulk Update Contract | Contracts + SDK scanner + Core MMS renderer + `SkyDataTable` | 模块开发者 / 模块详情页 / QA / 运营支持 | 顶层 `selection_mode`、`crud.toolbar.bulk_update`、`crud.bulk_update_handler`、`hosted-ui-datatable-bulk-update-design.md` | `TC-069`：schema / scanner、按钮状态、保序去重主键、空值、同步 / 异步、查询与分页清选择 | 通用交互由 Core / SDK / Contracts 维护者负责；业务校验与 `ctx.db` 写入由模块维护者负责 |
| `API-024` | Host-managed HTTP Request Contract | Core ATM + Core/Release dependency owner | `core-native-v2` full runtime 模块 | `ctx.tools.call("http.request")`、宿主 `httpx[http2,brotli]`、PyInstaller runtime check | `TC-071`：surface、请求保真、HTTP/2 拒绝降级、源码/wheel/冻结运行时 | Core 维护 API 与实现；Release owner 保证目标平台依赖；模块 owner 只传标准类型并处理业务响应 |
| `API-012` | Decorator-first Object Assembly Runtime（V2） | Core MMS + ATM + SDK + Contracts | 模块开发者 / 运行模板 / QA | `@interface/@component/@workflow/@page_action/@data_table/@data_view`、`.crawler4j/manifest.lock.json`、`0.4.0-decorator-object-assembly-architecture.md` | Contracts 装饰器单测、SDK 扫描/check full/module-open/DevLink/manifest lock、宿主保留字段诊断、Core descriptor v2、运行模板对象图 UI、执行器对象隔离测试 | Core / SDK / Contracts 维护者 |
| `API-013` | Versioned User / Developer Guide Contract | docs-stratego source docs | 使用者 / 模块开发者 / 文档维护者 | `docs/index.md`、`02-user-guide/v*/version.yaml`、`03-developer-guide/v*/version.yaml`、`0.4.0-guide-versioning-architecture.md` | docs-stratego validate、主文档版本 gate、版本元数据校验、跨版本链接校验 | 文档维护者 |

## 2. 当前接口风险

| 接口 | 风险 | 当前状态 |
|---|---|---|
| `API-002` | 真实站点 E2E 尚未完成，运行契约仍缺最终现场验证 | 未闭环 |
| `API-004` | 正式发布尚未切版，交付包仍需绑定实际发布批次 | 未闭环 |
| `API-008` | hosted page 已收口为 `@page(...)` 装饰器入口，但真实业务模块接入验证仍待继续推进 | 已本地验证，真实模块 E2E 待闭环 |
| `API-019` | Hosted UI 批量导入已完成 Contracts / SDK / Core / UI 本地实现和 `TC-060` 单测；对外发布版本、真实业务模块 E2E 与安装包证据仍待后续补齐 | 已本地验证 |
| `API-021` | 通用当前页批量编辑已完成整体 review、人工确认和 Contracts 0.4.3 / SDK 0.4.4 发布；最终全量 unit `1134 passed`，PyPI 哈希与隔离安装验证通过 | `core_packages_released`；具体业务模块 handler 与 E2E 未接线 |
| `API-024` | Core 通用工具、源码、隔离 wheel 与 macOS arm64 冻结 runtime 已验证；Windows 与 `ctrip_crawler` 外部仓库接线仍需完成 | 当前平台通过，跨平台/业务 E2E 待闭环 |
| `API-012` | core-native-v2 已实现；发布前仍需真实业务模块 E2E 与打包链路验证 | 已实现，发布验证待闭环 |
| `API-013` | 使用者指南和开发者指南已按版本分流；发布前需确认 docs-stratego 站点主入口切到 0.4.0 | 已实现，站点发布验证待闭环 |

## 3. 使用规则

- 当接口契约发生变化时，先改 `api-design.md`，再同步本矩阵。
- 需要判断“某个接口由谁负责、怎么验、出了问题谁接手”时，先看本矩阵，再进入实现或运维文档。

## 4. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-07-19 | 新增 `API-024` 责任矩阵，登记宿主统一 HTTP 方法、模块/Release owner 边界与 `TC-071` | Codex |
| 2026-07-10 | 新增 `API-021` 责任矩阵，登记 DataTable 当前页批量编辑的 Contracts / SDK / Core 提供方、模块数据 owner 与 `TC-069` 验证边界 | Codex |
| 2026-06-19 | 将 `API-019` 更新为已本地实现并通过 `TC-060`，当前剩余风险为发布版本与真实业务模块验证 | Codex |
| 2026-06-19 | 新增 `API-019` 责任矩阵，登记 Hosted UI 批量导入的提供方、消费方、契约来源、验证方式和待实现风险 | Codex |
| 2026-04-22 | 将 `API-008` 风险状态更新为“hosted page V1 已本地实现并验证，后续只剩 PR 收口与真实业务模块接入验证” | Codex |
| 2026-04-22 | 新增 `API-008` 责任矩阵，登记模块宿主管理页与最小化 UI 框架的提供方、消费方与验证方式 | Codex |
| 2026-04-30 | 新增 `API-013`，登记 docs-stratego 下使用者指南和开发者指南按版本分流的接口责任与验证方式 | Codex |
| 2026-04-30 | 补充 `API-012` 的 SDK 模块打开阶段诊断和宿主保留字段冲突验证方式 | Codex |
| 2026-04-30 | 新增 `API-012`，登记 0.4.0 装饰器对象装配运行时的提供方、消费方、契约来源与验证方式 | Codex |
| 2026-04-02 | 将占位页重写为正式接口责任矩阵 | Codex |
