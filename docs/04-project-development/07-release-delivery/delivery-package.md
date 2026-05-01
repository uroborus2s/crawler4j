# 交付包清单

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 草稿
**负责人：** 当前仓库维护者
**主要读者：** 发布负责人 | 交付方 | 运维 | 管理员
**上游输入：** `acceptance-checklist.md` | `release-notes.md` | `version-governance.md` | `docs/04-project-development/08-operations-maintenance/deployment-guide.md`
**下游输出：** 交付签收 | `docs/02-user-guide/admin-guide.md` | `docs/04-project-development/08-operations-maintenance/operations-runbook.md`
**关联 ID：** `REL-005`, `REL-006`, `TASK-017`, `REQ-004`
**最后更新：** 2026-05-01

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
| macOS 桌面包 | 已具备本地构建验证 | 2026-05-01 `uv run package-desktop` 已按 0.4.0 当前依赖线生成 `packages/crawler4j/dist/desktop/macos/Crawler4j.app`，且分发目录只保留该 `.app`；PyInstaller 中间产物固定放在 `packages/crawler4j/build/pyinstaller/macos/` |
| macOS 内部 Sparkle 更新包 | 已具备本地构建/上传脚手架 | `uv run install-sparkle --archive ...` 可先把 Sparkle release archive 落到仓库约定目录；`uv run package-macos-internal-release` 生成内部 DMG 与 `appcast.xml`；`uv run deploy-macos-internal-release` 则会继续把 `packages/crawler4j/dist/updates/macos/` 上传到 `CRAWLER4J_UPDATE_UPLOAD_TARGET/mac/` |
| Windows 桌面包 | 已具备发布脚手架，待正式批次补齐证据 | 仓库已具备 `PyInstaller onedir + Velopack` 发布链，`uv run package-windows-release` 可生成 `Setup.exe` / `.nupkg` / `releases.<channel>.json`，`uv run deploy-windows-release` 可继续通过 OpenSSH `sftp` 把 `packages/crawler4j/dist/updates/windows/` 上传到 `CRAWLER4J_UPDATE_UPLOAD_TARGET/win/`；但当前批次仍缺 Windows 真机签名、安装、升级留证与正式下载地址 |
| 正式交付产物 | 待发布时补齐 | 当前只有本地验证产物，不等于已形成可对外下载的正式发布物 |

## 4. 使用规则

- 每一次正式交付都应原地更新本文件，不创建 `delivery-package-v2.md`。
- 如果本次不交付 SDK / Contracts，必须显式写明“不包含”的原因。
- 如果交付对象不是 Core 维护者，而是现场实施或运维团队，必须同时附带管理员和运行文档。

## 5. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-05-01 | 补记 0.4.0 本地交付证据：三包 build 和 macOS `package-desktop` 已重新通过；正式交付仍需 Windows 真机证据、publish/远端 release 与交付批次闭环 | Codex |
| 2026-04-22 | 补记 Windows 发布能力边界：当前仓库已具备 `package-windows-release` 与 Velopack 更新目录脚手架，但仍未形成带真机留证的正式 Windows 下载包 | Codex |
| 2026-04-21 | 补记 macOS 内部 Sparkle 更新包：当前仓库已具备 DMG / `appcast.xml` 生成脚手架，但仍依赖本机提供 Sparkle 分发目录与 EdDSA 发布配置 | Codex |
| 2026-04-20 | 补记当前交付能力边界：macOS PyInstaller bundle 已完成本地复验，Windows 桌面包仍缺打包链与正式产物 | Codex |
| 2026-04-02 | 新增正式交付包清单并登记当前基线可复用材料 | Codex |
