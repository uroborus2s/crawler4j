# 执行记录

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** Tech Lead | 开发 | QA | 发布负责人
**上游输入：** `implementation-plan.md` | 当前任务结论 | 验证结果
**下游输出：** `docs/04-project-development/06-testing-verification/` | `docs/04-project-development/07-release-delivery/` | `.factory/memory/`
**关联 ID：** `TASK-014`, `TASK-015`, `TASK-016`, `TASK-017`, `TASK-018`, `TASK-019`, `TASK-020`, `TASK-021`, `TASK-022`, `TASK-026`, `TASK-027`, `TASK-028`, `CR-004`, `CR-005`, `CR-008`, `CR-012`, `CR-013`, `CR-014`, `API-009`, `API-010`, `BUG-013`
**最后更新：** 2026-05-30

## 1. 用途与记录规则

- 只记录已经开始执行或已经完成的正式事项。
- 每条记录至少说明输入、输出和当前状态。
- 这里记录“发生了什么”，不替代 `implementation-plan.md` 的任务规划职责。

## 2. Wave 11 文档治理整改执行记录

| 日期 | 条目 | 输入 | 输出 | 状态 |
|---|---|---|---|---|
| 2026-04-02 | `TASK-014` 根导航收口 | 文档规范审计、根导航覆盖检查 | `docs/index.md`、`docs/01-getting-started/index.md` | 已完成 |
| 2026-04-02 | `TASK-015` 角色入口重构 | 接手路径审计、四大模块边界 | `docs/02-user-guide/user-guide.md`、`docs/03-developer-guide/index.md`、`docs/04-project-development/08-operations-maintenance/core-maintainer-guide.md` | 已完成 |
| 2026-04-02 | `TASK-016` 过程文档补齐 | 空壳页清理清单 | `software-development-process.md`、`execution-log.md` | 已完成 |
| 2026-04-02 | `TASK-017` 发布文档补齐 | 最小文档包缺口 | `acceptance-checklist.md`、`delivery-package.md` | 已完成 |
| 2026-04-02 | `TASK-018` 运维与管理员文档补齐 | 运维职责边界、用户侧配置说明 | `operations-runbook.md`、`admin-guide.md` | 已完成 |
| 2026-04-02 | `TASK-019` 追踪与索引同步 | 文档索引缺口、接口矩阵缺口 | `interface-matrix.md`、`document-index.md`、`.factory/memory/doc-map.md` | 已完成 |
| 2026-04-02 | `TASK-020` 演进与结构验证收口 | 元数据问题清单、空壳页清理 | `skill-evolution-plan.md`、结构校验记录 | 已完成 |

## 3. 当前未决事项

| 事项 | 当前状态 | 下一步 |
|---|---|---|
| `ctrip` 真实站点 E2E | 未完成 | 回到实现/验证主线继续推进 |
| 根应用正式发布收口 | 未完成 | 在下一次正式发布前执行验收检查清单和交付包清单 |

## 4. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-05-30 | 将根应用 / 运行时版本提升到 `0.4.5`，用于开发模块源码目录保留 `.venv/` 时跳过忽略目录 symlink 的客户端修复版；SDK / Contracts 继续保持 `0.4.1`。本轮只修改客户端版本事实源，正式安装包与更新包仍需后续构建补齐 | Codex |
| 2026-05-30 | 修复开发模块源码目录扫描对 `.venv/` symlink 的误报：Core manifest lock 校验和 SDK 打包文件收集先跳过 `.venv/`、`dist/`、`build/`、缓存目录与 `*.egg-info/`，再对真实模块文件执行 symlink 拒绝；ZIP 内 symlink 与路径穿越安全策略不变。新增 DevLink/源码预检与 SDK `_archive_members()` 回归，定向用例 `4 passed` | Codex |
| 2026-05-26 | 将根应用 / 运行时版本提升到 `0.4.3` 并发布 macOS 客户端更新包：`uv run build crawler4j` 产出 `crawler4j-0.4.3` wheel/sdist，`uv run deploy-macos-internal-release` 产出 `Crawler4j-0.4.3.dmg` 与 `appcast.xml` 并上传远程 macOS 更新目录；Windows 更新包仍需在 Windows 构建机补齐 | Codex |
| 2026-05-26 | 修复 REM 环境列表刷新误触发 GC：刷新按钮改为只从数据库重载环境池并刷新列表，不再执行 `run_gc`，避免外部 provider `exists()` 判定失败时把 READY 环境误删；环境删除继续只通过“清理环境”或显式销毁入口发生。定向回归 `test_env_list_widget.py` 为 `23 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-05-11 | 收口 Hosted UI 内联 `DataTable` 查询契约：Contracts 新增固定 `HostedDataTableQuery` / 泛型 `HostedDataTableQueryResult[RowT]` / `HostedDataTableSortSpec`；runtime bridge 按 `(context, query)` 调用 query handler，不再传 `table_id`；renderer 只从显式 `searchable=True` 的 `DataTable.columns` 推导搜索字段并过滤非法排序字段，未声明列默认不可搜索；要求返回 `HostedDataTableQueryResult`，普通 dict 返回值 fail-fast，结果不再回传 `sort`；同步 SDK 校验、开发者指南、设计文档和 `.factory/memory/`；定向回归 `65 passed`，目标 `ruff check` 与 `git diff --check` 通过 | Codex |
| 2026-05-11 | 收口 `TaskContext` 边界：Contracts 删除 `screenshot()`、`run_subtask()` 和 `_subtask_executor`，保留 Core MMS 实际注入的 `run_page_action()`；核查 Core 未发现真实截图工具实现，REM 能力示例注释不再列 screenshot；同步开发者指南、设计说明和 `.factory/memory/`；定向回归 `31 passed`，目标 `ruff check` 与 `git diff --check` 通过 | Codex |
| 2026-05-11 | 修正 `ctx.db.from_(...).execute()` 默认分页语义：Contracts 仅在显式调用 `.limit(...)` / `.offset(...)` 后写入分页值，Core SQL 渲染缺省分页时不再追加 `LIMIT/OFFSET`，默认读取满足条件的全部行；新增 managed_dataset/custom_table 超过 100 行默认全量读取回归，开发者指南和 `.factory/memory/` 已同步；定向回归 `121 passed`，目标 `ruff check` 与 `git diff --check` 通过 | Codex |
| 2026-05-02 | 收口 REM 批量环境清理确认可读性：环境列表页的“确认批量清理”弹窗不再把待删环境拼成长文本，而是改为表格预览，按 `环境ID / 环境名 / Provider / 来源` 分列展示，并保留搜索与分页，便于核对长任务名和多来源环境；定向回归 `uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_env_list_widget.py -q` 为 `23 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-04-26 | 继续优化模块配置 YAML 可读性：修正 PyYAML 默认 indentless sequence 导致数组显示为父级同列的问题，保存/展示时统一输出为父 key 下缩进的 `- item`；`YamlCodeEditor.setPlainText()` 也会兜底规范化旧的 `key:\n- item` 文本；编辑器字号提升到 15pt，并增加额外行高。定向回归 `21 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-04-26 | 收口模块详情页滚动条与 YAML 编辑器视觉：`YamlCodeEditor` 隐藏横向/纵向滚动条，折叠样式从树状连线改为 plain fold，并弱化缩进参考线；模块详情页左侧菜单、任务链页面、Hosted 页面滚动区和 `SkyDataTable` 也统一隐藏滚动条但保留滚轮/触控板滚动。定向回归 `22 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-04-26 | 跟进资源池声明契约调整客户端交互：ATM 运行模板里的“资源池”由手动文本输入改为下拉选择，选项直接来自当前模块 `module.yaml.resource_pools[]`；未声明资源池时控件禁用，有声明时保留“不使用资源池”选项并展示声明池显示名与池名，避免用户继续手填旧资源池名称。定向回归 `23 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-04-26 | 模块详情页配置编辑器改为 QScintilla YAML 编辑器：新增公共 `YamlCodeEditor`，提供行号、折叠、YAML lexer、错误行标记；新增独立 YAML 验证层，保存前统一校验 YAML 语法、顶层映射对象与重复键，并支持标准 YAML flow mapping 输入后规范化回块格式。定向回归 `28 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-04-26 | 收口固定环境池名称事实源：`ModuleManifest` 新增 `resource_pools[]`，MMS 扫描时校验命名与去重；宿主加载模块运行时时把声明池注入 `ctx.runtime["declared_resource_pools"]`，模块运行时代码可从运行时池名或单一声明池解析 `pool_name`；ATM 运行模板表单和 Job 启动前校验都会阻止引用未声明资源池。定向回归 `106 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-04-26 | 调整“从已有环境导入”执行模型：导入弹窗不再按环境自动新建一次性 Job，而是要求选择已配置的“执行一次”批次任务；可一次选择多个未同步环境，每个环境作为同一 Job 下的 Task 运行，实际并发窗口数由该 Job 的 `concurrency_target` 限制，剩余环境在后台排队补位。定向回归 `29 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-04-25 | 优化公共消息弹窗与公共组件使用：`MessageDialog` 放弃自绘假标题栏，改为对齐“安装模块”面板的原生窗口壳、深色内容区和右下角动作按钮；`StyledButton` 新增 `success` 状态；安装模块弹窗的输入框、浏览/取消/开始检查按钮与校验提示改用公共组件。同步审查 UI 弹窗用法后，已把 ATM/MMS/REM/System 中简单同步提示和确认从 `QMessageBox` 收口到 `MessageDialog` / `ConfirmDialog`。剩余 `QMessageBox` 为环境/模块列表异步 `open()` 流程和任务中止三按钮流程，后续需补公共异步/多动作弹窗能力再迁移 | Codex |
| 2026-04-25 | 收口 IP 测试弹窗公共组件与无关表初始化：新增公共 `MessageDialog` 深色消息弹窗，`IPPoolTab` 的测试结果、普通提示和删除确认改用公共 `MessageDialog` / `ConfirmDialog`，不再直接使用局部 `QMessageBox`；`IPPoolManager` 不再持久化 `env_ip_bindings`，绑定/解绑只直接增减 `ip_entries.bound_count`；`init_database()` 不再创建遗留 `configs` 表。已有用户库中的旧表通过显式 SQL 清理，不写入启动迁移代码 | Codex |
| 2026-04-25 | 运行环境列表补齐 `env_metadata` 可用状态展示：列表加载时合并每个环境的元数据，按 `scheduler.resource_pool` 资格卡片聚合展示 `可用 / 部分可用 / 不可用 / 未标记`，并在 tooltip/search 文本中保留模块、资源池和停发原因；IP 池条目测试结果弹窗改为显式深色背景，避免 macOS 默认浅色消息框导致测试结果低对比。定向回归 `20 passed` | Codex |
| 2026-04-25 | 删除“从已有环境导入”的 provider 扩展字段：REM 环境表、`Environment` 模型与运行参数不再保留 provider 扩展元数据；未同步列表、重复导入复用与状态库唯一索引均改为按 `(provider, name)` 判断，来源名称不存在即视为未同步。定向组合回归 `38 passed`，REM 单测目录回归 `111 passed` | Codex |
| 2026-04-24 | 修复 IP 池条目编辑“保存后重启恢复旧值”缺陷：根因是 `IPPoolManager._persist_entry()` 的 `ip_entries` upsert 只更新 `bound_count/safety_score/expires_at`，没有回写 `address/protocol/port/username/password/pool_id`；因此编辑后当前进程内因为直接修改了内存对象看起来已生效，但应用重启重新从 `state.db` 加载时仍读回旧记录。当前已补齐这些字段的 upsert 回写，并新增 `test_ip_pool.py` 锁定“编辑后重载数据库仍保留新代理字段”回归 | Codex |
| 2026-04-24 | 修正 Hosted UI 页面注册与左侧菜单协议：`pages/` 现在是可路由页面注册表，`module.yaml.ui_extension.pages[]` 只控制左侧菜单；SDK `check full` 不再拒绝未写入菜单的合法页面文件，`page create --no-menu` 可创建详情页/二级页，模块详情页 `open_page` 可跳转到非菜单页面并复用参数刷新。定向回归已覆盖 SDK full 校验、CLI `--no-menu`、integration check 以及模块详情页 row action 跳转 | Codex |
| 2026-04-24 | 继续收口“从已有环境导入”弹窗的风险提示：warning 区域现已改为单层提示卡，内层文字显式固定为 `background: transparent; border: none; padding: 0;`，不再出现额外内圈；同时将 warning 文案收敛为“未标注支持已有环境导入，请由配置者自行判断是否适合这个场景”。当前定向回归 `test_import_existing_env_dialog.py` 通过，且本地 Qt 直出截图 `/tmp/import-existing-env-dialog-fix-v2.png` 已确认无内圈、文案为新版本 | Codex |
| 2026-04-24 | 修复桌面宿主入口与关闭阶段竞态：`src.ui.app` 不再在模块加载期提前拉起 debug worker/debugpy adapter/Shell 的深依赖，而是改为运行时懒加载，解除打包态启动早期的循环导入退出；同时主窗口显示后不再恢复 `quitOnLastWindowClosed`，改由 `lastWindowClosed` 驱动 `_run_application()` 的异步收尾，避免窗口关闭时 `qasync` 事件循环先停、`run_until_complete()` 抛出 `Event loop stopped before Future completed`。定向回归 `test_app.py` 为 `6 passed`，目标文件 `ruff check` 通过，重新打出的 macOS `.app` 已能越过原先的启动即退阶段 | Codex |
| 2026-04-24 | 完成全局环境页“从已有环境导入”链路：`VirtualBrowser` 现可拉取“来源有、本地无”的未同步环境并导入；环境列表页新增 `从已有环境导入` 配置面板，用户可选择 `环境来源 / 目标模块 / 模块工作流 / 未同步环境` 后执行 `导入并执行`；ATM 复用固定 `env_id` 执行链路，模块在 `ctx.env_id`、`ctx.page` 与 `ctx.runtime.creation_params` 中收到来源标记与 `import_mode="existing_env"`。定向回归 `120 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-04-24 | 修复桌面打包遗留问题：删除 `packages/crawler4j/crawler4j.spec` 中已被清理的 `src/ui/styles/dark_theme.qss` data 引用，避免 Windows `package-windows-release` 在 PyInstaller data append 阶段因找不到旧资源而失败；同时补强 `test_packaging_config.py` 锁定 spec 不再引用已删除的 UI 样式目录，并把 README / release 文档 / `.factory` 版本事实源统一更新到 `crawler4j 0.3.1`、最近正式 tag `v0.2.0`。定向回归 `71 passed`，root build 产出 `crawler4j-0.3.1` wheel/sdist，`uv run package-desktop` 本机复验通过 | Codex |
| 2026-04-24 | 按反馈继续收口桌面图标中心主组：在保持外底板 inset `(97, 96, 97, 96)` 不变的前提下，把圆形镜面保持在白底板几何正中，并将手柄从“短尾巴”延长到更接近右下边缘的安全区，但仍保留明显留白，不贴边、不越界；镜面继续保持约占底板宽度的 `80%`。对应图标回归继续锁定蓝色主徽记 bbox `(210, 210, 815, 815)`、左右上下 margin 仅允许 `1px` 误差，以及整组 focus bbox `(210, 210, 846, 850)`，`test_icon_packaging.py` 定向回归 `6 passed`、目标文件 `ruff check` 通过 | Codex |
| 2026-04-23 | 完成代码洁净性专项审查第三轮收口：4 个审查子 agent 与主线程复核确认 `crawler4j-sdk/src/hosted_ui.py` 属于真实阻塞级重复实现，现已改为 `crawler4j_contracts.hosted_ui` 的兼容薄 re-export，并新增 `test_hosted_ui_reexport.py` 锁定 SDK/Contracts 同源实现；同时删除 `src/core/system/update_service.py` 中未被消费的 `UpdateInfo` 占位 dataclass，并清理 ATM 相关测试里对 `normalize_db_view_schema` 的过时兼容垫片。定向回归 `47 passed + 17 passed`，目标文件 `ruff check` 通过；旧安装目录迁移回滚、repo-token 旧命名别名、workflow 旧字段与默认工作流 fallback 作为兼容/契约面问题暂不在本轮删除 | Codex |
| 2026-04-23 | 完成 UI 模块专项审阅收口：Hosted UI 运行时进一步硬化为“纯 UI 边界”，`declare_ui` / page / query handler 不再允许通过宿主能力做数据写入，`ManagedPageRenderer.refresh()` 改为只消费本轮 `declare_ui()` 的内存声明缓存，不再依赖 `module_pages` 持久化 schema；同时 SDK `check full` / `package build` / `package verify` / `page create` 现统一拒绝 legacy `ui/`、`config_schema.json`、`strategy.yaml` 与旧 `ui_extension` 字段。定向回归 `119 passed` | Codex |
| 2026-04-23 | 完成 `TASK-028` / `CR-014`：宿主新增 `module_db_views` 作为数据库视图事实源，运行时提供 `db.declare_db_view` / `db.query_view`，Hosted UI `core:data_table` 新增 `data_source_kind="db_view"` 只读统计表模式并支持过滤、排序、分页；模块卸载提示会列出待删除的数据库视图。V1 当前正式支持 `sql_view`，相关定向回归 `122 passed`、目标文件 `ruff check` 通过 | Codex |
| 2026-04-23 | 完成 `TASK-026` / `CR-012` 纠偏收口：新增 `module_data_resources` 统一登记 `managed_dataset/custom_table`，把 `module_datasets` 升级为支持 `record_key` / `run_status` / `record_status` 的 V3 结构，并把 `custom_table` 从泛型 `record_json` 容器修正为 `schema_version/schema_json/indexes_json` 驱动的受控实体表；`db.declare_data_resource`、`ui.declare_data_table` 与 `core:data_table` 已按资源模式读写托管 dataset 或受控实体表，模块卸载时会给出显著的数据清理提示；相关 unit/integration/acceptance 组合回归 `157 passed`，目标文件 `ruff check` 通过 | Codex |
| 2026-04-23 | 完成 `TASK-027` / `CR-013` 最终收口：Hosted UI 新增 `open_page.params`、表格 `row_action`、模块详情页缓存页参数替换，以及目标 `core:data_table` 的 `navigation_filters`；默认 CRUD 在过滤详情表下已改为对底层全量资源做定点写回，`row_action` 无 `params` 不再透传整行，同时保留显式 `data_resource` metadata 与 omitted `resource_id` alias 路由兼容；最终定向回归 `122 passed`、目标文件 `ruff check` 通过，测试团队结论 `PASS`、审查团队结论 `no blocking findings` | Codex |
| 2026-04-23 | 继续按根因微调 Dock 图标外轮廓：在保持蓝色主徽记 bbox `(284, 258, 741, 715)` 不变的前提下，仅把参数化生成链的外白底板再收 1px；当前运行时回归锁定到底板 inset `(97, 96, 97, 96)`，避免再次把内层主徽记误当成“偏大”根因 | Codex |
| 2026-04-23 | 继续按根因修正 Dock 光学尺寸：保留参数化“白底板 + 放大镜主徽记”两层生成链，只进一步缩小真正偏大的外白底板；当前运行时回归改为锁定到底板 inset `(96, 95, 96, 95)`，蓝色主徽记 bbox 保持 `(284, 258, 741, 715)` 不变 | Codex |
| 2026-04-23 | 收口宿主表格默认“序号列”语义：`SkyDataTable` 已隐藏 Qt 垂直表头，避免把系统行头误显示成业务序号；同时为 `TaskListWidget` 与 `ModuleListWidget` 显式增加 `__index__` 列，并在 provider 侧按分页结果计算全局序号，确保第 2 页从 `3/4...` 继续递增 | Codex |
| 2026-04-23 | 继续推进 `CR-015 / TASK-029` 共享表格基座重构：当前仓库正式宿主表格与 hosted page 内联 `DataTable` 已统一切到纯 UI `SkyDataTable`，并进一步删除 hosted UI 内联表格顶层 `binding` / `rows` 兼容写法，强制页面 schema 显式声明 `data_source`，避免新组件边界再次被旧 schema 渗透 | Codex |
| 2026-04-22 | 继续微调桌面应用图标的壳层占比：将共享图标母版的导出缩放系数从 `0.965` 下调到 `0.964`，统一重建 `app_icon.png` / `app_icon.icns` / `app_icon.ico`，把 macOS Dock 与 Windows 壳层图标再缩小约 1px | Codex |
| 2026-04-23 | 继续收口 Windows 打包版首窗启动竞态：`src.ui.app:_run_application` 在 `Shell.show()/showMinimized()` 之后不再立刻恢复 `quitOnLastWindowClosed`，而是先让 `qasync` 事件循环过一个 tick 再恢复，避免 Windows 安装态在主窗口完成首轮原生注册前就提前退出；对应启动顺序单测与项目记忆已同步更新 | Codex |
| 2026-04-22 | 继续收口桌面应用图标的 Dock 外轮廓占比：新增 `app_icon_master.png -> scripts/rebuild_app_icon_assets.py -> app_icon.png/icns/ico` 的可重复生成链，统一把共享图标按固定比例回缩到更保守的安全区，避免 macOS Dock 中的外轮廓继续比浅色系统图标更大；同时修正图标回归测试里右/下 inset 计算口径，锁定四边安全区范围 | Codex |
| 2026-04-22 | 发布打包目录清理收口：`package-windows-release` 与 `package-macos-internal-release` 现会在真正生成新发布物前先清空各自的 `dist/updates/<platform>/` 目录，避免本地打包或打包后上传继续复用旧 release 产物；对应单测已补齐 Windows/macOS 两条回归 | Codex |
| 2026-04-22 | 修正 Windows 安装态启动与图标对齐：GUI 入口在异步启动阶段会先禁用 `quitOnLastWindowClosed`，等主窗口显示后再恢复，避免 Windows 打包版在首窗显示前提前停掉事件循环；同时 `package-windows-release` 现在会把 `app_icon.ico` 一并传给 Velopack，确保安装器/快捷方式与 `Crawler4j.exe` 图标一致 | Codex |
| 2026-04-22 | 补齐 Windows 桌面壳层图标资源：在既有 `app_icon.png` / `app_icon.icns` 之外新增 `app_icon.ico`，并让 PyInstaller 在 macOS 继续绑定 `icns`、在 Windows 改绑 `ico`，避免 Windows `Crawler4j.exe` 继续显示旧图标；同时更新桌面发布说明与图标打包回归测试 | Codex |
| 2026-04-22 | 完成 hosted UI V1 二轮问题收口：模块详情页对宿主页入口改为 lazy instantiate，避免详情页打开时提前执行未选中页面的 `declare_ui()` / `load_handler`，并在再次选中已有 hosted page 时自动 refresh；`ModuleUIRuntimeBridge` 改为“`declare_ui` session 仅供下一次 non-declare hook 单次消费”，data-table handler 执行前也会先刷新声明会话，并通过 UI 声明 staging buffer + `replace_declared_ui()` 保证 schema 原子替换；SDK `check full` / `package build` / `package verify` 现统一补齐 hosted page / data table handler 契约校验并阻断 legacy `ui/` 目录；相关 unit/integration/acceptance 合并回归 `130 passed`，定向 `ruff check` 通过 | Codex |
| 2026-04-22 | 继续收口桌面应用图标的 Dock 光学尺寸：先对标本机系统圆角方形图标在 `1024x1024` 画布中的外轮廓占比，再在保持外底板占比不变的前提下单独缩小中心蓝色徽章与放大镜组，避免在 Dock 中比系统常见应用图标显得更大；同时把图标回归测试补成“透明圆角 + 中轴安全区 + 浅色暖灰底板 + 蓝色主徽记 + 中心主标”断言 | Codex |
| 2026-04-21 | 对齐 VirtualBrowser `addBrowser` 官方代理口径：创建环境时把代理 `protocol` 统一转成大写 `HTTP/HTTPS/SOCKS5`，并在 `addBrowser` 返回非 2xx 或 `success=false` 时把状态码与响应正文透传到宿主日志和异常消息，便于继续定位代理/IP 池创建失败；同步补充 REM 单测锁定协议归一化与 `500` 正文回传 | Codex |
| 2026-04-26 | 统一任务启动进度处理：新增 Shell 级 `TaskProgressPresenter` 订阅 `TASK_PROGRESS` / `TASK_STARTED` / 终态事件，ATM 手动执行、REM 已有环境导入和导入队列均通过同一全局任务进度弹窗展示；环境页不再轮询导入 task 的 `PENDING -> RUNNING`，后台排队环境也会发布统一排队进度。聚焦回归 `59 passed`，ATM/REM/UI 宽回归 `351 passed`，全量 `747 passed`，`ruff check .` 通过 | Codex |
| 2026-04-18 | 完成 `TASK-022` / `CR-008`：为模块新增 `module_audit_events`，后续收口为 `ctx.db.audit(...).append/query`，并把快照数据与审计事件契约同步到正式文档、测试计划与 `.factory/memory/` | Codex |
| 2026-04-02 | 新增正式执行记录页并登记 Wave 11 文档治理整改结果 | Codex |
| 2026-04-15 | 修复 VirtualBrowser 创建后 CDP 连接过早失败；补 REM post-create connect 语义与单测 | Codex |
| 2026-04-15 | 收敛 REM 手动创建环境边界；移除 post-create workflow 配置并改为创建后保持 RUNNING | Codex |
| 2026-04-15 | 收敛 REM 创建成功反馈；创建后仅刷新列表，不再弹成功提示框 | Codex |
| 2026-04-15 | 收敛 ATM 生命周期：删除 TaskScript/TaskFlow 私有 hooks，引入 `TaskSignal` 与 `WAITING_CONFIRMATION`，移除运行模板清理策略 UI | Codex |
| 2026-04-17 | 完成 SDK / Contracts `1.2.0` 版本收口；同步 `__version__`、依赖基线、脚手架默认版本范围与开发者文档口径 | Codex |
| 2026-04-15 | 按方案 A 落地 ATM 手动批次任务：新增 `BATCH + MANUAL` 的“执行一次”模式，并补任务创建页/列表页交互与回归测试 | Codex |
| 2026-04-15 | 按方案 A 收敛运行模板资源配置：拆成“创建环境 / 选择环境”，并让 provider / 匹配规则真正进入 REM 选环境链路 | Codex |
| 2026-04-15 | 继续收敛运行模板创建环境页：将执行脚本选择并入基础信息区，按 VirtualBrowser 现有交互重做指纹参数表单，补官方 `addBrowser` 指纹参数透传与 IP 池绑定策略下发，并移除 `retry`；随后补齐浏览器版本下拉、默认 `145`、内核自动匹配，以及 UA 的默认 / 自定义 / 随机交互 | Codex |
| 2026-04-15 | 继续收敛 VirtualBrowser 指纹配置交互：将 `Canvas` / `WebGL 图像` / `WebGL 元数据` / `WebGPU` / `AudioContext` / `ClientRects` / `Speech Voices` 改为按钮式模式切换，并补 `WebGL 厂商` / `渲染` 的选项式输入与 UI 单测 | Codex |
| 2026-04-15 | 修复 VirtualBrowser 长文本下拉框宽度：`WebGL 厂商` / `渲染` 现在会按内容自动扩宽控件本身和弹出列表，并补 UI 单测 | Codex |
| 2026-04-15 | 调整运行模板弹窗宽度：默认宽度从屏幕的 `50%` 提升到 `60%`，即比原来增大 `20%`，并补 UI 单测锁定尺寸口径 | Codex |
| 2026-04-15 | 修复 `Do Not Track` / `硬件加速` 开关 UI：替换成自绘滑动开关，修正深色主题下的滑块缺失问题，并补交互单测 | Codex |
| 2026-04-16 | 修复任务创建页“运行配置”更新按钮被压缩的问题：改为按文案计算最小宽度并左对齐放置，避免“重新编辑运行模板”被挤压，并补 UI 单测 | Codex |
| 2026-04-15 | 微调 VirtualBrowser 创建默认值：新建创建环境时默认开启“创建后随机化指纹”，UA 默认回填为自定义随机值，并加高 UA 编辑框以完整显示内容 | Codex |
| 2026-04-15 | 继续对齐截图交互：将 `设备名称` / `MAC地址` / `SSL` / `端口扫描保护` / `启动参数` 改成分段按钮，将 `Do Not Track` / `硬件加速` 改成开关，并把新建默认值收敛到 `AudioContext` / `ClientRects` / `Speech Voices=随机`、`内存=8GB`、设备名与 MAC 默认自定义随机值 | Codex |
| 2026-04-15 | 修复运行模板执行脚本下拉：界面优先展示工作流 `display_name`，保存与运行仍保持 `workflow.name` 契约，并补 UI 单测 | Codex |
| 2026-04-15 | 修复运行模板执行脚本模块下拉空白项：移除空默认选项，改为 placeholder 未选中态，并补 UI 单测 | Codex |
| 2026-04-16 | 调整应用启动默认宽度与任务监控操作列：主窗口默认宽度改为 `1420px`，任务监控“操作”列放宽到 `240px`，避免按钮文案被截断，并补 UI 单测 | Codex |
| 2026-04-16 | 优化 ATM 手动批次“执行一次”交互：点击后列表立即显示“执行中”并禁用按钮，直到任务终态与环境回收完成后才恢复可执行，并补 UI/服务回归测试 | Codex |
| 2026-04-17 | 继续优化 ATM 手动批次“执行一次”反馈：新增列表级“环境启动中”启动条与行内状态，环境真正启动后自动隐藏；同时把 VirtualBrowser `launchBrowser` 的具体错误透传到顶部 Toast，避免用户误判为点击无响应 | Codex |
| 2026-04-18 | 完成 ATM 手动批次“中止”闭环：手动执行一次在启动中/执行中时主按钮改为 `⏹ 中止`，弹窗支持“保留环境中止 / 删除环境中止”（删除仅限创建环境模式）；同时 `WAITING_CONFIRMATION` 任务也会被 stop 直接收口为 `CANCELLED`，`on_cleanup` 调整为先于环境动作执行，并补 ATM/UI 回归测试与开发者文档 | Codex |
| 2026-04-18 | 修复 ATM 手动批次“中止不了”缺陷：`ExecutionRunner` 现在会主动 cancel 运行中的模块协程，不再只记录 stop request；`TaskContext.wait()` / `run_subtask()` 在 stop 后会尽快抛 `asyncio.CancelledError`，并补 ATM/SDK 回归测试与开发者契约说明 | Codex |
| 2026-04-16 | 收敛 ATM 环境回收语义：任务完成、创建失败与僵尸任务恢复均只关闭并回收环境，不再自动删除；只有模块显式发送 `EnvAction.DESTROY` 时才执行环境销毁，并同步新默认生命周期与回归测试 | Codex |
| 2026-04-16 | 移除运行模板中的“生命周期”兼容控件：前端不再展示任何环境删除策略入口，保存运行模板时固定写入非自动删除语义，并补 UI 回归测试 | Codex |
| 2026-04-16 | 收敛 REM 命名语义：将 `EnvironmentManager.reset()` 更名为 `recycle_env()`，明确其仅执行关窗回收和任务解绑，不表示清空浏览器持久数据，并补 ATM 回归测试 | Codex |
| 2026-04-16 | 完成 `TASK-021` / `CR-004`：为 `TaskSignal.wait_for_confirmation` 增加任务 signal 持久化、`task.signal` 事件和 ATM 详情页结构化确认面板，客户端可按 `payload.confirmation` 展示字段并调用既有确认服务完成任务收尾 | Codex |
| 2026-04-16 | 调整模块自定义数据列表横向滚动表现：隐藏底部横向滚动条，但保留触控板/滚轮横向滑动能力，并补 `ModuleDataTablePage` 回归断言锁定滚动策略 | Codex |
| 2026-04-16 | 完成 `BUG-013` / `CR-005`：`ModuleAssembler` 发现 `tasks/` / `workflows/` import 失败时改为输出异常上下文与 traceback，并在命中失败条目时向运行时回传 discovery hint；ATM 普通执行 `DevLink` 模块时也会显式开启一次性 reload，无需重启主客户端即可吃到最新源码 | Codex |
| 2026-04-24 | 收口 Windows 打包态 `qasync` 停环竞态：宿主入口新增 `_ShutdownController`，显式拦截 `QEvent.Type.Quit` 并把真正退出延后到异步清理完成之后；同时补 `Quit`/`lastWindowClosed` 两条 UI 生命周期回归，避免桌面包再次弹出 `Event loop stopped before Future completed` | Codex |
| 2026-04-24 | 收口共享表格删除确认框配色：`ConfirmDialog` 改为完整深色主题，补齐标题/正文/取消按钮/危险按钮的对象名与样式选择器，避免 macOS 下删除确认面板继续出现黑字/浅底等系统默认配色；同时新增组件级 UI 回归 `test_confirm_dialog.py` | Codex |
| 2026-04-24 | 为 Hosted UI `Page` 增加页面级滚动配置：`crawler4j_contracts.hosted_ui.normalize_page_schema()` 现支持 `scroll.vertical = auto|hidden`，`ManagedPageRenderer` 会按页面 schema 切换外层 `QScrollArea` 的竖向滚动条策略；同时新增契约回归 `test_hosted_ui_card.py` 与隔离渲染回归 `test_managed_page_scroll.py`，用于收口“今日运营看板”右侧滚动槽 | Codex |
| 2026-04-24 | 收口模块数据库开发者接口：运行时只向模块暴露 `ctx.db` fluent API，旧 `ctx.tools.call("db.*")` 工具面退出正式协议；同步补齐 managed/custom/view/read-only view 查询边界、旧调用扫描和定向回归 `159 passed` | Codex |

## 5. 2026-04-15 缺陷修复记录

| 日期 | 条目 | 输入 | 输出 | 状态 |
|---|---|---|---|---|
| 2026-04-15 | VirtualBrowser 创建后连接失败排查 | 用户复现截图、`crawler4j.log` 中 `env-20260415-3` 与多次 `connect_over_cdp` 400 记录 | `packages/crawler4j/src/core/rem/handle.py`、`packages/crawler4j/src/core/rem/manager.py`、对应 REM 单测 | 已完成 |
| 2026-04-15 | REM 手动创建环境边界收敛 | 用户确认 REM 只负责运行环境生命周期；手动创建成功后保持 `RUNNING` | `packages/crawler4j/src/core/rem/manager.py`、`packages/crawler4j/src/core/rem/ui/env_list_widget.py`、`packages/crawler4j/src/core/atm/execution_runner.py`、相关单测与文档/记忆 | 已完成 |
| 2026-04-15 | REM 创建成功反馈收敛 | 用户要求创建成功后不弹窗，只刷新运行环境列表 | `packages/crawler4j/src/core/rem/ui/env_list_widget.py`、对应 UI 单测、执行记录与 `.factory/memory/` 摘要 | 已完成 |
| 2026-04-15 | ATM hooks / 信号系统重构 | 用户要求统一为 ATM hooks，删除脚本/工作流私有 hooks，并用统一信号承接清理环境、等待人工确认等流程动作 | `packages/crawler4j-contracts/src/signal.py`、`packages/crawler4j-sdk/src/{base,workflow,assembler,context,signal}.py`、`packages/crawler4j/src/core/atm/{execution_runner,dispatcher,service,run_profile,ui/run_profile_dialog}.py`、相关单测与开发文档 | 已完成 |
| 2026-04-15 | ATM 手动批次模式落地 | 用户确认采用方案 A：不新增 JobType，而是在 `BATCH` 下增加 `MANUAL` 触发，UI 提供“执行一次”入口 | `packages/crawler4j/src/core/atm/{service.py,ui/task_create_dialog.py,ui/task_list_widget.py,ui/task_detail_dialog.py}`、`packages/crawler4j/tests/unit/test_core/test_atm/{test_job_modes.py,test_task_create_dialog.py,test_task_list_widget.py}`、用户/管理员说明与 `.factory/memory/` | 已完成 |
| 2026-04-15 | 运行模板资源配置收敛 | 用户要求把运行模板资源页简化为“创建环境 / 选择环境”两条路径，并删除无效参数 | `packages/crawler4j/src/core/atm/{dispatcher.py,execution_runner.py,job_runtime.py,ui/run_profile_dialog.py,ui/task_create_dialog.py}`、`packages/crawler4j/src/core/rem/{models.py,pool.py,provider.py}`、相关 ATM/REM 单测、用户说明与 `.factory/memory/` | 已完成 |
| 2026-04-15 | 运行模板创建环境页二次收口 | 用户要求删除失败重试、把基础信息和执行脚本选择合并，并按 VirtualBrowser 现有交互页重做指纹参数配置 | `packages/crawler4j/src/core/atm/{run_profile.py,ui/run_profile_dialog.py,ui/task_create_dialog.py}`、`packages/crawler4j/src/core/atm/execution_runner.py`、`packages/crawler4j/src/core/rem/{models.py,ip_pool.py,manager.py,provider.py}`、相关 ATM/REM 单测、用户说明与 `.factory/memory/` | 已完成 |
| 2026-04-16 | ATM 模块日志可见性修复 | 用户反馈“执行一次”后携程手动登录脚本看起来没有执行；本地 `crawler4j.log` 已确认执行链进入 `ctrip.run(...)` 但模块 `ctx.logger` 日志未进入主日志 | `packages/crawler4j/src/core/atm/execution_runner.py`、`packages/crawler4j/src/core/mms/ui/module_data_table_page.py`、`packages/crawler4j/tests/unit/test_core/test_atm/test_execution_runner.py`、`.factory/memory/current-state.md` | 已完成 |

### 结论

- `env-20260415-3` 在 2026-04-15 14:15:06 至 14:15:09 已完成环境创建和窗口打开，但 `connect_over_cdp` 在约 1 秒内连续 3 次失败，工作流没有进入执行阶段。
- 2026-04-14 的成功日志显示同一路径下 `Opened browser -> Connected Playwright` 最长可超过 2 秒，因此原有重试预算不足，属于真实缺陷而非误操作。
- post-create 链路在 connect 失败后会自动关闭窗口，因此不应再弹出“浏览器窗口已打开”的保留态提示；该提示只保留给手动启动场景。
