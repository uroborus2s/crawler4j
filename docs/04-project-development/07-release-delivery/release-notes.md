# 发布说明

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 草稿  
**负责人：** 当前仓库维护者  
**主要读者：** 发布负责人 | QA | 维护者  
**上游输入：** Git tag | `docs/04-project-development/02-discovery/current-state-analysis.md` | 本地构建结果  
**下游输出：** 后续正式 release notes | `delivery-package.md`（待需要时补齐）  
**关联 ID：** `REL-001`, `REL-002`, `BUG-001`, `CR-001`  
**最后更新：** 2026-07-14

## 1. 最新已知正式发布

### `REL-001` `v0.2.0`

- Tag 时间：2026-04-20
- Tag 标题：`release: v0.2.0`
- 关联提交：`2d914f48566647304e6a14053063dadb5b305ef1`

## 2. 当前仓库相对正式发布的状态

- 当前工作区根应用版本：`0.4.38`
- 当前运行时版本：`0.4.38`
- 最近正式发布 tag：`v0.2.0`
- SDK 当前已发布版本：`0.4.4`
- Contracts 当前已发布版本：`0.4.3`
- 根应用 0.4.38 为 `env.cookie.ensure` 增加脱敏分阶段错误诊断，并承接 0.4.37 的环境管理改进；SDK 0.4.4 / Contracts 0.4.3 保持不变
- 已按 `crawler4j-contracts 0.4.3 -> crawler4j-sdk 0.4.4` 顺序完成 PyPI 发布，并核对在线文件哈希与隔离安装结果
- SDK 当前口径已收敛为“数据库唯一入口 `ctx.db`，非数据库宿主能力继续通过 `ctx.tools.call(...)` 调用”；模块侧不再使用专用 `ctx.captcha` 字段
- 当前 0.4.x 工作区已移除 `hooks/*.py` 生命周期运行链；模块流程控制通过 workflow 主体返回 `TaskResult`，workflow/component 可选实现 `setup(ctx, workflow)` 和 `cleanup(ctx, outcome)`，环境回收由宿主收口

## 3. 当前证据状态

| 项目 | 结果 |
|---|---|
| 版本相关单测与打包配置 | 通过（2026-07-14 客户端 0.4.38 全量 `1201 passed`，`uv lock --check` 通过） |
| Root wheel/sdist build | 通过（2026-07-14 产出 `crawler4j 0.4.38` wheel/sdist） |
| SDK wheel/sdist build | 通过（2026-07-10 产出 `crawler4j-sdk 0.4.4` wheel/sdist，元数据依赖 Contracts `>=0.4.3,<0.5.0`） |
| SDK publish | 通过（2026-07-10 在 Contracts 在线可见后上传 0.4.4；PyPI wheel/sdist 哈希和隔离安装通过） |
| Contracts wheel/sdist build | 通过（2026-07-10 产出 `crawler4j-contracts 0.4.3` wheel/sdist） |
| Contracts publish | 通过（2026-07-10 先上传 0.4.3；PyPI wheel/sdist 哈希与本地一致） |
| Desktop PyInstaller / macOS Sparkle bundle | 通过（2026-06-19 删除远端旧 `Crawler4j-0.4.16.dmg` 后，`uv run package-macos-internal-release` 重新生成 `Crawler4j.app`、`Crawler4j-0.4.16.dmg`、`appcast.xml` 并上传 macOS 更新目录；公网 DMG `HEAD 200`，SHA256 为 `8463f4982ea4948a2151a7061449fc8a3fd9152848b37197a35504efb1f04243`） |
| Full test / lint / smoke | 客户端 0.4.38 全量 `1201 passed`；全仓 Ruff、`uv lock --check` 与 `git diff --check` 通过；UI smoke 沿用 0.4.37 基线 |
| Docs markdown tree | 通过（`docs-stratego source validate --repo-path .`，`pages=86 contracts=0`） |

## 4. 当前不建议直接发布的原因

- `0.4.38` 对应的桌面安装包、Git tag、正式 GitHub release 与交付批次仍待后续完成
- `ctrip` 真实站点 E2E 与正式 release closeout 仍未完成
- Windows 真机签名、安装和自更新留证仍未完成

## 5. 下一版发布前必须满足

- 按 [版本治理规则](version-governance.md) 复验 `0.4.38` 仍是目标正式版本，且 README / 包描述 / release 文档不再混用旧口径
- 更新 Git tag、正式 release notes 与交付批次说明
- 决定真实站点 E2E 与 release closeout 的先后顺序，并完成至少一轮闭环
- 至少复验 `uv run pytest -q`、根应用 smoke、Root / SDK / Contracts build

## 6. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-07-15 | 完成 CR-022 Hosted UI 公共字段 change、Form scope、安全 handle、`ui.form.reset`、create default、长表单滚动和 1–3 列响应式 Form 布局通用能力；Contracts 0.4.3 / SDK 0.4.4 版本保持不变，未发布 | Codex |
| 2026-07-14 | 将根应用 / 运行时源码版本提升到 0.4.38，为 `env.cookie.ensure` 增加不泄露 API Key 和 Cookie 值的分阶段错误诊断；SDK / Contracts 版本保持不变 | Codex |
| 2026-07-13 | 将根应用 / 运行时源码版本提升到 0.4.37，承接环境管理代理与指纹手动更新交互收口；本轮只提交推送源码版本，不构建桌面安装包 | Codex |
| 2026-07-12 | 将根应用 / 运行时源码版本提升到 0.4.36，承接 DevLink 模块并发强制重载序列化；本轮只提交推送源码版本，不构建桌面安装包 | Codex |
| 2026-07-11 | 将根应用 / 运行时源码版本提升到 0.4.35，承接 VirtualBrowser 随机后最小指纹修正与创建验收；本轮只提交推送源码版本，不构建桌面安装包 | Codex |
| 2026-07-11 | 将根应用 / 运行时源码版本提升到 0.4.34，承接 VirtualBrowser 启动后完整代理状态回写；本轮只提交推送源码版本，不构建桌面安装包 | Codex |
| 2026-07-11 | 将根应用 / 运行时源码版本提升到 0.4.33，承接 VirtualBrowser 随机内核版本选择与 Windows 已验证的启动后代理状态回写；本轮只提交推送源码版本，不构建桌面安装包 | Codex |
| 2026-07-10 | 将根应用 / 运行时源码版本提升到 0.4.32，承接 VirtualBrowser 代理启动后完整状态回写、固定地区语言指纹与环境命名收敛；本轮只提交推送源码版本，不构建桌面安装包 | Codex |
| 2026-07-10 | 将根应用 / 运行时源码版本提升到 0.4.31，承接 VirtualBrowser 厂商随机指纹、代理地理回写与创建后页面运行时自检；本轮只提交推送源码版本，不构建桌面安装包 | Codex |
| 2026-07-10 | 将根应用 / 运行时源码版本提升到 0.4.30，承接 Hosted UI DataTable 当前页批量编辑与行按钮页面导航；本轮只提交推送源码版本，不构建桌面安装包 | Codex |
| 2026-07-10 | 发布 Contracts 0.4.3 / SDK 0.4.4，用于对外提供 Hosted UI DataTable 当前页多选批量编辑 schema 与 scanner 校验；两包均完成 PyPI 哈希和隔离安装验证，根应用 / 客户端保持现有 0.4.29 | Codex |
| 2026-03-26 | 建立基线 release notes | Codex |
| 2026-03-26 | 按统一版本规则区分当前工作区版本与最近正式发布 | Codex |
| 2026-04-17 | 将根应用 / SDK / Contracts 当前源码版本与 README、release 文档统一收敛到 `0.2.0` 发布基线，并明确最近正式 tag 仍为 `v0.1.1` | Codex |
| 2026-04-17 | 追加本轮发布前复核结果：版本相关单测、三包构建与 `docs-stratego` 文档树校验均通过 | Codex |
| 2026-04-19 | SDK 独立升到 `0.3.0`，并完成本地构建与 PyPI 发布 | Codex |
| 2026-04-22 | SDK 继续升到 `0.4.0`，并完成本地构建与 PyPI 发布 | Codex |
| 2026-04-24 | SDK 升到 `0.5.2`，补齐 `module repair-init` 命令与相关回归，发布结果以本轮执行记录为准 | Codex |
| 2026-04-24 | 修正 release 文档中的版本漂移：最近正式 tag 更新为 `v0.2.0`，当前根应用 / 运行时版本更新为 `0.3.1`，并同步 Packaging 遗留修复后的本地构建事实 | Codex |
| 2026-04-27 | 统一当前版本事实为 `crawler4j 0.3.1`、`crawler4j-sdk 0.6.1`、`crawler4j-contracts 0.4.0`，并把 SDK/Contracts 当前构建发布证据与 QScintilla 打包证据标记为待补 | Codex |
| 2026-04-29 | 将当前根应用 / 运行时版本提升到 `0.3.2`，并把 Root build 证据切回“需按新版本重跑”的发布口径 | Codex |
| 2026-05-01 | 0.4.0 全面审查后同步发布证据：三包 wheel/sdist 构建、全量测试、lint、SDK CLI help、UI smoke 与 macOS `package-desktop` 均通过；正式发布仍因 `ctrip` 真站 E2E、Windows 真机证据、publish 与交付批次未闭环保持 No-Go | Codex |
| 2026-05-18 | 将正式发布候选版本提升到 `0.4.1`，绕开 PyPI 0.4.0 删除文件名不可复用阻塞；已完成 SDK / Contracts PyPI 发布与 macOS 客户端升级包发布 | Codex |
| 2026-05-18 | 仅将根应用 / 运行时版本提升到 `0.4.2`，用于后续 Windows 客户端修复版升级包；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-05-26 | 仅将根应用 / 运行时版本提升到 `0.4.3`，用于发布 REM 环境列表刷新不触发 GC 的客户端修复版；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-05-26 | 完成 `crawler4j 0.4.3` root wheel/sdist 构建与 macOS Sparkle 更新包发布：生成 `Crawler4j-0.4.3.dmg` / `appcast.xml` 并上传远程 macOS 更新目录；Windows 更新包仍需在 Windows 构建机补齐 | Codex |
| 2026-05-27 | 仅将根应用 / 运行时版本提升到 `0.4.4`，用于发布 VirtualBrowser 启动就绪竞态与 `addBrowser` relay 500 诊断修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-05-30 | 仅将根应用 / 运行时版本提升到 `0.4.5`，用于发布开发模块源码扫描跳过忽略目录内 symlink 的客户端修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-07 | 仅将根应用 / 运行时版本修正提升到 `0.4.6`，用于发布指纹浏览器生命周期串行化修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-09 | 仅将根应用 / 运行时版本提升到 `0.4.7`，用于发布对象 cleanup 固定超时移除修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-11 | 仅将根应用 / 运行时版本提升到 `0.4.8`，用于发布 IP 池最久未使用默认分配策略、最近使用时间记录与旧库迁移修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-12 | 仅将根应用 / 运行时版本提升到 `0.4.9`，用于发布运行模板指定环境选择、DataTable 可见筛选排序和 IP 池条目人工状态等客户端改动；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-13 | 仅将根应用 / 运行时版本提升到 `0.4.10`，用于发布任务监控暂停后对象 cleanup 链路 `asyncio.CancelledError` 截断修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-13 | 仅将根应用 / 运行时版本提升到 `0.4.11`，用于发布 Hosted UI DataTable 自定义行按钮分发到同名 `@ui_action` 的客户端修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-13 | 仅将根应用 / 运行时版本提升到 `0.4.12`，用于发布 Hosted UI DataTable 行按钮显式 params 分发和任务暂停后绑定业务行 `run_status` 释放修复；SDK / Contracts 继续保持 `0.4.1` | Codex |
| 2026-06-15 | 将 SDK / Contracts 提升到 `0.4.2` 并发布到 PyPI，用于对外提供 `@workflow(host_scenarios=["existing_env_import"])` 与 SDK CLI 导入 workflow 脚手架；根应用 / 运行时保持 `0.4.13` 并补充环境列表绑定 IP 展示 | Codex |
| 2026-06-16 | 仅将根应用 / 运行时版本提升到 `0.4.14`，用于发布已导入指纹浏览器环境的来源代理同步与 IP 表唯一匹配绑定能力；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-06-16 | 仅将根应用 / 运行时版本提升到 `0.4.15`，用于发布 VirtualBrowser 来源代理解析修复：优先使用结构化来源代理，避免把本地转发 URL 当作绑定 IP；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-06-18 | 仅将根应用 / 运行时版本提升到 `0.4.16`，用于发布来源代理同步匹配规则修复：按 `host + port` 唯一命中 IP 表，不再比较协议、用户名或密码；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-06-19 | 删除远端旧 macOS `0.4.16` DMG，重新生成并上传 `Crawler4j-0.4.16.dmg` 与 `appcast.xml`，公网下载 URL 已返回 `200` | Codex |
| 2026-06-20 | 仅将根应用 / 运行时版本提升到 `0.4.17`，用于发布任务监控作业禁用状态、REM 固定运行模板安全门和来源代理同步匹配规则修复；SDK / Contracts 继续保持 `0.4.2`，0.4.17 客户端包仍需后续补齐 | Codex |
| 2026-06-22 | 仅将根应用 / 运行时版本提升到 `0.4.18`，用于发布 VirtualBrowser 随机指纹创建期不下发具体指纹字段和 `chrome_version=139..145` 随机化；SDK / Contracts 继续保持 `0.4.2`，0.4.18 客户端包仍需后续补齐 | Codex |
| 2026-06-28 | 仅将根应用 / 运行时版本提升到 `0.4.19`，用于发布 `browser.drag` 连续轨迹生成与框架自检 trace 能力；SDK / Contracts 继续保持 `0.4.2`，0.4.19 客户端包仍需后续补齐 | Codex |
| 2026-06-28 | 仅将根应用 / 运行时版本提升到 `0.4.20`，用于发布 `browser.drag natural` 体感时长、约 60Hz 采样与固定 seed 默认混入运行随机盐的框架自检能力；SDK / Contracts 继续保持 `0.4.2`，0.4.20 客户端包仍需后续补齐 | Codex |
| 2026-06-29 | 仅将根应用 / 运行时版本提升到 `0.4.21`，用于发布 VirtualBrowser 随机指纹代理出口 geo 校准、创建后轻量验收、风险环境标记与默认调度跳过；SDK / Contracts 继续保持 `0.4.2`，0.4.21 客户端包仍需后续补齐 | Codex |
| 2026-06-29 | 仅将根应用 / 运行时版本提升到 `0.4.22`，用于发布 VirtualBrowser 随机指纹语言参数去重；SDK / Contracts 继续保持 `0.4.2`，0.4.22 客户端包仍需后续补齐 | Codex |
| 2026-06-30 | 仅将根应用 / 运行时版本提升到 `0.4.23`，用于本轮 GitHub release 收口；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-07-05 | 仅将根应用 / 运行时版本提升到 `0.4.24`，用于 REM 批量环境清理预览的模块候选 scope 修复；SDK / Contracts 继续保持 `0.4.2` | Codex |
| 2026-07-08 | 仅将根应用 / 运行时版本提升到 `0.4.26`，用于 VirtualBrowser 创建环境指纹自洽与稳定性优化；SDK / Contracts 继续保持 `0.4.2` | Codex |
