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
- 文档：根 `docs/index.md` 已补全四大模块目录树和 `docs/03-developer-guide/` 正式导航；第二部分 `docs/02-user-guide/` 已拆分出 `admin-guide.md`；第五部分 `docs/04-project-development/05-development-process/` 已补齐 `execution-log.md`；第七、八部分已补齐 `acceptance-checklist.md`、`delivery-package.md`、`operations-runbook.md`；`interface-matrix.md`、`software-development-process.md`、`skill-evolution-plan.md` 已从占位页重写为正式文档；`REQ-006` / `TASK-013` 已完成实现、测试与文档收口；`core:data_table` 的 `declare_ui` / create/update handler 契约与 DevLink 调试刷新语义已同步到正式文档；ATM 已收敛到“任务直接配置 RunProfile”的单入口，侧边栏和内部 `TSM` 依赖均已删除；`TaskContext` 的宿主扩展能力已统一收敛到 `ctx.tools.call(...)`；2026-04-15 已修复 VirtualBrowser 创建后 CDP 连接重试预算过短的问题，并把 REM 手动创建环境边界收敛为“只负责 create/open/connect 并保持 RUNNING”，移除创建页中的 post-create workflow 编排；创建成功后的 UI 反馈也已收敛为只刷新列表，不再弹成功框；ATM 生命周期现已进一步收敛为单一 `module_runtime.py` hooks + `TaskSignal` 信号系统，`TaskScript` / `TaskFlow` 私有 hooks 与运行模板清理策略 UI 已移除；同日已按方案 A 将任务创建页补成 `批次任务 + 执行一次/Cron` 双模式，手动批次通过列表页 `▶ 执行一次` 即时发起且不进入长期 `ACTIVE`；运行模板资源配置现已完全移除规则匹配模式，“选择环境”只接受模块在 `module_runtime.py` 里声明的 `@env_selector(...)` 回调，宿主会把全部 `ready` 浏览器环境候选交给模块选择，UI 对 `return_none` 占位选择器会直接提示函数返回了 none；脚手架也已把 `module_runtime.py` 收敛为标准文件，默认生成 `return_none` 与 `random_ready` 两个选择器示例；运行模板的“创建环境”表单现已把基础信息和执行脚本选择合并到同页，并按用户提供的 VirtualBrowser 交互页重做为显式指纹表单；`virtualbrowser` 自定义指纹参数会直接进入官方 `addBrowser` 请求体，IP 池绑定策略也会跟随创建参数下发；`retry` 已从运行模板模型和 UI 中删除，失败即结束；同日又补齐了浏览器版本下拉与 UA 的“默认 / 自定义 / 随机”交互，项目默认浏览器版本改为 `145`，UA 随机按钮会按当前浏览器大版本在本地生成候选值后以下发自定义 UA；本次又把 `Sec-CH-UA` 改成按 `brand + version` 维护的显式列表，`语言` / `时区` 改成下拉控件并保留“跟随 IP”开关，旧模板里的字符串/旧字段值会在新控件中自动回填；同日晚间又把 `Canvas` / `WebGL 图像` / `WebGL 元数据` / `WebGPU` / `AudioContext` / `ClientRects` / `Speech Voices` 改成截图同款的按钮式模式切换，并让 `WebGL` 自定义时显示 `厂商` / `渲染` 选项式输入；刚刚又把新建创建环境的默认值改成“创建后随机化指纹已开启 + UA 默认自定义随机值”，并把 UA 文本框加高到可完整预览；本次再把 `WebRTC` / 地理位置权限 / 分辨率 / 字体 这 4 项也统一改成截图同款的分段按钮交互，避免 VirtualBrowser 指纹表单里仍混用下拉框；这次继续把 `设备名称` / `MAC地址` / `SSL` / `端口扫描保护` / `启动参数` 对齐到截图同款的按钮式交互，把 `Do Not Track` / `硬件加速` 改成开关样式，并把新建默认值进一步收敛到 `AudioContext` / `ClientRects` / `Speech Voices=随机`、`内存=8GB`、设备名与 MAC 默认自定义随机值；运行模板的执行脚本下拉现已优先展示工作流 `display_name`，但保存到 `RunProfile` 的仍是稳定的 `workflow.name`；这次又把 `WebGL 厂商` / `渲染` 这类长文本下拉框改成按候选内容自动扩宽控件本身和弹出列表；分辨率随后又按最新要求改成“跟随电脑 / 自定义”分段按钮 + 预设分辨率下拉，并保持对旧 `screen.width/height/_value` 模板的回填兼容；现在又把整个运行模板弹窗默认宽度从屏幕的 `50%` 提升到 `60%`，即比原来增大 `20%`；本次再把执行脚本里的模块下拉空白项去掉，改为真正的 placeholder 未选中态，不再展示空白首项；这次又把 `Do Not Track` / `硬件加速` 从纯样式 `QCheckBox` 换成了真正的自绘滑动开关，修正深色主题下滑块缺失、开关状态不清晰的 UI 问题；刚刚又把“随机化指纹”的语义从“创建后再调用 `/api/randomizeFingerprint`”纠正为“创建参数里直接生成随机值”，新模板默认会直接写入随机 UA、随机设备名、随机 MAC，并把旧 `__randomize_after_create__` 仅保留为兼容老模板的读取与 provider 兜底逻辑；现在又修复了任务创建页“运行配置”更新按钮被压缩的问题，按钮会按文案自动计算最小宽度并左对齐显示，不再挤压“重新编辑运行模板”；这次继续把随机逻辑彻底下沉到创建期展开，同一模板每次创建都会重新生成 UA / 设备名 / MAC，且 `字体` / `Canvas` / `WebGL 图像` / `AudioContext` / `ClientRects` / `Speech Voices` 只要选了随机就会直接随本次创建参数生效，旧 `__randomize_after_create__` 已不再兼容；现在又把应用启动默认宽度直接调到 `1420px`，并把任务监控列表的“操作”列宽维持在 `240px`，避免长操作按钮被截断
- 最新修复：2026-04-16 已把 ATM 与 `core:data_table` 构造的 `TaskContext.logger` 接到统一应用日志器，模块 `before_run()` / workflow / task script 的 `ctx.logger` 输出会进入主日志，便于确认“执行一次”是否真正进入模块执行链；同日又修复任务监控里手动批次作业的 `▶ 执行一次` 交互，点击后会立即进入“执行中”禁用态，并以活跃任务计数为准，在任务终态和环境回收完成后自动恢复可点击；本次再把 ATM 默认环境收尾语义收敛为“任务结束只关闭并回收到 READY”，创建环境失败和僵尸任务恢复也不再自动销毁环境，只有模块显式发出 `EnvAction.DESTROY` 信号时才允许删除环境；随后又把运行模板里残留的“生命周期”兼容控件彻底移除，前端不再暴露任何自动删除环境选项；现在又将 `EnvironmentManager.reset()` 正式更名为 `recycle_env()`，明确该动作只是关窗回收并解除任务占用，不代表清空 cookie、指纹或代理配置；本次再为 `TaskSignal.wait_for_confirmation` 补齐任务 signal 持久化、`task.signal` 事件和 ATM 详情页结构化确认面板，客户端可按 `payload.confirmation` 展示字段并直接回调既有确认服务；现在又把模块自定义数据列表底部横向滚动条设为隐藏，同时保留触控板/滚轮横向滑动，并补回归断言锁定滚动策略；这次继续修复 `ModuleAssembler` 发现期静默吞错问题，task/workflow import 失败会进入主日志并在命中失败条目时向运行时回传 discovery hint；同时为 DevLink 普通执行补齐一次性 reload 语义，改完源码后下一次 ATM 执行可直接吃到新代码。
- 最新修复：2026-04-16 已删除脚手架与客户端内残留的声明式 `ui/config_schema.json` / `strategy.yaml` 链路；`module.yaml` 继续作为唯一模块清单，默认配置页改为只读取宿主持久化的模块设置，`add-ui` 也已收敛为只生成 `micro_app` 代码型页面。
- 最新修复：2026-04-16 已把模块持久配置从旧 `configs` 聚合键迁到 `config.db.module_config_entries`，`ctx.get_config()` 现只读取模块/工作流配置；ATM 与 Debug 注入链中的 `workflow`、`execution.params`、`job.params`、`devel_mode`、`creation_params` 已全部改走 `ctx.runtime`，不再污染模块配置命名空间；旧 KV 配置兼容迁移与旧 workflow 配置兜底路径已删除。
- 最新修复：2026-04-16 已压缩仪表盘页面上半部分的标题区、统计卡高度与纵向间距，并抬高“系统实时日志”区域的最小高度；默认窗口尺寸下首页可见日志行数明显增加，便于直接观察任务执行输出。
- 缺陷：BUG-003-pyqt-runtime-blocked-by-system-policy、BUG-004-zip-upgrade-leaves-stale-files、BUG-005-hybrid-acquisition-mode-declared-but-rejected、BUG-013-module-assembler-import-errors-hidden

## 下一步建议

- 检查任务人天估算是否真实合理，仅在必要时再细化到 0.5 人天精度
- 若进入设计或实施阶段，先确认 `docs/04-project-development/04-design/technical-selection.md` 已明确框架、模块、后台范围和编码规则
- 模块入口自动托管方案已闭环，后续优先处理真实站点 E2E 与发布收口
- 再次手动复验 VirtualBrowser 的“创建即保持 RUNNING”链路，确认 `crawler4j.log` 能看到 `Connected Playwright`，且点击停止后环境回到 `READY`
- 调试模块 UI 时，优先使用 DevLink 并在详情页通用数据表中点击“刷新”验证最新 `declare_ui` / handler 行为
- 若 UX/UI 需要可视化评审，优先登记真实设计交付物而不是只写文字
- 若工作项进入收尾，确认关联 PR 已完成评审并合并
- 阶段切换前先更新正式文档，再刷新 `/.factory/memory/` 压缩记忆
