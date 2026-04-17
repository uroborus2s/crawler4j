# 当前状态

- 当前模式：Default
- 当前阶段：IMPLEMENTATION
- 活跃任务：13
- 活跃变更：3
- 活跃缺陷：5
- 活跃 PR：0

- 角色目录总数：9
- 当前阶段主要角色：项目协调者、后端工程师、前端工程师、测试工程师、文档与记忆管理员

- 当前技术画像：Crawler4j Model 项目画像
- 技术画像预设：crawler4j-model
- 关键工程规则数：5
- 设计交付物数：1

## 最近条目

- 任务：TASK-011-mms-settings-store-and-module-state-persistence、TASK-012-mms-trust-gate-and-custom-ui-loading、TASK-013-stabilize-module-root-entry-shim-and-sdk-assembler、TASK-021-add-signal-driven-confirmation-panel
- 变更：CR-001-version-and-release-governance-alignment、CR-002-quality-gate-and-docs-navigation-alignment、CR-003-mms-settings-and-ui-extension-compliance、CR-004-atm-signal-driven-confirmation-ui、CR-005-devlink-run-once-reload
- 文档：2026-04-17 已把 `docs/03-developer-guide/` 统一收口到当前 `crawler4j-sdk` 命令树与模块契约，正式口径不再固定 `crawler4j-sdk==某个版本`；首页、quickstart、CLI 参考、调试、交付与排障现统一以 `module/task/workflow/page/data-table/env-selector/config/package/release/host/check` 分组命令和最新帮助输出为准，旧迁移页已删除。
- 文档：2026-04-17 已对仓库根与各子包 `README.md`、包 `pyproject.toml` 描述、`release-notes.md`、`version-governance.md` 和 `.factory` 版本摘要做发布前复核，移除了 `packages/crawler4j/modules/` 这类不存在目录的错误说明，并把当前源码版本口径统一收敛为 `crawler4j / crawler4j-sdk / crawler4j-contracts 0.2.0`，同时保留“最近正式 Git tag 仍为 `v0.1.1`”的分层描述。
- 文档：2026-04-17 已根据“小白模块开发者”苛刻审稿完成第二轮修订：补齐了 `--repo` 占位值说明、`module set default-workflow`、`ui:DashboardPage` / `ui/__init__.py` 导出关系、`TaskResult.data` / `run_subtask()` 真实语义、`host install` 与宿主 UI 两条互斥安装路径、DevLink/ATM 最短调试判据、`core:data_table` 最短分叉排障，以及 `reference-sdk-and-cli.md` 的完整可复制命令前缀。
- 文档：2026-04-17 已完成 6 个“小白模块开发者”子 agent 二轮复核，分别覆盖上手、命令复制、调试、交付四类场景，最终全部给出 PASS；当前 `docs/03-developer-guide/` 可直接作为标准模块开发主手册使用。
- 文档：2026-04-17 `docs/02-user-guide/` 已完成第二次完全重写并按真实普通用户路径重新排序为 `安装与第一次打开 -> 首次设置 -> 开始使用 -> 日常使用 -> 管理员指南`；本轮新增“新手只看 3 个入口”“参数来源表”“运行模板入口固定说明”“结果只认一个入口”“作业状态下一步动作”“IP 池最短闭环”“可复制报障模板”，根 `docs/index.md` 导航顺序已同步调整。
- 文档：2026-04-17 `docs/01-getting-started/` 已进一步压缩为单页模式，当前只保留 `了解 crawler4j` 这一篇作为正式入口；正文改为面向客户的产品介绍，不再拆成多页教读者选路径，原辅助页已删除。
- 文档：2026-04-17 已新增 `docs/02-user-guide/exception-cases.md`，面向普通用户与现场支持按症状收敛“应用打不开、页面空白、模块未启用、执行一次没反应、任务实例全失败、环境不可用、升级失败、结果找不到”8 类异常；每个案例统一采用“现象 / 先看哪里 / 先做什么 / 什么情况升级给管理员或研发”结构，`docs/index.md`、`docs/02-user-guide/index.md`、`document-index.md` 与 `.factory/memory/doc-map.md` 已同步接入。
- 文档：2026-04-17 已新增 `docs/02-user-guide/job-detail-guide.md`，把“作业详情整图说明”单独收口为培训讲义页；正文固定按 `任务实例表 -> 结果/错误 -> 任务日志 -> 成功/失败判据 -> 不同状态下一步动作` 讲解，当前内容可直接用于培训。
- 文档：2026-04-17 已为桌面客户端新增 `📘 使用文档` 树形导航页；现已收口为“文档中心”结构，左侧最上面是直接打开 `01-getting-started/index.md` 的顶层文档 `开始前`，其余内容再按 `使用指南 / 开发指南` 两组展示；分组标题使用可见的文字箭头并支持整行点击展开/收起，右侧不再显示重复的标题/副标题/当前文档头部；文档页现已改为在资源加载阶段按正文可视宽度缩放本地截图，避免 `QTextBrowser` 被原始大图撑爆，并在文档加载后统一把 Markdown 链接改成高对比浅蓝加下划线，避免沿用 Qt 默认深蓝；开发态始终直接读取工作区 `docs/`，打包态读取构建时拷入包内的 docs 快照；当前 PyInstaller spec 已显式包含 `docs/index.md`、`docs/01-getting-started/`、`docs/02-user-guide/` 与 `docs/03-developer-guide/`，正式发布包可直接按 Markdown 展示上述文档，文内相对跳转与截图在客户端内可直接查看。
- 文档：2026-04-17 已按用户要求对当前 `docs/02-user-guide/` 执行“3 个专业产品文档子 agent 分工重写 + 6 个普通用户子 agent 两轮苛刻复核”闭环；普通用户首轮反馈为 `3 PASS / 3 FAIL`，集中指出入口顺序、参数来源、运行模板入口、状态决策和结果入口收束仍不够傻瓜，补齐后第二轮 6 个普通用户全部转为 `PASS`，并明确愿意把文档原样发给新同事。
- 文档：2026-04-17 已新增 `docs/04-project-development/06-testing-verification/ctrip-real-site-e2e-closeout.md`，把 `ctrip` 真实站点 E2E 的前置条件、DevLink/ZIP 双链路执行顺序、证据要求和放行条件收敛为单一正式入口；`test-plan.md`、`acceptance-checklist.md`、`document-index.md` 与 `.factory/memory/doc-map.md` 已同步接入。
- 维护资产：2026-04-17 已清理仓库根 `scripts/` 中不再进入正式调试链或发布链的历史残留脚本，当前只保留 `db_cli.py` 与 `smoke_test_ui.py` 两个维护脚本；对应 README 与 `test_packaging_config.py` 已同步更新。
- 最新修复：2026-04-17 已把 `playwright_local` 从“环境创建成功但无 `page` 可用”修到真实站点可执行：Provider 现在会真实拉起本地 Playwright 浏览器，优先尝试 bundled Chromium，再回退 system Chrome；对应 `test_playwright_provider.py` 已锁定 open/connect/close/reset/health_check 语义。真实 `ctrip` 回放已能进入登录页，业务失败也会正确落到任务失败而不是 workflow 假绿。
- 最新修复：2026-04-17 已继续收口 `VirtualBrowser` 观测与恢复链：`VirtualBrowserClient.launch_browser()` 现会把可恢复的 `launchBrowser` 错误写入主日志，并把 `browser is running` 冲突纳入 stop-then-retry；新增回归测试覆盖 `500 DevTools port` 与 `400 is running` 两类恢复路径。通过直接调用 `localhost:9002` 的 `addBrowser -> launchBrowser`、冷启动外部应用、复用旧 worker 和 `chrome_version=139..146` 扫描，已确认当前剩余阻塞收敛为外部 VirtualBrowser 运行时故障，不再是宿主 REM 配置或 provider 默认值问题。
- 最新修复：2026-04-16 已把 ATM 与 `core:data_table` 构造的 `TaskContext.logger` 接到统一应用日志器，模块 `before_run()` / workflow / task script 的 `ctx.logger` 输出会进入主日志，便于确认“执行一次”是否真正进入模块执行链；同日又修复任务监控里手动批次作业的 `▶ 执行一次` 交互，点击后会立即进入“执行中”禁用态，并以活跃任务计数为准，在任务终态和环境回收完成后自动恢复可点击；本次再把 ATM 默认环境收尾语义收敛为“任务结束只关闭并回收到 READY”，创建环境失败和僵尸任务恢复也不再自动销毁环境，只有模块显式发出 `EnvAction.DESTROY` 信号时才允许删除环境；随后又把运行模板里残留的“生命周期”兼容控件彻底移除，前端不再暴露任何自动删除环境选项；现在又将 `EnvironmentManager.reset()` 正式更名为 `recycle_env()`，明确该动作只是关窗回收并解除任务占用，不代表清空 cookie、指纹或代理配置；本次再为 `TaskSignal.wait_for_confirmation` 补齐任务 signal 持久化、`task.signal` 事件和 ATM 详情页结构化确认面板，客户端可按 `payload.confirmation` 展示字段并直接回调既有确认服务；现在又把模块自定义数据列表底部横向滚动条设为隐藏，同时保留触控板/滚轮横向滑动，并补回归断言锁定滚动策略；这次继续修复 `ModuleAssembler` 发现期静默吞错问题，task/workflow import 失败会进入主日志并在命中失败条目时向运行时回传 discovery hint；同时为 DevLink 普通执行补齐一次性 reload 语义，改完源码后下一次 ATM 执行可直接吃到新代码。
- 最新修复：2026-04-16 已删除脚手架与客户端内残留的声明式 `ui/config_schema.json` / `strategy.yaml` 链路；`module.yaml` 继续作为唯一模块清单，默认配置页改为只读取宿主持久化的模块设置，代码型页面脚手架也已收敛为 `page create` 只生成 `micro_app` 页面。
- 最新修复：2026-04-16 已把模块持久配置从旧 `configs` 聚合键迁到 `config.db.module_config_entries`，`ctx.get_config()` 现只读取模块/工作流配置；ATM 与 Debug 注入链中的 `workflow`、`execution.params`、`job.params`、`devel_mode`、`creation_params` 已全部改走 `ctx.runtime`，不再污染模块配置命名空间；旧 KV 配置兼容迁移与旧 workflow 配置兜底路径已删除。
- 最新修复：2026-04-17 已把真实生效的模块详情页补回 `配置` 标签，宿主现在直接提供模块级配置与工作流级覆盖的 YAML 编辑器，并显式拒绝 JSON/花括号对象字面量；`core:data_table` 的 schema 与 dataset records 当前只认 `data.db`，运行时代码不包含旧 `state.db.kv_store` 自动迁移逻辑；SDK CLI 现已提供 `data-table create` 并把 `detail_menu` 收敛为受控的 `core:data_table:<view_id>` 入口，代码型 UI 只允许单一 `ui_extension.entry`。
- 最新修复：2026-04-17 已重排模块详情页 `配置` 标签布局：移除了模块配置与 Workflow 配置外层卡片框，页面主体改为可拖拽的纵向分隔布局，默认按“模块配置约 70% / Workflow 配置约 30%”分配高度；用户可直接拖动中间分隔条手动调整两个 YAML 编辑区的可视高度，长模块配置不再被底部区域挤压得过于局促；两个编辑区右侧纵向滚动条默认隐藏，但滚轮与触控板滚动仍可用。
- 最新修复：2026-04-17 已为 `module.yaml` 增加 `config_defaults` 契约；宿主首次加载模块时会按 `config_defaults.module` / `config_defaults.workflows` 初始化 `config.db.module_config_entries` 一次并写入初始化标记，后续升级与刷新不再自动覆盖；模块详情页新增“恢复模块默认 / 恢复 Workflow 默认”按钮，并在警告确认后按当前 manifest 模板重写对应 scope。
- 最新修复：2026-04-17 已补齐 `docs/04-project-development/04-design/module-config-runtime-data-contract.md`，并把开发者指南中的 `ctx.config`、`ctx.runtime`、`ctx.state`、`db.*` 使用边界同步为统一规范，供模块开发者按同一契约开发。
- 最新修复：2026-04-17 已把模块分发契约收敛到 `module.yaml.upgrade_source`；正式模块安装入口现支持 `本地 ZIP` 与 `GitHub 源 URL` 双模式，安装前会校验 GitHub 仓库是否存在；DevLink 注册同样执行清单与升级源预检；模块管理页新增 `检查更新` 与行级 `升级` 按钮，正式模块可按 GitHub Release 自动下载并执行原子升级，运行中任务会阻断升级。
- 最新修复：2026-04-17 已开始重构 `crawler4j-sdk` CLI V1，旧平铺命令树已被 `module / task / workflow / page / data-table / env-selector / config / package / release / host / check` 分组体系替换；脚手架不再创建 `data/` 抽象层，`data-table create` 会直接维护 `detail_menu` 并在 `module_runtime.py` 追加 `declare_ui` 骨架，`check` 也已强化为 `structure / release / full` 三档 gate，且 SDK CLI 现已补上 `release publish` 以及宿主桥接命令 `host devlink/install/upgrade/debug config`。
- 最新修复：2026-04-17 已补齐 `crawler4j check full` 的导入失败收敛逻辑：当生成模块的 `module_runtime.py` 或 `ui/__init__.py` 本身存在缺失依赖/导入错误时，CLI 现在会输出明确的文件级校验错误并返回失败，不再直接抛出 traceback；新增回归测试已锁定这两条失败路径，`uv run pytest -q` 当前为 `337 passed`。
- 最新修复：2026-04-16 已压缩仪表盘页面上半部分的标题区、统计卡高度与纵向间距，并抬高“系统实时日志”区域的最小高度；默认窗口尺寸下首页可见日志行数明显增加，便于直接观察任务执行输出。
- 缺陷：BUG-003-pyqt-runtime-blocked-by-system-policy、BUG-004-zip-upgrade-leaves-stale-files、BUG-005-hybrid-acquisition-mode-declared-but-rejected、BUG-013-module-assembler-import-errors-hidden

## 下一步建议

- 检查任务人天估算是否真实合理，仅在必要时再细化到 0.5 人天精度
- 若进入设计或实施阶段，先确认 `docs/04-project-development/04-design/technical-selection.md` 已明确框架、模块、后台范围和编码规则
- 模块入口自动托管方案已闭环，后续优先处理真实站点 E2E 与发布收口
- 执行 `ctrip` 真实站点 E2E 时，统一按 `docs/04-project-development/06-testing-verification/ctrip-real-site-e2e-closeout.md` 收口，不再用临时聊天清单替代正式步骤
- 优先处理外部 VirtualBrowser 运行时故障；当前 `localhost:9002` 上直接 `addBrowser -> launchBrowser` 也会稳定报 `Failed to detect DevTools port`，在外部应用恢复前不要把该阻塞继续归因到宿主 REM 代码
- 调试模块 UI 时，优先使用 DevLink 并在详情页通用数据表中点击“刷新”验证最新 `declare_ui` / handler 行为
- 若 UX/UI 需要可视化评审，优先登记真实设计交付物而不是只写文字
- 若工作项进入收尾，确认关联 PR 已完成评审并合并
- 阶段切换前先更新正式文档，再刷新 `/.factory/memory/` 压缩记忆
