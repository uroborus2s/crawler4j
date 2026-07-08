# 发布说明

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 草稿  
**负责人：** 当前仓库维护者  
**主要读者：** 发布负责人 | QA | 维护者  
**上游输入：** Git tag | `docs/04-project-development/02-discovery/current-state-analysis.md` | 本地构建结果  
**下游输出：** 后续正式 release notes | `delivery-package.md`（待需要时补齐）  
**关联 ID：** `REL-001`, `REL-002`, `BUG-001`, `CR-001`  
**最后更新：** 2026-07-08

## 1. 最新已知正式发布

### `REL-001` `v0.2.0`

- Tag 时间：2026-04-20
- Tag 标题：`release: v0.2.0`
- 关联提交：`2d914f48566647304e6a14053063dadb5b305ef1`

## 2. 当前仓库相对正式发布的状态

- 当前工作区根应用版本：`0.4.26`
- 当前运行时版本：`0.4.26`
- 最近正式发布 tag：`v0.2.0`
- SDK 当前版本：`0.4.2`
- Contracts 当前版本：`0.4.2`
- 当前工作区根应用已切到 `0.4.26` 源码版本线，用于 VirtualBrowser 创建环境指纹自洽与稳定性优化；SDK / Contracts 保持 `0.4.2`
- `crawler4j-sdk 0.4.2` 与 `crawler4j-contracts 0.4.2` 已在本轮按 `contracts -> sdk` 依赖顺序完成 PyPI 发布
- SDK 当前口径已收敛为“数据库唯一入口 `ctx.db`，非数据库宿主能力继续通过 `ctx.tools.call(...)` 调用”；模块侧不再使用专用 `ctx.captcha` 字段
- 当前 0.4.x 工作区已移除 `hooks/*.py` 生命周期运行链；模块流程控制通过 workflow 主体返回 `TaskResult`，workflow/component 可选实现 `setup(ctx, workflow)` 和 `cleanup(ctx, outcome)`，环境回收由宿主收口

## 3. 当前证据状态

| 项目 | 结果 |
|---|---|
| 版本相关单测（`test_version_service.py`） | 通过（2026-07-08 随 0.4.26 版本提升回归覆盖，`3 passed`） |
| Root wheel/sdist build | 历史通过（2026-05-26 `uv run build crawler4j` 产出 `crawler4j 0.4.3` wheel/sdist；当前 0.4.26 尚未刷新 root build） |
| SDK wheel/sdist build | 通过（2026-06-15 `uv run build crawler4j-contracts crawler4j-sdk` 产出 `crawler4j-sdk 0.4.2` wheel/sdist） |
| SDK publish | 通过（2026-06-15 `uv run publish crawler4j-sdk` 上传 0.4.2 到 PyPI） |
| Contracts wheel/sdist build | 通过（2026-06-15 `uv run build crawler4j-contracts crawler4j-sdk` 产出 `crawler4j-contracts 0.4.2` wheel/sdist） |
| Contracts publish | 通过（2026-06-15 `uv run publish crawler4j-contracts` 上传 0.4.2 到 PyPI） |
| Desktop PyInstaller / macOS Sparkle bundle | 通过（2026-06-19 删除远端旧 `Crawler4j-0.4.16.dmg` 后，`uv run package-macos-internal-release` 重新生成 `Crawler4j.app`、`Crawler4j-0.4.16.dmg`、`appcast.xml` 并上传 macOS 更新目录；公网 DMG `HEAD 200`，SHA256 为 `8463f4982ea4948a2151a7061449fc8a3fd9152848b37197a35504efb1f04243`） |
| Full test / lint / smoke | 历史全量通过（2026-05-18 `992 passed`）；0.4.17 任务禁用 / REM 固定运行模板安全门聚焦回归 `115 passed`；0.4.18 VirtualBrowser 随机指纹与版本服务聚焦回归 `56 passed`；0.4.20 版本服务与 `browser.drag` 自检回归 `24 passed`；0.4.21 版本服务、VirtualBrowser 指纹与风险环境调度聚焦回归 `85 passed`；0.4.22 版本服务、VirtualBrowser 指纹与运行模板 UI 聚焦回归 `44 passed`；0.4.23 版本服务回归 `3 passed`；0.4.24 版本服务与 REM cleanup scope 回归 `51 passed`；当前 0.4.26 版本服务、VirtualBrowser 创建环境指纹和运行模板 UI 聚焦回归 `83 passed`，`ruff check`、`.factory/project.json` JSON 校验与 `git diff --check` 通过 |
| Docs markdown tree | 历史通过（`docs-stratego source validate --repo-path .`）；本轮未重跑 |

## 4. 当前不建议直接发布的原因

- `0.4.26` 对应的 Git tag、正式 GitHub release 与交付批次将在本轮合并后完成
- `ctrip` 真实站点 E2E 与正式 release closeout 仍未完成
- Windows 真机签名、安装和自更新留证仍未完成

## 5. 下一版发布前必须满足

- 按 [版本治理规则](version-governance.md) 复验 `0.4.26` 仍是目标正式版本，且 README / 包描述 / release 文档不再混用旧口径
- 更新 Git tag、正式 release notes 与交付批次说明
- 决定真实站点 E2E 与 release closeout 的先后顺序，并完成至少一轮闭环
- 至少复验 `uv run pytest -q`、根应用 smoke、Root / SDK / Contracts build

## 6. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
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
