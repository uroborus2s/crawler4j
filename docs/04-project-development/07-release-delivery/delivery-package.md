# 交付包清单

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 草稿
**负责人：** 当前仓库维护者
**主要读者：** 发布负责人 | 交付方 | 运维 | 管理员
**上游输入：** `acceptance-checklist.md` | `release-notes.md` | `version-governance.md` | `docs/04-project-development/08-operations-maintenance/deployment-guide.md`
**下游输出：** 交付签收 | `docs/02-user-guide/admin-guide.md` | `docs/04-project-development/08-operations-maintenance/operations-runbook.md`
**关联 ID：** `REL-005`, `REL-006`, `TASK-017`, `REQ-004`
**最后更新：** 2026-07-10

## 1. 用途

本文件定义一次正式交付至少要包含哪些内容，避免“代码能跑，但交付对象拿不到完整材料”。

## 2. 交付包最小内容

| 类别 | 必需内容 | 说明 |
|---|---|---|
| 版本与说明 | `release-notes.md` | 说明本次交付范围、版本和已知限制 |
| 验收材料 | `acceptance-checklist.md` | 说明当前是否满足发布 Gate |
| 运行材料 | `deployment-guide.md`、`operations-runbook.md` | 说明怎么部署、巡检和处理故障 |
| 管理材料 | `admin-guide.md` | 说明管理员/实施者怎么接手环境和模块 |
| 产物 | Root 正式发布产物、必要时的 SDK / Contracts 产物 | 具体名称和路径按本次发布补齐 |
| 版本事实 | 目标版本号、对应 Git tag、SDK / Contracts 版本 | 与 `version-governance.md` 保持一致 |

## 3. 当前基线可复用情况

| 项目 | 当前状态 | 说明 |
|---|---|---|
| 发布说明基线 | 已具备 | 已能区分当前工作区和最近正式发布 |
| 验收清单模板 | 已具备 | 可直接用于下一次正式发布 Gate |
| 部署与运行文档 | 已具备 | 部署说明、运行手册、管理员指南已补齐 |
| macOS 桌面包 | 已补齐 0.4.16 内部包 | 2026-06-19 `uv run package-macos-internal-release` 已重新生成 `packages/crawler4j/dist/desktop/macos/Crawler4j.app` |
| macOS 内部 Sparkle 更新包 | 已补齐 0.4.16 内部更新包 | 2026-06-19 已删除远端旧 `Crawler4j-0.4.16.dmg`，重新生成并上传 `packages/crawler4j/dist/updates/macos/Crawler4j-0.4.16.dmg` 与 `appcast.xml` 到 `CRAWLER4J_UPDATE_UPLOAD_TARGET/mac/`；公网 DMG `HEAD 200`，SHA256 为 `8463f4982ea4948a2151a7061449fc8a3fd9152848b37197a35504efb1f04243` |
| Windows 桌面包 | 已具备发布脚手架，待正式批次补齐证据 | 仓库已具备 `PyInstaller onedir + Velopack` 发布链，`uv run package-windows-release` 可生成 `Setup.exe` / `.nupkg` / `releases.<channel>.json`，`uv run deploy-windows-release` 可继续通过 OpenSSH `sftp` 把 `packages/crawler4j/dist/updates/windows/` 上传到 `CRAWLER4J_UPDATE_UPLOAD_TARGET/win/`；但当前批次仍缺 Windows 真机签名、安装、升级留证与正式下载地址 |
| 正式交付产物 | 部分补齐 | SDK 0.4.4 / Contracts 0.4.3 PyPI 已完成；根应用保持现有 0.4.29，最新已记录 macOS 0.4.16 内部更新包已重新生成并上传；0.4.29 客户端包、Git tag / GitHub release、Windows 真机安装/升级证据和正式交付签收仍需补齐 |

## 4. 使用规则

- 每一次正式交付都应原地更新本文件，不创建 `delivery-package-v2.md`。
- 如果本次不交付 SDK / Contracts，必须显式写明“不包含”的原因。
- 如果交付对象不是 Core 维护者，而是现场实施或运维团队，必须同时附带管理员和运行文档。

## 5. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-07-10 | 完成 SDK 0.4.4 / Contracts 0.4.3 PyPI 交付，在线 wheel/sdist 哈希与本地一致并通过隔离安装；客户端未在本轮发布 | Codex |
| 2026-05-18 | 完成 0.4.1 发布批次的 SDK / Contracts PyPI 发布与 macOS Sparkle 更新包构建上传；正式交付仍需 Git tag / GitHub release、Windows 真机证据和签收闭环 | Codex |
| 2026-05-01 | 补记 0.4.0 本地交付证据：三包 build 和 macOS `package-desktop` 已重新通过；正式交付仍需 Windows 真机证据、publish/远端 release 与交付批次闭环 | Codex |
| 2026-05-18 | 版本提升到 `0.4.1`，原 0.4.0 本地包证据不再作为当前发布批次证据；SDK / Contracts / 客户端升级包需重建发布 | Codex |
| 2026-05-18 | 根应用版本提升到 `0.4.2`，用于后续 Windows 修复版客户端升级包；SDK / Contracts 不随本次变更升版 | Codex |
| 2026-05-26 | 根应用版本提升到 `0.4.3`，用于 REM 环境列表刷新误删环境修复；macOS 内部 Sparkle 更新包已重新生成并上传，Windows 更新包仍需在 Windows 构建机补齐 | Codex |
| 2026-05-27 | 根应用版本提升到 `0.4.4`，用于 VirtualBrowser 启动就绪竞态和 `addBrowser` relay 500 诊断修复；客户端包与正式交付证据仍需后续构建批次补齐 | Codex |
| 2026-05-30 | 根应用版本提升到 `0.4.5`，用于开发模块源码扫描跳过忽略目录内 symlink 的客户端修复；客户端包与正式交付证据仍需后续构建批次补齐 | Codex |
| 2026-06-07 | 根应用版本修正提升到 `0.4.6`，用于指纹浏览器生命周期串行化修复；0.4.6 客户端包、正式 tag / release 与真机升级证据仍需后续补齐 | Codex |
| 2026-06-09 | 根应用版本提升到 `0.4.7`，用于对象 cleanup 固定超时移除修复；0.4.7 客户端包、正式 tag / release 与真机升级证据仍需后续补齐 | Codex |
| 2026-06-11 | 根应用版本提升到 `0.4.8`，用于 IP 池最久未使用默认分配策略、最近使用时间记录与旧库迁移修复；0.4.8 客户端包、正式 tag / release 与真机升级证据仍需后续补齐 | Codex |
| 2026-06-12 | 根应用版本提升到 `0.4.9`，用于运行模板指定环境选择、DataTable 可见筛选排序和 IP 池条目人工状态等客户端改动；0.4.9 客户端包、正式 tag / release 与真机升级证据仍需后续补齐 | Codex |
| 2026-06-13 | 根应用版本提升到 `0.4.10`，用于任务监控暂停后对象 cleanup 链路 `asyncio.CancelledError` 截断修复；0.4.10 客户端包、正式 tag / release 与真机升级证据仍需后续补齐 | Codex |
| 2026-06-13 | 根应用版本提升到 `0.4.11`，用于 Hosted UI DataTable 自定义行按钮分发到同名 `@ui_action` 的客户端修复；0.4.11 客户端包、正式 tag / release 与真机升级证据仍需后续补齐 | Codex |
| 2026-06-13 | 根应用版本提升到 `0.4.12`，用于 Hosted UI DataTable 行按钮显式 params 分发和任务暂停后绑定业务行 `run_status` 释放修复；0.4.12 客户端包、正式 tag / release 与真机升级证据仍需后续补齐 | Codex |
| 2026-06-19 | 重新发布 macOS `0.4.16` 客户端升级包：删除远端旧 DMG 后重新生成并上传 `Crawler4j-0.4.16.dmg` 与 `appcast.xml`，公网下载 URL 已返回 `200` | Codex |
| 2026-06-20 | 根应用版本提升到 `0.4.17`，用于任务监控作业禁用状态、REM 固定运行模板安全门和来源代理同步匹配规则修复；0.4.17 客户端包、正式 tag / release 与真机升级证据仍需后续补齐 | Codex |
| 2026-06-22 | 根应用版本提升到 `0.4.18`，用于 VirtualBrowser 随机指纹创建期不下发具体指纹字段和 `chrome_version=139..145` 随机化；0.4.18 客户端包、正式 tag / release 与真机升级证据仍需后续补齐 | Codex |
| 2026-06-28 | 根应用版本提升到 `0.4.19`，用于 `browser.drag` 连续轨迹生成与框架自检 trace 能力；0.4.19 客户端包、正式 tag / release 与真机升级证据仍需后续补齐 | Codex |
| 2026-06-28 | 根应用版本提升到 `0.4.20`，用于 `browser.drag natural` 体感时长、约 60Hz 采样与固定 seed 默认混入运行随机盐的框架自检能力；0.4.20 客户端包、正式 tag / release 与真机升级证据仍需后续补齐 | Codex |
| 2026-06-29 | 根应用版本提升到 `0.4.21`，用于 VirtualBrowser 随机指纹代理出口 geo 校准、创建后轻量验收、风险环境标记与默认调度跳过；0.4.21 客户端包、正式 tag / release 与真机升级证据仍需后续补齐 | Codex |
| 2026-06-29 | 根应用版本提升到 `0.4.22`，用于 VirtualBrowser 随机指纹语言参数去重；0.4.22 客户端包、正式 tag / release 与真机升级证据仍需后续补齐 | Codex |
| 2026-06-30 | 根应用版本提升到 `0.4.23`，用于本轮 GitHub release 收口；0.4.23 客户端包与 Windows 真机证据仍需后续补齐 | Codex |
| 2026-07-05 | 根应用版本提升到 `0.4.24`，用于 REM 批量环境清理预览的模块候选 scope 修复；0.4.24 客户端包与 Windows 真机证据仍需后续补齐 | Codex |
| 2026-07-08 | 根应用版本提升到 `0.4.26`，用于 VirtualBrowser 创建环境指纹自洽与稳定性优化；0.4.26 客户端包与 Windows 真机证据仍需后续补齐 | Codex |
| 2026-04-22 | 补记 Windows 发布能力边界：当前仓库已具备 `package-windows-release` 与 Velopack 更新目录脚手架，但仍未形成带真机留证的正式 Windows 下载包 | Codex |
| 2026-04-21 | 补记 macOS 内部 Sparkle 更新包：当前仓库已具备 DMG / `appcast.xml` 生成脚手架，但仍依赖本机提供 Sparkle 分发目录与 EdDSA 发布配置 | Codex |
| 2026-04-20 | 补记当前交付能力边界：macOS PyInstaller bundle 已完成本地复验，Windows 桌面包仍缺打包链与正式产物 | Codex |
| 2026-04-02 | 新增正式交付包清单并登记当前基线可复用材料 | Codex |
