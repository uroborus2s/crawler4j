# 版本治理规则

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 发布负责人 | Tech Lead | Dev | QA  
**上游输入：** `packages/crawler4j/pyproject.toml` | Git tag | 子包 `pyproject.toml` | docs-stratego 源仓导航
**下游输出：** `release-notes.md` | `deployment-guide.md` | `docs/index.md` | `.factory/project.json`
**关联 ID：** `CR-001`, `TASK-004`, `REQ-004`, `REQ-0401`, `NFR-002`
**最后更新：** 2026-07-15

## 1. 规则

1. 根应用当前工作区版本以 `packages/crawler4j/pyproject.toml` 的 `[project].version` 为唯一事实源。
2. 运行时版本显示必须由代码读取根应用包元数据，不再维护独立的 `__version__.py` 镜像文件。
3. Git tag 只表示最近一次正式发布，可以落后于当前工作区版本。
4. `crawler4j-sdk` 与 `crawler4j-contracts` 是独立版本线，不要求与根应用版本号相同。
5. 发布说明必须同时区分：
   - 当前工作区版本
   - 最近一次正式发布 tag
   - SDK / Contracts 当前发布版本
6. docs-stratego 网站主文档必须指向当前已发布版本的使用者指南和开发者指南，不得默认指向未发布的开发中版本。
7. 旧版本使用者指南和开发者指南必须保留在版本目录中，通过历史版本入口继续访问。

## 2. 当前版本事实

| 对象 | 当前值 | 说明 |
|---|---|---|
| 根应用包版本 | `0.4.39` | 当前仓库源码事实；承接 CR-022 Hosted UI 通用 Form 能力 |
| 根应用运行时版本 | `0.4.39` | 由运行时代码从包元数据或 `packages/crawler4j/pyproject.toml` 解析 |
| 最近正式发布 tag | `v0.2.0` | 最新已知正式发布 |
| SDK | `0.4.5` | 发布候选；增加 Hosted Field change handler 扫描与 `HostedFieldChangeEvent`，依赖 `crawler4j-contracts>=0.4.4,<0.5.0` |
| Contracts | `0.4.4` | 发布候选；增加公共字段 `on_change`、安全 Form scope/reset 与多列 Form layout 契约 |
| docs-stratego 主文档版本 | 待正式发布前确认 | 当前源码文档入口已把 0.4.x 作为当前主线、0.3.x 作为历史维护；发布站点切换仍需随正式发布动作确认 |

## 3. 为什么这样定义

- 过去的问题不是“版本号多少”，而是同一份仓库里同时存在根包版本、运行时版本和 tag 口径漂移。
- 当前根应用源码为 `0.4.39`，但 Git tag 在本次发布前仍停留在 `v0.2.0`；如果不显式分层，维护者会误以为当前源码版本已完成正式发布。
- 版本治理文档的职责不是制造第二事实源，而是明确“当前源码版本”和“最近正式发布”之间的关系。

## 4. 发布前动作

在下一次正式发布根应用前，至少完成：

1. 确认 `packages/crawler4j/pyproject.toml`、运行时版本显示和 README 仍统一指向目标正式版本 `0.4.39`
2. 更新 `docs/04-project-development/07-release-delivery/release-notes.md`
3. 复验 `uv run pytest -q`
4. 复验 `uv run python scripts/smoke_test_ui.py`
5. 复验 Root / SDK / Contracts build
6. 为根应用补打对应 `0.4.39` Git tag 与正式 release 资产
7. 若发布会切换文档主版本，则同步更新 `docs/index.md`、对应 `version.yaml` 和 docs-stratego 历史版本入口

## 5. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-07-15 | 将根应用 / 运行时源码版本提升到 `0.4.39`，Contracts 提升到 `0.4.4`、SDK 提升到 `0.4.5`，用于发布 CR-022 Hosted UI 通用 Form 契约与 SDK 支持 | Codex |
| 2026-07-14 | 将根应用 / 运行时源码版本提升到 `0.4.38`，为 `env.cookie.ensure` 增加分阶段脱敏错误诊断；SDK 0.4.4 / Contracts 0.4.3 保持不变 | Codex |
| 2026-07-13 | 将根应用 / 运行时源码版本提升到 `0.4.37`，承接环境列表创建时间展示、代理更新交互优化、手动指纹刷新校准和高风险操作确认；SDK 0.4.4 / Contracts 0.4.3 保持不变，本轮不构建桌面安装包 | Codex |
| 2026-07-12 | 将根应用 / 运行时源码版本提升到 `0.4.36`，承接 DevLink 模块并发强制重载序列化；SDK 0.4.4 / Contracts 0.4.3 保持不变，本轮不构建桌面安装包 | Codex |
| 2026-07-11 | 将根应用 / 运行时源码版本提升到 `0.4.35`，承接 VirtualBrowser 随机后最小指纹修正与创建验收；SDK 0.4.4 / Contracts 0.4.3 保持不变，本轮不构建桌面安装包 | Codex |
| 2026-07-11 | 将根应用 / 运行时源码版本提升到 `0.4.34`，承接 VirtualBrowser 启动后完整代理状态回写；SDK 0.4.4 / Contracts 0.4.3 保持不变，本轮不构建桌面安装包 | Codex |
| 2026-07-11 | 将根应用 / 运行时源码版本提升到 `0.4.33`，承接 VirtualBrowser 随机内核版本选择与 Windows 已验证的启动后代理状态回写；SDK 0.4.4 / Contracts 0.4.3 保持不变，本轮不构建桌面安装包 | Codex |
| 2026-07-10 | 将根应用 / 运行时源码版本提升到 `0.4.32`，承接 VirtualBrowser 代理启动后完整状态回写、固定地区语言指纹与环境命名收敛；SDK 0.4.4 / Contracts 0.4.3 保持不变，本轮不构建桌面安装包 | Codex |
| 2026-07-10 | 将根应用 / 运行时源码版本提升到 `0.4.31`，承接 VirtualBrowser 厂商随机指纹、代理地理回写与创建后页面运行时自检；SDK 0.4.4 / Contracts 0.4.3 保持不变，本轮不构建桌面安装包 | Codex |
| 2026-07-10 | 将根应用 / 运行时源码版本提升到 `0.4.30`，承接 Hosted UI DataTable 批量编辑与行按钮页面导航；SDK 0.4.4 / Contracts 0.4.3 保持不变，本轮不构建桌面安装包 | Codex |
| 2026-07-10 | 将 Contracts 提升并发布到 `0.4.3`、SDK 提升并发布到 `0.4.4`，用于提供 Hosted UI DataTable 当前页多选批量编辑契约与 scanner 校验；根应用保持现有 `0.4.29`，客户端未在本轮升级或发布 | Codex |
| 2026-07-08 | 仅将根应用 / 运行时版本提升到 `0.4.26`，用于承接 VirtualBrowser 创建期随机指纹自洽与稳定性优化；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-07-05 | 仅将根应用 / 运行时版本提升到 `0.4.24`，用于承接 REM 批量环境清理预览的模块候选 scope 修复；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-03-26 | 建立根应用 / 运行时 / tag / SDK / Contracts 的统一版本治理规则 | Codex |
| 2026-04-17 | 将根应用 / SDK / Contracts 当前源码版本与 README、release 文档统一收敛到 `0.2.0` 发布基线，并明确最近正式 tag 仍为 `v0.1.1` | Codex |
| 2026-04-19 | 将 SDK 版本独立提升到 `0.3.0`，并同步 README、发布文档与 `.factory` 版本事实源 | Codex |
| 2026-04-22 | 将 SDK 版本提升到 `0.4.0`，并完成本地构建与 PyPI 发布 | Codex |
| 2026-04-24 | 修正版本治理与发布文档的事实漂移：根应用 / 运行时更新到 `0.3.1`，最近正式 tag 更新为 `v0.2.0`，SDK / Contracts 当前版本同步为 `0.5.2` / `0.3.0` | Codex |
| 2026-04-27 | 同步当前源码版本线：根应用 / 运行时保持 `0.3.1`，最近正式 tag 保持 `v0.2.0`，SDK / Contracts 当前版本同步为 `0.6.1` / `0.4.0`；本轮仍缺当前版本 build/publish 证据 | Codex |
| 2026-04-29 | 将根应用当前源码版本提升到 `0.3.2`，同步 README / `.factory` / release 文档口径，并要求后续正式发布按 `0.3.2` 重新补齐 build、桌面打包与交付证据 | Codex |
| 2026-04-30 | 补充 docs-stratego 文档版本治理：站点主文档必须指向当前已发布版本，旧版本使用者/开发者指南保留为历史版本入口，未发布版本只能作为开发版预览 | Codex |
| 2026-05-01 | 将当前源码版本事实同步到 `0.4.0`，登记三包 build、全量测试、UI smoke 与 macOS package-desktop 已补证；正式发布仍需 tag/release、publish、Windows 真机和真实站点 E2E 证据 | Codex |
| 2026-05-18 | 将发布候选提升到 `0.4.1`，避免 PyPI 0.4.0 删除文件名不可复用阻塞；已完成 SDK / Contracts PyPI 发布与 macOS 客户端升级包发布，Git tag / GitHub release 与 Windows 真机证据仍待补 | Codex |
| 2026-05-18 | 仅将根应用 / 运行时版本提升到 `0.4.2`，用于承接 Windows 客户端升级卡死修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-05-26 | 仅将根应用 / 运行时版本提升到 `0.4.3`，用于承接 REM 环境列表刷新误触发 GC 的客户端修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-05-27 | 仅将根应用 / 运行时版本提升到 `0.4.4`，用于承接 VirtualBrowser 启动就绪竞态、`addBrowser` relay 500 重试与脱敏诊断日志修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-05-30 | 仅将根应用 / 运行时版本提升到 `0.4.5`，用于承接开发模块源码扫描跳过 `.venv/` 等忽略目录内 symlink 的客户端修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-07 | 仅将根应用 / 运行时版本修正提升到 `0.4.6`，用于承接指纹浏览器生命周期串行化修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-09 | 仅将根应用 / 运行时版本提升到 `0.4.7`，用于承接 workflow/component 对象 cleanup 固定超时移除；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-11 | 仅将根应用 / 运行时版本提升到 `0.4.8`，用于承接 IP 池最久未使用默认分配策略、最近使用时间记录与旧库迁移；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-12 | 仅将根应用 / 运行时版本提升到 `0.4.9`，用于承接运行模板指定环境选择、DataTable 可见筛选排序和 IP 池条目人工状态等客户端改动；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-13 | 仅将根应用 / 运行时版本提升到 `0.4.10`，用于承接任务监控暂停后对象 cleanup 链路 `asyncio.CancelledError` 截断修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-13 | 仅将根应用 / 运行时版本提升到 `0.4.11`，用于承接 Hosted UI DataTable 自定义行按钮分发到同名 `@ui_action` 的客户端修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-13 | 仅将根应用 / 运行时版本提升到 `0.4.12`，用于承接 Hosted UI DataTable 行按钮显式 params 分发和任务暂停后绑定业务行 `run_status` 释放修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-15 | 将 SDK / Contracts 提升到 `0.4.2` 并发布到 PyPI，用于发布已有环境导入 workflow 场景契约与 SDK CLI 脚手架；根应用 / 运行时保持 `0.4.13` 并补充环境列表绑定 IP 展示 | Codex |
| 2026-06-16 | 仅将根应用 / 运行时版本提升到 `0.4.14`，用于承接已导入指纹浏览器环境的来源代理同步、IP 表唯一匹配绑定和环境管理页批量同步入口；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-06-16 | 仅将根应用 / 运行时版本提升到 `0.4.15`，用于修复 VirtualBrowser 来源代理解析优先级，来源代理同步优先使用结构化代理地址而不是 `proxy.url` 中的本地转发 URL；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-06-18 | 仅将根应用 / 运行时版本提升到 `0.4.16`，用于修复来源代理同步匹配规则，绑定 IP 表时只按 `host + port` 唯一命中，不再比较协议、用户名或密码；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-06-20 | 仅将根应用 / 运行时版本提升到 `0.4.17`，用于承接任务监控作业禁用状态、REM 固定运行模板安全门和来源代理同步匹配规则修复；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-06-22 | 仅将根应用 / 运行时版本提升到 `0.4.18`，用于承接 VirtualBrowser 随机指纹创建期不下发具体指纹字段，并在随机指纹模式下把 `chrome_version` 每次随机为 `139..145`；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-06-28 | 仅将根应用 / 运行时版本提升到 `0.4.19`，用于承接 `browser.drag` 连续轨迹生成与框架自检 trace 能力；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-06-28 | 仅将根应用 / 运行时版本提升到 `0.4.20`，用于承接 `browser.drag natural` 体感时长、约 60Hz 采样与固定 seed 默认混入运行随机盐的框架自检能力；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-06-29 | 仅将根应用 / 运行时版本提升到 `0.4.21`，用于承接 VirtualBrowser 随机指纹代理出口 geo 校准、创建后轻量验收、风险环境标记与默认调度跳过；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-06-29 | 仅将根应用 / 运行时版本提升到 `0.4.22`，用于承接 VirtualBrowser 随机指纹语言参数去重；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-06-30 | 仅将根应用 / 运行时版本提升到 `0.4.23`，用于本轮 GitHub release 收口；SDK / Contracts 继续保持 `0.4.2` | Codex |
