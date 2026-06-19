# 实施方案

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 技术负责人 | 开发 | QA | 发布负责人  
**上游输入：** `docs/04-project-development/03-requirements/` | `docs/04-project-development/04-design/` | 当前文档治理缺口审计  
**下游输出：** `docs/04-project-development/05-development-process/execution-log.md` | `docs/04-project-development/06-testing-verification/test-plan.md` | `docs/04-project-development/07-release-delivery/release-notes.md`  
**关联 ID：** `TASK-002`, `TASK-003`, `TASK-004`, `TASK-005`, `TASK-006`, `TASK-007`, `TASK-008`, `TASK-009`, `TASK-010`, `TASK-011`, `TASK-012`, `TASK-013`, `TASK-014`, `TASK-015`, `TASK-016`, `TASK-017`, `TASK-018`, `TASK-019`, `TASK-020`, `TASK-021`, `TASK-022`, `TASK-023`, `TASK-024`, `TASK-025`, `TASK-027`, `TASK-028`, `TASK-029`, `TASK-030`, `TASK-031`, `TASK-032`, `TASK-033`, `TASK-034`, `BUG-001`, `BUG-002`, `BUG-003`, `BUG-004`, `BUG-005`, `CR-001`, `CR-002`, `CR-003`, `CR-004`, `CR-008`, `CR-009`, `CR-010`, `CR-011`, `CR-013`, `CR-014`, `CR-015`, `CR-016`, `API-009`, `API-010`, `API-019`
**最后更新：** 2026-06-19

## 1. 实施目标

- 把历史项目从“可运行但发布/治理漂移”的状态推进到“入口、关键模块、版本规则可验证”的状态。
- 已完成波次优先修复根入口、关键模块运行时和版本治理；Wave 14 已补齐环境候选 Service Job 的宿主等待队列能力。
- 在不改变 Core 当前模块加载契约的前提下，为模块开发链路补齐“根 `__init__.py` 自动托管”的最小演进方案。
- 在不改动现有 macOS Sparkle 线路的前提下，为 Windows 桌面宿主补齐正式安装器与自更新主方案。
- 已完成把模块 UI 从 `micro_app` / `ui:*` 切换到 hosted page V1；模块详情页、SDK CLI、测试夹具与开发者文档已统一到 `ui_extension.pages[] + ui.declare_page/ui.declare_data_table` 契约。
- 为 Hosted UI 追加宿主托管批量导入方案：页面 / 表格 toolbar 自定义按钮、宿主 Excel/CSV/剪贴板解析弹窗、标准 import payload、批次结果展示和暂存明细状态页。

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
| Wave 11 | `TASK-014` ~ `TASK-020` | 文档规范审计、根导航覆盖检查、最小文档包缺口 | 生产级文档入口收口、缺失正式页补齐、索引与 memory 同步 | 进行中：以四大模块结构为单一入口，补齐发布/运维/追踪关键页 |
| Wave 12 | `TASK-021` | `REQ-007`、`api-design.md`、现有 `TaskSignal` / ATM / UI 实现 | 信号驱动的结构化确认面板、任务 signal 持久化与客户端确认闭环 | 已完成：任务 signal 已持久化并发布 `task.signal` 事件，ATM 详情页可展示结构化确认面板并回调既有确认服务 |
| Wave 13 | `TASK-022` | `REQ-008`、`API-005`、模块数据持久化现状 | 模块审计事件独立存储、事件能力与契约文档同步 | 已完成：`module_audit_events`、`ctx.db.audit(...).append/query` 与对应测试/文档已落地 |
| Wave 14 | `TASK-023` | `REQ-009`、`API-007`、`atm-resource-pool-queue-design.md` | 环境候选 Service Job 的宿主等待队列、`@env_candidates` 纯函数候选、FIFO 补位与模块环境授权 | 已完成：宿主不再把候选环境暂时不可用直接判失败，资源池同步方案已被 `candidates/` 纯函数候选方案取代 |
| Wave 15 | `TASK-024` | `CR-010`、当前 `package-desktop`、`UpdateService`、Windows 发布缺口 | Windows `PyInstaller onedir + Velopack` 发布与宿主自更新闭环 | 已完成：新增 Windows Velopack 发布脚本、宿主更新后端分派、README/运维/测试计划同步 |
| Wave 16 | `TASK-025` | `CR-011`、`API-008`、`module-hosted-ui-framework.md` | Hosted module UI V1：`ui_extension.pages[]`、`ui.declare_page`、宿主页渲染器、SDK CLI/测试/文档同步 | 已完成：宿主不再执行外部 `PyQt6` 页面类，详情页/CLI/回归夹具已统一切到 hosted page V1 |
| Wave 17 | `TASK-027` | `CR-013`、`API-008`、`module-hosted-ui-framework.md`、当前 Hosted UI V1 路由链 | Hosted UI 主从表行导航：`row_action`、`open_page.params`、缓存页参数替换、详情表 `navigation_filters` | 已完成：主表点击可打开关联详情页/详情表，目标页收到 params，目标 `core:data_table` 可按参数过滤关联记录 |
| Wave 18 | `TASK-028` | `CR-014`、`API-009`、`module-entity-table-view-design.md`、`CR-012` 已落地的实体表资源模式 | 模块实体表视图与分析查询：`module_db_views`、`db.declare_db_view`、`db.query_view`、只读统计表 | 已完成：V1 已交付 `sql_view + query_view + readonly hosted table`，并补齐卸载提示与定向回归 |
| Wave 19 | `TASK-029` | `CR-015`、`API-010`、`shared-sky-data-table-design.md`、现有宿主表格/Hosted UI 表格分裂现状 | 共享表格基座重构：唯一正式 `SkyDataTable`、宿主/模块统一查询契约、删除旧 `SkyTableWidget`/旧 schema | 进行中：先重写共享组件并迁移正式表格，再切 Hosted UI 新契约 |
| Wave 20 | `TASK-030` ~ `TASK-034` | `REQ-010`、`CR-016`、`API-019`、`hosted-ui-batch-import-design.md`、当前 Hosted UI DataTable / `@ui_action` / workflow 调度链 | Hosted UI 批量导入：toolbar 自定义按钮、宿主导入弹窗、import payload 分发、批次结果和逐条状态展示 | 已完成：Contracts / SDK schema、宿主解析弹窗、renderer 分发、workflow runtime 注入、结果展示、`import_data_records` 跳转约定和 `TC-060` 单测已落地 |

## 3. 风险与应对

| 风险 | 影响 | 触发信号 | 应对策略 |
|---|---|---|---|
| 入口修复影响历史打包流程 | 无法及时出包 | `uv run python -m src.ui.app` 或 PyInstaller smoke 仍失败 | 先补 smoke，再调 spec 与脚本 |
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
- UI 组件目录需保留导入 smoke；未被主流程引用的残留组件也必须能被正常导入，避免已删除旧路径继续静默滞留
- UI 组件公共基座应优先抽成 `src.ui.components.*` 正式组件，避免把样式逻辑继续内嵌在单页私有类里
- UI 静态资源也要做引用面扫描；未被任何入口加载的 QSS / SVG 不应继续留在仓库里伪装成可用资源
- Wave 10 已完成：ModuleAssembler 与 Shim 落地并经全量测试验证
- Wave 9 后续回归已补强：`core:data_table` 页面会在刷新时重放 `declare_ui`，并验证 `create_handler` / `update_handler` 与 DevLink 调试上下文
- Wave 14 额外需要验证环境候选 Service Job 的“运行中 / 等待中”口径、FIFO 补位、容量扩张补位、候选纯函数实时过滤、模块环境授权与等待超时收口
- Wave 16 额外需要验证 hosted page renderer、模块详情页入口跳转、CLI 骨架生成、`check full` hosted UI gate，以及 integration/acceptance 对新契约的覆盖
- Wave 17 额外需要验证 row click 导航、`open_page.params`、已缓存目标页参数替换，以及目标 `core:data_table` 的 `navigation_filters`
- Wave 20 额外需要验证 toolbar schema 规范化、Excel/CSV/剪贴板解析、文件大小与行数限制、敏感字段脱敏、`@ui_action` / workflow 分发、导入结果汇总和 `import_data_records` 批次明细跳转

## 5. 任务表

| 任务 | 目标 | 主要产物 | 验收标准 | 优先级 | 状态 |
|---|---|---|---|---|---|
| `TASK-014` | 收口根导航与角色快读入口 | `docs/index.md`、`docs/01-getting-started/index.md` | 根导航覆盖正式页面，四类读者都有明确入口 | P0 | 已完成 |
| `TASK-015` | 重构开发者/维护者入口页 | `docs/03-developer-guide/index.md`、`docs/04-project-development/08-operations-maintenance/core-maintainer-guide.md`、`docs/02-user-guide/user-guide.md` | 每个入口页都说明“谁看、看什么、下一步去哪” | P0 | 已完成 |
| `TASK-016` | 补齐过程控制文档骨架 | `software-development-process.md`、`execution-log.md` | 过程规则和执行事实分离，且都可独立交接 | P1 | 已完成 |
| `TASK-017` | 补齐发布与交付文档骨架 | `acceptance-checklist.md`、`delivery-package.md` | 发布前检查、交付物清单和阻塞项可快速判断 | P1 | 已完成 |
| `TASK-018` | 补齐运维与管理员文档骨架 | `operations-runbook.md`、`admin-guide.md` | 管理员、维护者和运维读者职责分离 | P1 | 已完成 |
| `TASK-019` | 补齐追踪与索引同步 | `interface-matrix.md`、`document-index.md`、`.factory/memory/doc-map.md` | 文档索引、接口矩阵和 memory 映射一致 | P1 | 已完成 |
| `TASK-020` | 治理演进与结构验证收口 | `skill-evolution-plan.md`、结构校验记录 | 空壳页清理完毕，根导航覆盖与链接检查通过 | P1 | 已完成 |
| `TASK-021` | 建立 ATM 信号驱动的结构化确认面板闭环 | `TaskSignal`、ATM 详情页、任务快照持久化 | `wait_for_confirmation` 信号可展示结构化内容，客户端确认后调用既有确认服务完成任务收尾 | P1 | 已完成 |
| `TASK-023` | 建立 ATM 环境候选 Service Job 等待队列与模块候选分配闭环 | `execution_runner`、`controller`、MMS env candidates resolver、Contracts `EnvCandidates` DSL、SDK `candidates/` 脚手架、运行模板/UI 文案 | 候选环境场景支持“运行中 + 等待中 = 目标并发”，宿主实时执行当前模块候选纯函数并只从已授权、READY、未租约占用的浏览器环境里 FIFO 补位 | P1 | 已完成 |
| `TASK-024` | 建立 Windows `PyInstaller onedir + Velopack` 正式发布与宿主自更新闭环 | Windows 发布脚本、宿主更新桥接、README/运维/测试计划同步 | `uv run package-windows-release` 能产出 Velopack 安装器/更新目录，宿主 `检查更新` 在 Windows 安装态可用 | P0 | 已完成 |
| `TASK-025` | 建立 hosted module UI V1 并删掉旧 `micro_app/ui:*` 路径 | hosted page runtime capability、schema 存储、`ManagedPageRenderer`、SDK CLI/开发者文档同步 | 模块详情页只消费 `core:page` / `core:data_table`，CLI 不再生成 `ui/` 页面类，相关回归通过 | P0 | 已完成 |
| `TASK-027` | 为 Hosted UI 补主从表行导航与关联详情表能力 | `row_action`、`open_page.params`、`navigation_filters`、模块详情页路由参数复用 | 点击主表记录可打开关联详情页/详情表，目标页参数不残留旧值，定向回归通过 | P0 | 已完成 |
| `TASK-028` | 为模块实体表补数据库视图与分析查询能力 | `module_db_views`、`db.declare_db_view`、`db.query_view`、`core:data_table` 只读统计表模式 | 统计视图能以受控 SQL 模板方式登记、创建、查询和卸载清理，客户端可按过滤/排序/分页展示只读统计表 | P0 | 已完成 |
| `TASK-029` | 重构共享表格组件 SkyDataTable 并统一宿主/模块表格边界 | 新 `SkyDataTable`、宿主正式表格迁移、Hosted UI DataTable 新 schema/adapter、旧表格 API 删除 | 所有正式表格统一使用 `SkyDataTable`，组件只负责 UI，查询由外部 provider 完成，旧组件和旧 schema 删除 | P0 | 进行中 |
| `TASK-030` | 建立 Hosted UI toolbar 批量导入契约 | Contracts schema helper、SDK scanner / manifest lock、toolbar action 校验、import payload / result 类型约定 | 页面和 DataTable 可声明 toolbar actions；`open_import_dialog`、`ui_action`、`workflow` 动作被规范化并能在非法配置时被 SDK/Core 阻断 | P1 | 已完成 |
| `TASK-031` | 实现宿主导入弹窗与来源解析 | Excel/CSV 文件选择、剪贴板粘贴、可选手工录入、预览、列映射、限制与脱敏 | 宿主能解析 `.xlsx/.csv` 和剪贴板文本，限制文件类型/大小/最大行数，解析错误可见，敏感字段不进日志明文 | P1 | 已完成 |
| `TASK-032` | 贯通 Hosted UI 导入分发与结果展示 | `ManagedPageRenderer` toolbar 分发、`@ui_action` payload 参数、workflow 运行态注入、导入结果弹窗和页面跳转 | 导入 payload 能提交给模块 `@ui_action` 或 workflow；模块返回批次汇总后宿主展示结果并可跳转 `import_data_records` | P1 | 已完成 |
| `TASK-033` | 约定导入暂存明细与逐条状态展示 | `import_data_records` 页面参数、批次明细表约定、从暂存表导入业务表的逐条状态口径 | 页面能按 `batch_id/target_type` 展示导入明细；后续业务表导入可展示 `imported/import_failed/skipped_duplicate/validation_failed` 等状态 | P1 | 已完成 |
| `TASK-034` | 完成批量导入测试、开发者说明和记忆收口 | 单元/集成/验收测试、开发者指南、测试计划、release/traceability/memory 同步 | `TC-060` 覆盖 toolbar schema、解析限制、脱敏、分发、结果展示和明细页跳转；正式文档与 `.factory/memory/` 同步 | P1 | 已完成 |

## 6. 阶段建议

- 当前登记阶段：`IMPLEMENTATION`
- 当前活动波次：Wave 19 `TASK-029` 共享表格基座重构进行中；Wave 20 `TASK-030` ~ `TASK-034` 已完成
- 当前首项：继续完成 `SkyDataTable` 共享组件重构与宿主/模块统一接入，避免旧兼容表格壳继续扩散
- 后续波次：Hosted UI 批量导入已完成本地实现与 `TC-060` 单测，后续如需对外发布需另行完成 SDK / Contracts / 根应用版本提升、构建与发布证据

## 7. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-06-19 | 完成 Wave 20 / `TASK-030` ~ `TASK-034`：落地 Hosted UI toolbar 批量导入契约、宿主解析弹窗、payload 分发、workflow runtime 注入、结果展示和 `TC-060` 验证 | Codex |
| 2026-06-19 | 新增 Wave 20 / `TASK-030` ~ `TASK-034`，为 Hosted UI 批量导入拆分 toolbar 契约、宿主导入弹窗、payload 分发、暂存状态页和测试文档收口 | Codex |
| 2026-04-24 | 为共享 `Card` / Hosted UI `Card` 补齐布局参数：标题对齐、内容水平/垂直对齐、最小高度与 padding | Codex |
| 2026-04-24 | 修正共享 `Card` 样式作用域，避免通配 `QFrame` 误命中 `QLabel` 导致标题/副标题显示成“文字外套边框” | Codex |
| 2026-04-24 | Hosted UI 正式新增 `Card` 容器组件，并把 dashboard `StatCard` 改为基于共享 `Card` 组合；`Section.variant="card"` 收口为兼容别名 | Codex |
| 2026-04-24 | 删除未加载的 `dark_theme.qss` 与旧箭头 SVG 资源，收口 UI 目录静态孤岛资源 | Codex |
| 2026-04-24 | 清理 `config_editor` / `log_viewer` / `status_bar` / `syntax_highlighter` 孤岛代码，并新增正式 `StatCard` 组件替换 dashboard 私有实现 | Codex |
| 2026-04-24 | 为 `src.ui.components` 新增导入 smoke，并删除未使用的旧路径残留组件 `glass_card` / `metric_badge` | Codex |
| 2026-04-22 | 新增 Wave 16 / `TASK-025`，为模块 UI 建立 hosted page V1 并移除旧 `micro_app/ui:*` 路径 | Codex |
| 2026-04-22 | 完成 Wave 16 / `TASK-025` 实现与本地回归验证 | Codex |
| 2026-04-23 | 新增 Wave 17 / `TASK-027`，为 Hosted UI 补主从表行导航、`open_page.params` 与详情表 `navigation_filters` | Codex |
| 2026-04-23 | 完成 Wave 17 / `TASK-027` 实现与本地回归验证 | Codex |
| 2026-04-23 | 新增 Wave 18 / `TASK-028`，为模块实体表补数据库视图与分析查询能力正式设计 | Codex |
| 2026-04-23 | 完成 Wave 18 / `TASK-028` 实现与本地回归验证 | Codex |
| 2026-04-23 | 新增 Wave 19 / `TASK-029`，重构共享表格组件 `SkyDataTable` 并统一宿主/模块表格边界 | Codex |
| 2026-04-22 | 新增 Wave 15 / `TASK-024`，为 Windows 建立 `PyInstaller onedir + Velopack` 正式发布与宿主自更新闭环 | Codex |
| 2026-04-22 | 完成 Wave 15 / `TASK-024` 实现与本地回归验证 | Codex |
| 2026-04-30 | 将 Wave 14 / `TASK-023` 正式口径改为 `candidates/` + `@env_candidates` 纯函数候选；资源池同步和 `ctx.tools` 资源池能力退出 0.4.0 契约 | Codex |
| 2026-04-19 | 历史记录：曾新增 Wave 14 / `TASK-023` 固定资源池等待队列；该方案已被 2026-04-30 环境候选方案替代 | Codex |
| 2026-04-19 | 历史记录：曾完成固定资源池 V1 本地回归；当前正式回归以环境候选方案为准 | Codex |
| 2026-04-08 | 补强 Wave 9 的 `core:data_table` 声明刷新、CRUD hook 与 DevLink 调试回路验证 | Codex |
| 2026-04-18 | 新增 Wave 13 / `TASK-022`，为模块建立快照数据与审计事件分层存储契约 | Codex |
| 2026-04-02 | 新增 Wave 11 文档治理整改波次，并补写任务表 | Codex |
| 2026-04-16 | 新增 Wave 12 / `TASK-021`，收口 `TaskSignal.wait_for_confirmation` 的结构化确认面板与客户端确认闭环 | Codex |
| 2026-03-26 | 建立首批实施计划 | Codex |
| 2026-03-26 | 标记 Wave 3 / Wave 4 完成，并纳入设计一致性审查结果 | Codex |
| 2026-03-26 | 标记 Wave 6 完成，模块开发者指南按真实外部开发链路重做 | Codex |
| 2026-03-26 | 标记 `TASK-004` 完成，并建立统一版本治理规则 | Codex |
| 2026-03-26 | 标记 `TASK-005` 完成，并固化默认质量门与文档导航规则 | Codex |
| 2026-03-26 | 拆分 `CR-003` 并完成 `TASK-011`，将剩余范围收缩到 `TASK-012` | Codex |
| 2026-03-26 | 完成 `TASK-012` 并关闭 `CR-003` | Codex |
| 2026-03-31 | 新增 Wave 10，登记 `TASK-013` 的设计输入与待启动状态 | Codex |
| 2026-03-31 | 完成 Wave 10 / `TASK-013` 实现与全量验证 | Gemini |
