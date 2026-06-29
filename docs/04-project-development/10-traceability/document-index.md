# 文档索引

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 新维护者 | 模块开发者 | Tech Lead | QA | 发布负责人 | 运维
**上游输入：** `docs/index.md` | 当前正式文档树 | 文档治理整改结果
**下游输出：** `docs/01-getting-started/index.md` | `.factory/memory/doc-map.md` | 角色阅读路径
**关联 ID：** `DOC-106`, `TASK-014`, `TASK-019`, `TASK-020`
**最后更新：** 2026-06-28

## 1. 当前正式文档结构

当前正式的人类文档收敛为四大模块：

| 模块 | 作用 | 主要读者 |
|---|---|---|
| `docs/01-getting-started/` | 面向所有人的单页产品介绍和阅读入口 | 第一次接触产品的人 / 协作者 |
| `docs/02-user-guide/` | 开始使用、安装、设置、日常使用、作业详情讲义、异常案例和管理员指南 | 宿主使用者 / 管理员 / 协作者 |
| `docs/03-developer-guide/` | 开发者指南；在本项目中即 module 开发指南 | 模块开发者 / 做模块集成的 Core 成员 |
| `docs/04-project-development/` | 治理、需求、设计、计划、测试、发布、运维和追踪等正式内部文档 | Tech Lead / Dev / QA / 发布 |

当前 0.4.0 文档版本分流已在开发者指南入口落地：`docs/03-developer-guide/` 根目录保留版本选择页，0.4.0 是当前主线，0.3.x 只作为历史维护入口。docs-stratego 发布站点仍需在正式发布前按版本治理确认主入口、历史入口和开发中入口的发布策略。

## 2. 按角色快速阅读

### 新维护者

1. [根入口](../../index.md)
2. [了解 crawler4j](../../01-getting-started/index.md)
3. [开始使用](../../02-user-guide/user-guide.md)
4. [Core 接手与日常维护](../08-operations-maintenance/core-maintainer-guide.md)
5. [当前真实状态分析](../02-discovery/current-state-analysis.md)
6. [实施方案](../05-development-process/implementation-plan.md)

### 模块开发者

1. [开发者指南总览](../../03-developer-guide/index.md)
2. [0.4.0 当前契约概览](../../03-developer-guide/v0.4.0/index.md)
3. [0.4.0 装饰器与对象装配](../../03-developer-guide/v0.4.0/decorators-and-object-assembly.md)
4. [从 0.3.0 迁移到 0.4.0](../../03-developer-guide/v0.4.0/migration-from-v0.3.0.md)
5. [0.3.0 历史契约概览](../../03-developer-guide/v0.3.0/index.md)
6. [0.3.0 快速开始](../../03-developer-guide/v0.3.0/quickstart.md)
7. [0.3.0 构建模块](../../03-developer-guide/v0.3.0/build-modules.md)
8. [0.3.0 交付模块](../../03-developer-guide/v0.3.0/shipping.md)

### 发布 / 运维

1. [发布与交付概览](../07-release-delivery/index.md)
2. [验收检查清单](../07-release-delivery/acceptance-checklist.md)
3. [ctrip 真实站点 E2E 收口方案](../06-testing-verification/ctrip-real-site-e2e-closeout.md)
4. [交付包清单](../07-release-delivery/delivery-package.md)
5. [部署与运行说明](../08-operations-maintenance/deployment-guide.md)
6. [运行手册](../08-operations-maintenance/operations-runbook.md)

## 3. 阶段文档入口

| 阶段 | 关键入口 | 作用 |
|---|---|---|
| 治理与调研 | `01-governance/`、`02-discovery/` | 说明背景、范围、风险和现状证据 |
| 需求与设计 | `03-requirements/`、`04-design/` | 说明为什么做、怎么设计、接口和边界是什么 |
| 实施与验证 | `05-development-process/`、`06-testing-verification/` | 说明如何推进、怎么验证、最近执行了什么 |
| 发布与运维 | `07-release-delivery/`、`08-operations-maintenance/` | 说明什么时候能发、如何交付、如何运行和接手 |
| 追踪与演进 | `09-evolution/`、`10-traceability/` | 说明模式级改进、需求覆盖和接口责任 |

## 4. 维护规则

- 根 `docs/index.md` 是唯一的全站导航源；本文件负责“入口解释”和“按角色索引”，不重复维护整棵页面树。
- 任何新增、删除或移动页面，都要同步更新根 `docs/index.md`、本文件和 `.factory/memory/doc-map.md`。
- `docs/project-process/` 与 `docs/model-development/` 不再作为正式入口保留。
- 当前事实以代码、当前文档和可重复验证结果为准。

## 5. 最近同步

- 2026-06-29：根应用 / 运行时版本事实源已提升到 `crawler4j 0.4.22`，用于 VirtualBrowser 随机指纹语言参数去重；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、发布文档与 `.factory/memory/` 已同步到同一口径。
- 2026-06-29：根应用 / 运行时版本事实源已提升到 `crawler4j 0.4.21`，用于 VirtualBrowser 随机指纹代理出口 geo 校准、创建后轻量验收、风险环境标记与默认调度跳过；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、发布文档与 `.factory/memory/` 已同步到同一口径。
- 2026-06-29：指纹风险环境已接入手动重新检测与默认调度跳过。风险状态写入 `fingerprint.validation` metadata，环境列表展示“风险”状态和原因；普通租约、固定环境选择、候选调度和 Service 容量计算默认跳过风险环境，不自动删除。手动复检只更新 validation metadata，不修改代理、指纹或 WebRTC 配置。同步用户说明、执行记录、测试计划和 `.factory/memory/`。
- 2026-06-29：VirtualBrowser 随机指纹创建期已接入代理出口 geo 探测，随机指纹且带代理时用真实出口国家/时区覆盖 `ua-language` 与 `time-zone`，并在 `addBrowser` 后调用 `getBrowserFullParameters(id)` 做轻量验收；探测失败回退默认画像，不自动删除环境。同步执行记录、测试计划和 `.factory/memory/`。
- 2026-06-29：VirtualBrowser 随机指纹创建期展开已改为下发最小自洽默认画像，补齐 `zh-CN` / `Asia/Shanghai`、常见屏幕 `mode=1`、常见 CPU/内存和随机扰动项，同时继续剥离手工 UA、Sec-CH-UA、设备名和 MAC；运行模板 UI 在随机指纹开启时隐藏高级指纹参数。同步执行记录、测试计划和 `.factory/memory/`。
- 2026-06-28：根应用 / 运行时版本事实源已提升到 `crawler4j 0.4.20`，用于 `browser.drag natural` 体感时长、约 60Hz 采样与固定 seed 默认混入运行随机盐的框架自检能力；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、发布文档与 `.factory/memory/` 已同步到同一口径。
- 2026-06-28：根应用 / 运行时版本事实源已提升到 `crawler4j 0.4.19`，用于 `browser.drag` 连续轨迹生成与框架自检 trace 能力；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、发布文档与 `.factory/memory/` 已同步到同一口径。
- 2026-06-22：根应用 / 运行时版本事实源已提升到 `crawler4j 0.4.18`，用于 VirtualBrowser 随机指纹创建期不下发具体指纹字段和 `chrome_version=139..145` 随机化；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、发布文档与 `.factory/memory/` 已同步到同一口径。
- 2026-06-22：VirtualBrowser 随机指纹创建期展开已改为不再由 Core 注入 `ua`、设备名、MAC、字体、Canvas、WebGL 等具体指纹字段；调用 `addBrowser` 前剥离内部标记，并将 `chrome_version` 每次随机为 `139..145`，完整指纹由 VirtualBrowser 自身生成；同步执行记录、定向回归证据和 `.factory/memory/`。
- 2026-06-19：完成 Hosted UI 批量导入代码实现与 `TC-060` 验证，并同步 `hosted-ui-batch-import-design.md`、`api-design.md`、`module-hosted-ui-framework.md`、`implementation-plan.md`、`execution-log.md`、`test-plan.md`、需求文档、追踪矩阵、接口矩阵、`.factory/workitems/` 和 `.factory/memory/`。
- 2026-06-19：重新发布 macOS `0.4.16` 客户端下载版本，删除远端旧 `Crawler4j-0.4.16.dmg` 后重新生成并上传 `Crawler4j-0.4.16.dmg` 与 `appcast.xml`，并同步 README、发布文档、执行记录和 `.factory/memory/`。
- 2026-06-19：新增 Hosted UI 批量导入方案文档 `docs/04-project-development/04-design/hosted-ui-batch-import-design.md`，并同步 `REQ-010` / `NFR-010`、`API-019`、`CR-016`、`TASK-030` ~ `TASK-034`、`TC-060` 到 PRD、需求分析、校验、实施计划、测试计划、追踪矩阵、接口矩阵、根导航和 `.factory/memory/`。
- 2026-06-20：根应用 / 运行时版本事实源已提升到 `crawler4j 0.4.17`，用于任务监控作业禁用状态、REM 固定运行模板安全门和来源代理同步匹配规则修复；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、发布文档与 `.factory/memory/` 已同步到同一口径。
- 2026-06-18：根应用 / 运行时版本事实源已提升到 `crawler4j 0.4.16`，用于修复来源代理同步匹配规则：只按 `host + port` 唯一命中 IP 表，不再比较协议、用户名或密码；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、用户指南、测试计划、发布文档与 `.factory/memory/` 已同步到同一口径。
- 2026-06-16：根应用 / 运行时版本事实源已提升到 `crawler4j 0.4.15`，用于修复 VirtualBrowser 来源代理解析优先级，避免把 `proxy.url` 中的 `127.0.0.1:本地端口` 转发地址保存为绑定 IP；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、用户指南、测试计划、发布文档与 `.factory/memory/` 已同步到同一口径。
- 2026-06-16：根应用 / 运行时版本事实源已提升到 `crawler4j 0.4.14`，用于发布已导入指纹浏览器环境的来源代理同步、IP 表唯一匹配绑定和环境管理页批量同步入口；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、用户指南、测试计划、发布文档与 `.factory/memory/` 已同步到同一口径。
- 2026-06-15：根应用 / 运行时版本事实源保持 `crawler4j 0.4.13`，SDK / Contracts 提升到 `0.4.2`，用于发布已有环境导入 workflow 场景契约、`env.get_proxy` 当前代理读取、多环境导入批次元数据和环境列表绑定 IP 展示；`packages/*/pyproject.toml`、`uv.lock`、README、发布文档与 `.factory/memory/` 已同步到同一口径。
- 2026-06-13：根应用 / 运行时版本事实源已提升到 `crawler4j 0.4.12`，用于承接 Hosted UI DataTable 行按钮显式 params 分发和任务暂停后绑定业务行 `run_status` 释放修复；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、发布文档与 `.factory/memory/` 已同步到同一口径，SDK / Contracts 继续保持 `0.4.1`。
- 2026-06-13：根应用 / 运行时版本事实源已提升到 `crawler4j 0.4.11`，用于承接 Hosted UI DataTable 自定义行按钮分发到同名 `@ui_action` 的客户端修复；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、发布文档与 `.factory/memory/` 已同步到同一口径，SDK / Contracts 继续保持 `0.4.1`。
- 2026-06-13：根应用 / 运行时版本事实源已提升到 `crawler4j 0.4.10`，用于承接任务监控暂停后对象 cleanup 链路 `asyncio.CancelledError` 截断修复；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、发布文档与 `.factory/memory/` 已同步到同一口径，SDK / Contracts 继续保持 `0.4.1`。
- 2026-06-12：`docs/02-user-guide/usage.md`、`execution-log.md` 与 `.factory/memory/` 已同步补记 IP 池条目人工 `可用 / 不可用` 状态；不可用条目只影响后续绑定候选，不自动解绑已有环境。
- 2026-06-11：根应用 / 运行时版本事实源已提升到 `crawler4j 0.4.8`，用于承接 IP 池最久未使用默认分配策略、最近使用时间记录与旧库迁移；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、发布文档与 `.factory/memory/` 已同步到同一口径，SDK / Contracts 继续保持 `0.4.1`。
- 2026-06-09：根应用 / 运行时版本事实源已提升到 `crawler4j 0.4.7`，用于承接 workflow/component 对象 cleanup 固定超时移除；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、发布文档与 `.factory/memory/` 已同步到同一口径，SDK / Contracts 继续保持 `0.4.1`。
- 2026-06-07：根应用 / 运行时版本事实源已修正提升到 `crawler4j 0.4.6`，用于承接指纹浏览器生命周期串行化修复版；`packages/crawler4j/pyproject.toml`、`uv.lock`、README、发布文档与 `.factory/memory/` 已同步到同一口径，SDK / Contracts 继续保持 `0.4.1`。
- 2026-06-06：指纹浏览器生命周期并发串行化已从 VirtualBrowser 启动链路扩展到 VirtualBrowser / BitBrowser 的关闭、销毁、重置、状态检查、来源列表和配置更新。`packages/crawler4j/src/core/rem/provider.py` 现统一使用 provider 生命周期锁保护外部管理 API 与 Playwright/CDP 生命周期入口，并通过内部 unlocked helper 避免锁内递归；`docs/02-user-guide/exception-cases.md` 与 `docs/04-project-development/06-testing-verification/test-plan.md` 已同步新的现场排障口径和回归证据。
- 2026-05-12：0.4.0 开发者指南审阅意见已并入正式正文。`docs/03-developer-guide/v0.4.0/` 现统一校正阅读路径、quickstart 的 DevLink + ZIP install 闭环、`check structure -> manifest lock -> check full` 校验顺序、candidate/cleanup CLI 入口、manifest lock 当前结构、UI Action 与 Page Action 边界、DataTable total/count 示例、ZIP 标准目录和手工迁移边界；`v0.4.0/version.yaml` 已标为当前主线，`v0.3.0/version.yaml` 已标为历史维护。
- 2026-06-06：VirtualBrowser 并发启动串行化已同步到用户排障与测试计划。`packages/crawler4j/src/core/rem/provider.py` 对 VirtualBrowser 创建、打开和 Playwright 连接使用同一生命周期锁，避免多环境同时启动时并发调用本地管理 API / `launchBrowser` / CDP connect；`docs/02-user-guide/exception-cases.md` 与 `docs/04-project-development/06-testing-verification/test-plan.md` 已记录该运行口径和回归证据。
- 2026-05-11：Hosted UI 内联 `DataTable` 查询契约已同步为固定类型。`crawler4j-contracts` 新增 `HostedDataTableQuery`、泛型 `HostedDataTableQueryResult[RowT]`、`HostedDataTableSortSpec`；`docs/03-developer-guide/v0.4.0/{ui-and-data-table,reference-core-capabilities,troubleshooting}.md` 与 `docs/04-project-development/04-design/{api-design,module-config-runtime-data-contract,module-hosted-ui-framework,module-entity-table-view-design}.md` 已明确 `query_handler(context, query)`、返回 `HostedDataTableQueryResult`，且 `DataTable.table_id` 只作为 UI 组件实例 ID。`search_fields` 只从显式 `searchable=True` 的 `DataTable.columns` 生成，未声明列默认不可搜索，结果不再回传 `sort`。
- 2026-05-11：`TaskContext` 边界清理已同步。`packages/crawler4j-contracts/src/crawler4j_contracts/context.py` 删除 `screenshot()`、`run_subtask()` 与 `_subtask_executor`，`run_page_action()` 仍由 `packages/crawler4j/src/core/mms/service.py` 注入 `_page_action_executor` 后调用 `@page_action`；Core 未发现真实截图工具实现，REM 能力示例注释已移除 screenshot。`docs/03-developer-guide/v0.4.0/{reference-core-capabilities,migration-from-v0.3.0}.md` 与 `docs/04-project-development/04-design/0.4.0-decorator-object-assembly-architecture.md` 已同步。
- 2026-05-11：`ctx.db.from_(...).execute()` 默认分页语义已修正并同步。`packages/crawler4j-contracts/src/crawler4j_contracts/database.py` 现在只在显式调用 `.limit(...)` / `.offset(...)` 时把分页值写入 plan；`packages/crawler4j/src/core/persistence/module_data_store.py` 缺省分页时不再追加 `LIMIT/OFFSET`。`docs/03-developer-guide/v0.4.0/{data-contracts,reference-core-capabilities}.md` 与 `docs/04-project-development/04-design/api-design.md` 已明确未显式分页会读取满足条件的全部行，表格和可增长数据源必须显式分页；`.factory/memory/` 已同步测试和当前状态。
- 2026-05-09：`ctx.db.describe(source)` 数据源描述入口已同步到开发者指南。`docs/03-developer-guide/v0.4.0/{index,data-contracts,reference-core-capabilities}.md` 现明确 `source` 是逻辑数据源名，并说明 `custom_table` 自增/非自增主键、`managed_dataset` 系统字段和 `writable_fields` / `required_fields` / `read_only_fields` 的宿主归一化语义；`.factory/memory/` 已同步 API、测试和演进基线。
- 2026-05-08：Hosted UI 用户操作契约已新增 `@ui_action`。`docs/03-developer-guide/v0.4.0/architecture-rules.md` 已新增模块 DDD 与根目录固定规则；`docs/03-developer-guide/v0.4.0/{decorators-and-object-assembly,ui-and-data-table,module-structure,reference-sdk-and-cli,reference-core-capabilities}.md` 和 `docs/04-project-development/04-design/{api-design,module-config-runtime-data-contract,0.4.0-decorator-object-assembly-architecture,module-hosted-ui-framework}.md` 已同步区分 `@ui_action` 与 `@page_action`：按钮/CRUD handler/表单提交走 `@ui_action`，浏览器页面操作只由 workflow/component 通过 `ctx.run_page_action(...)` 调用；`@page_action` 内部不再允许嵌套调用另一个 `@page_action`。
- 2026-05-08：0.4.0 模块根目录结构说明已细化。`docs/03-developer-guide/v0.4.0/module-structure.md` 现在按根目录固定文件和固定文件夹分别说明 `module.yaml`、`.crawler4j/manifest.lock.json`、`interfaces/`、`objects/`、`workflows/`、`tasks/`、`data/`、`pages/`、`candidates/`、`cleanups/` 的含义、扫描入口和维护边界；`.factory/memory/runtime-brief.md` 已补记压缩事实。
- 2026-05-02：运行模板对象装配 UI 已同步为公共树形对象图。`packages/crawler4j/src/ui/components/object_graph_tree.py` 提供公共 `ObjectGraphTree`，`packages/crawler4j/src/core/atm/ui/run_profile_dialog.py` 现在按 `workflow -> interface 绑定行 -> 子 interface/参数` 展示对象装配，绑定行左侧显示 interface 中文 `label(name)`，右侧下拉框显示 component 中文 `label(name)`，interface 选择继续保存到 `object_bindings`，component 创建参数继续保存到 `object_params`；`docs/03-developer-guide/v0.4.0/decorators-and-object-assembly.md` 与 `docs/04-project-development/04-design/{0.4.0-decorator-object-assembly-architecture,module-config-runtime-data-contract}.md` 已补记该 UI 口径。
- 2026-05-02：宿主 `browser.*` 页面交互协议已同步到脚手架、开发者指南、设计契约和项目记忆。`packages/crawler4j-sdk/src/cli/templates.py` 生成的 page action 现在直接调用 `ctx.tools.call("browser.goto", ...)`；`docs/03-developer-guide/v0.4.0/{index,quickstart,build-modules,decorators-and-object-assembly,reference-core-capabilities,ui-and-data-table,migration-from-v0.3.0}.md` 与 `docs/04-project-development/04-design/{api-design,module-config-runtime-data-contract,0.4.0-decorator-object-assembly-architecture}.md` 已统一明确“标准页面交互走宿主 `browser.*` tool，`ctx.page` 主要保留给读取与宿主未覆盖能力”。后续拟人化评分优化已补记到 `reference-core-capabilities.md` 与 `module-config-runtime-data-contract.md`：分段停顿、导航扫描、目标尺寸感知轨迹、mouse/key dwell、自然输入纠错概率、敏感输入保护和惯性滚动由宿主统一治理。
- 2026-06-11：`docs/02-user-guide/usage.md` 与 `execution-log.md` 已同步补记 IP 池默认分配策略调整：新增“最久未使用”策略并作为新建 IP 池、默认池和运行模板默认值，IP 条目记录并展示最近使用时间，旧库通过 `ip_entries.updated_at` / `last_used_at` 补列迁移兼容。
- 2026-05-01：0.4.0 全面审查后同步文档入口和发布证据。`docs/03-developer-guide/index.md` 与根 `docs/index.md` 已把 0.4.0 标为当前主线、0.3.x 标为历史维护；发布与测试记忆登记本轮 `886 passed`、ruff、三包构建、SDK CLI help、UI smoke 与 macOS `package-desktop` 通过。正式发布裁决仍为 No-Go，阻塞项为 `ctrip` 真实站点 DevLink + ZIP 双链 E2E、Windows 真机签名/安装/自更新和正式交付批次。
- 2026-05-01：`ctx.db` 写入并发底座第一阶段已同步到开发者指南和设计契约。`docs/03-developer-guide/v0.4.0/reference-core-capabilities.md` 与 `docs/04-project-development/04-design/module-config-runtime-data-contract.md` 现明确模块开发者不管理锁、事务或提交/回滚；宿主负责短事务、busy timeout、写协调器排队与重试；`custom_table` 新增 `upsert/update_where/delete_where` 和 `batch()` 写入语义，`replace()` 保留全量覆盖语义。
- 2026-04-30：开发者指南已按版本分流并补齐 0.4.0 开发版正文。`docs/03-developer-guide/index.md` 只保留版本选择；0.3.0 稳定指南冻结到 `docs/03-developer-guide/v0.3.0/`；0.4.0 开发者指南新增到 `docs/03-developer-guide/v0.4.0/`，主线为 `core-native-v2` 装饰器对象装配、manifest lock、`ctx.db` 数据契约和保留字段诊断，并已明确 0.4.x SDK / Contracts 只服务 Core 0.4.0，不兼容 0.3.x 命令、模板或开发模式；根 `docs/index.md` 已更新开发者指南导航。
- 2026-04-30：Workflow 运行参数契约与运行模板 UI 已同步到开发者入口。`docs/03-developer-guide/{index.md,module-structure.md,reference-sdk-and-cli.md}` 与 `docs/04-project-development/04-design/module-config-runtime-data-contract.md` 现统一说明 `module.yaml.workflows[].parameters[]`、支持的数据类型、SDK 校验和 `RunProfile.execution.params` 注入链路；`.factory/memory/` 已同步登记。
- 2026-04-30：使用者指南与开发者指南版本分流方案已形成。新增 `docs/04-project-development/03-requirements/0.4.0-guide-versioning-requirements.md` 与 `docs/04-project-development/04-design/0.4.0-guide-versioning-architecture.md`，明确 docs-stratego 网站主文档必须指向当前已发布版本，旧版本指南保留为历史版本入口；0.4.0 源码文档入口的当前主线状态已在 2026-05-01 同步覆盖。
- 2026-04-30：0.4.0 正式架构方向调整为装饰器对象装配。新增 `docs/04-project-development/03-requirements/0.4.0-decorator-object-assembly-requirements.md` 与 `docs/04-project-development/04-design/0.4.0-decorator-object-assembly-architecture.md`，明确 workflow 不再声明参数，参数归属 component 创建；interfaces/components/workflows/page actions/data tables 由装饰器扫描生成运行时对象图，Core 负责每任务环境对象装配，SDK/Contracts 同步进入 v2 重构；SDK 打开阶段、DevLink、`check full` 与打包阶段需前置阻断宿主保留数据库字段冲突。
- 2026-04-25：公共 `MessageDialog` 已按“安装模块”面板视觉重做，`StyledButton` 增加成功态动作按钮；安装模块弹窗和多处简单提示/确认已改用公共组件。剩余未迁移的 `QMessageBox` 已收敛到环境/模块列表异步流程与任务中止三按钮流程，需后续补齐公共异步/多动作弹窗能力。
- 2026-04-25：IP 测试结果弹窗已从局部 `QMessageBox` 收口到公共 `MessageDialog`，并同步移除 `env_ip_bindings` / `configs` 的初始化与运行依赖；已有用户库旧表只通过显式 SQL 清理，不写入启动迁移代码。
- 2026-04-25：`docs/02-user-guide/usage.md`、`execution-log.md`、`test-plan.md` 与 `.factory/memory/` 已同步补记运行环境列表的 `env_metadata` 可用状态展示和 IP 测试结果深色面板。运行环境列表当前按 `scheduler.resource_pool` 资格卡片聚合展示可用状态，IP 测试结果弹窗固定深色背景。
- 2026-04-24：模块数据库开发者接口已收口为唯一 `ctx.db` fluent API。`docs/03-developer-guide/`、`docs/04-project-development/04-design/{api-design.md,module-config-runtime-data-contract.md,module-hosted-ui-framework.md,module-entity-table-view-design.md}` 与 `.factory/memory/` 已同步删除旧数据库工具正式口径，并明确 `managed_dataset` 单源读取、`custom_table` 显式 join/group/aggregate、view 只读轻量查询和 read-only view 的边界。
- 2026-04-24：`execution-log.md` 与 `.factory/memory/current-state.md` 已同步补记 IP 池条目编辑持久化缺陷的根因和修复：此前 `ip_entries` upsert 未回写地址/协议/端口/认证字段，现已补齐并新增数据库重载回归 `test_ip_pool.py`。
- 2026-04-24：`docs/02-user-guide/{index.md,usage.md}` 已同步补记 IP 池条目级代理测试口径：当前 `环境管理 -> IP 池管理` 支持对单条 IP 执行真实代理探测，弹窗直接返回是否成功、出口 IP、耗时和失败阶段，且结果不做持久化。
- 2026-04-24：Hosted UI `Card` 现已补齐布局参数口径。`docs/03-developer-guide/{index.md,ui-and-data-table.md}`、`docs/04-project-development/04-design/{module-hosted-ui-framework.md,api-design.md}`、`implementation-plan.md` 与 `.factory/memory/current-state.md` 已同步说明 `title_align`、`content_align`、`content_vertical_align`、`min_height`、`padding` 的正式支持范围。
- 2026-04-24：Hosted UI 现已正式补入 `Card` 容器组件，并明确收口“`Card` 是纯卡片容器、`Section.variant=\"card\"` 只是兼容别名”的口径；`docs/03-developer-guide/ui-and-data-table.md`、`docs/04-project-development/04-design/{module-hosted-ui-framework.md,api-design.md}`、`implementation-plan.md` 与 `.factory/memory/current-state.md` 已同步更新。
- 2026-04-23：开发者指南与设计文档已补记 `managed_dataset` 的最终收口语义：`docs/03-developer-guide/{index.md,quickstart.md,reference-core-capabilities.md}` 与 `docs/04-project-development/04-design/{api-design.md,module-config-runtime-data-contract.md}` 现统一说明 `managed_dataset/custom_table` 都必须先在 `module.yaml.data.resources[]` 注册，未注册资源会被 `db.get_record` / `db.list_records` / `db.replace_records` 直接拒绝，不再按名称隐式创建托管表资源。
- 2026-04-23：`docs/03-developer-guide/` 已把 manifest 驱动数据契约正式收口到开发者入口：`index.md`、`core-concepts.md`、`module-structure.md`、`quickstart.md`、`build-modules.md`、`reference-sdk-and-cli.md`、`debugging.md`、`troubleshooting.md` 现统一说明 `module.yaml.data + data/sql + data/seeds`、CLI `data` 命令组，以及 `db.get_record` / `db.query_view` 新正式口径；`docs/02-user-guide/` 同步补记管理员与现场支持对“旧协议模块包会被直接拒绝加载”的分诊口径。
- 2026-04-22：`module-hosted-ui-framework.md` 已从“设计已批准”推进到“本地实现已落地”，对应的 `implementation-plan.md`、`test-plan.md`、`requirements-matrix.md`、`interface-matrix.md`、`.factory/workitems/` 与 `.factory/memory/` 已同步登记 `CR-011` / `TASK-025` / `TC-049`。
- 2026-04-22：已新增 `module-hosted-ui-framework.md`，将“模块不得直接使用 `PyQt6`、宿主统一托管模块页面、最小化 UI 框架 V1 只公开 `Page/Section/Text/Button/DataTable`”正式沉淀为设计文档；`docs/index.md`、`module-boundaries.md`、`api-design.md`、`interface-matrix.md` 与 `.factory/memory/` 摘要已同步到同一口径。
- 2026-04-22：`deployment-guide.md`、根 `README.md`、`packages/crawler4j/README.md` 与 `.env.example` 已同步补记 macOS Sparkle 内部分发的两项新口径：改写 bundle 后自动 ad-hoc 重签，以及 `generate_appcast` 可通过 keychain account / 私钥文件 / 私钥串读取 EdDSA 私钥，不再只依赖默认 `ed25519` 账户名。
- 2026-04-22：`deployment-guide.md`、运维目录索引、根 `README.md` 与 `packages/crawler4j/README.md` 已同步补记 macOS Sparkle unsigned 内部分发的签名口径：`package-macos-internal-release` 当前会写入 `SUEnableCodeSigningValidation=false` 与空 `SUPackageSigningCertificate`，只关闭宿主 app 的苹果代码签名校验，更新包仍保留 EdDSA 校验。
- 2026-04-21：已修正根 `docs/index.md` 中 `ctrip-real-site-e2e-closeout.md` 对应导航项的非法 YAML 标题写法，并把测试收口页标题与本文件入口统一收口为普通字符串，恢复 `docs-stratego` 对文档根索引的解析。
- 2026-04-21：`docs/04-project-development/06-testing-verification/index.md` 与 `test-plan.md` 已同步补记宿主 `qasync` UI 重入回归：REM 环境列表页的创建/编辑/销毁及异步操作提示现统一走非阻塞对话框，仪表盘刷新则改为取消旧 pending load 后再启动新一轮；对应 `.factory/memory/tests.summary.md` 已新增 `TC-043`。
- 2026-04-20：`docs-stratego` 联动发布口径已从 `feature/task-plugin-system` 收口到 `main`；`deployment-guide.md`、运维目录索引与 notify workflow 现统一说明主分支是唯一自动通知来源，且 dispatch token 会先去掉意外换行再发起 `repository_dispatch`。
- 2026-04-20：固定环境池语义已进一步收紧并同步到开发/设计/测试文档：当前只从 `eligible=true + READY + 无租约` 环境集合发号，`KEEP_ALIVE` 留下的 `RUNNING` 环境不会自动回池；若候选在 `get_env` / 租约阶段被别人先抢走，任务会回到等待席位而不是直接失败；对应 ATM/REM 单测已补锁。
- 2026-04-19：已对固定环境池 / 环境队列开发者文档执行“1 个专业文档 reviewer + 2 个模块开发者 reviewer”的三轮苛刻复核；`docs/03-developer-guide/index.md`、`reference-core-capabilities.md`、`build-modules.md`、`debugging.md`、`troubleshooting.md` 以及 `api-design.md`、`atm-resource-pool-queue-design.md` 现统一钉死 `Service Job` 前提、`resource_pool / selector_name / wait_timeout` 语义、`env_id` 来源、`@env_selector(...)` 入口、`replace_resource_pool_snapshot(...)` 全量重建和等待状态文案分层，最终 3 个 reviewer 全部给出 `无 blocker`。
- 2026-04-19：已新增 `docs/04-project-development/02-discovery/atm-resource-pool-queue-brainstorm.md` 与 `docs/04-project-development/04-design/atm-resource-pool-queue-design.md`，把“模块资源池资格标签 + 宿主等待队列 + FIFO 补位 + 黑号先停发号再销毁”的方案沉淀为正式 discovery/design 输入；根 `docs/index.md` 与 `.factory/memory/doc-map.md` 已同步接入。
- 2026-04-17：`docs/01-getting-started/` 已进一步压缩为单页模式，当前只保留 `了解 crawler4j` 这一篇作为正式入口；正文改为面向客户的产品介绍，不再拆成多页教读者选路径，原辅助页已删除。
- 2026-04-17：新增 `docs/02-user-guide/exception-cases.md`，把“应用打不开、页面空白、模块未启用、执行一次没反应、任务实例全失败、环境不可用、升级失败、结果找不到”统一收敛为按症状分诊的异常案例页；每个案例都固定给出“现象 / 先看哪里 / 先做什么 / 什么情况升级给管理员或研发”，并同步接入 `docs/index.md` 与 `docs/02-user-guide/index.md`。
- 2026-04-17：新增 `docs/02-user-guide/job-detail-guide.md`，把“作业详情整图说明”单独收口为培训讲义页，固定按 `任务实例表 -> 结果/错误 -> 任务日志 -> 成功/失败判据 -> 不同状态下一步动作` 的顺序讲解；当前正文已可直接用于培训。
- 2026-04-20：`docs/02-user-guide/configuration.md`、`system-architecture.md`、`api-design.md` 与 `atm-resource-pool-queue-design.md` 已同步补记 ATM Service Job 的 5 秒兜底巡检改为 `JobController` 挂在主 async loop 上的后台协程循环，不再复用 `APScheduler` 周期 job / `run_coroutine_job()` 包装；启动时先做 bootstrap 调和、作业激活/更新时定向调和，5 秒 periodic loop 仅作后续兜底。统一日志服务对 `APScheduler` 周期性心跳日志仍维持 `WARNING` 下限，对应控制器回归测试与日志口径已同步更新。
- 2026-04-17：`docs/02-user-guide/` 已按“普通用户真正能照着走”的标准做第二次完全重写，正式顺序调整为 `安装与第一次打开`、`首次设置`、`开始使用`、`日常使用`、`管理员指南`；本轮补齐了“新手先点哪 3 个入口”“设置参数从哪里拿”“运行模板入口”“结果只认一个入口”“作业状态下一步动作”“IP 池最短操作闭环”“可复制报障模板”，并同步更新根 `docs/index.md` 导航顺序。
- 2026-04-17：按用户要求执行了 3 个专业产品文档子 agent 分工重写和 6 个普通用户子 agent 两轮苛刻复核。普通用户首轮反馈为 `3 PASS / 3 FAIL`，集中指出入口顺序、参数来源、运行模板入口、状态决策和结果入口收束仍不够傻瓜；二次修订后，第二轮 6 个普通用户子 agent 全部给出 `PASS`，并明确表示愿意将当前 `docs/02-user-guide/` 原样发给新同事使用。
- 2026-04-17：`docs/04-project-development/06-testing-verification/` 新增 `ctrip-real-site-e2e-closeout.md`，把真实站点 E2E 的前置条件、Phase A/B/C 执行顺序、证据要求与放行条件收敛为单一正式入口；发布/运维阅读路径已同步纳入该页。
- 2026-04-17：`docs/03-developer-guide/` 已从旧多层目录重排为产品式平铺结构，首页改为正式开发者入口页，`Quick Start`、`Guide`、`Reference`、调试、交付与排障全部一级直达；旧迁移页与对应入口已下线。
- 2026-04-17：历史记录：开发者指南中的 CLI 命令面当时对齐到 0.3.x `crawler4j-sdk`，使用 `module/task/workflow/page/data-table/env-selector/config/package/release/host/check` 分组命令；当前 0.4.0 命令面以 `docs/03-developer-guide/v0.4.0/` 和 2026-05-01 CLI help 证据为准。
- 2026-04-17：`docs/03-developer-guide/` 已根据 6 个“小白模块开发者”子 agent 的两轮苛刻复核继续补强：新增 `--repo` 占位值说明、`module set default-workflow`、`ui:DashboardPage` / `ui/__init__.py` 导出关系、`TaskResult.data` / `run_subtask()` 真实语义、CLI 宿主桥接与宿主 UI 安装的互斥路径、DevLink/ATM 最短调试判据，以及 `core:data_table` / 调试 / 排障分叉清单；最终 6 个子 agent 全部给出 PASS。
- 2026-04-17：`docs/02-user-guide/configuration.md`、`docs/04-project-development/04-design/module-config-runtime-data-contract.md` 与开发者指南相关章节已统一模块配置 / 运行态 / 单次运行内状态 / 数据表边界；`core:data_table` schema / records 当前只读写 `data.db`，运行时代码不包含旧 `state.db.kv_store` 自动迁移逻辑。
- 2026-04-18：开发者指南与模块运行时数据契约已补齐“快照数据 vs 审计事件”的统一口径：`db.list_records` / `db.replace_records` 与 `core:data_table` 继续只服务当前快照，append-only 历史单独归到审计事件通道；精确工具签名和持久化表名继续以当前宿主实现为准。
