# 验收检查清单

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 草稿
**负责人：** 当前仓库维护者
**主要读者：** 发布负责人 | QA | Tech Lead
**上游输入：** `version-governance.md` | `release-notes.md` | `docs/04-project-development/06-testing-verification/test-plan.md` | `docs/04-project-development/08-operations-maintenance/deployment-guide.md`
**下游输出：** `delivery-package.md` | 发布决策 | `docs/04-project-development/08-operations-maintenance/operations-runbook.md`
**关联 ID：** `REL-003`, `REL-004`, `TASK-017`, `REQ-009`, `REQ-0401`, `NFR-003`
**最后更新：** 2026-06-15

## 1. 使用范围

本清单用于判断“当前工作区是否可以进入正式发布或交付阶段”。它不是测试计划的替代，而是发布前的最终 Gate。

## 2. 发布前最小检查项

| 类别 | 检查项 | 证据 | 当前基线状态 |
|---|---|---|---|
| 版本 | `packages/crawler4j/pyproject.toml` 与发布目标版本一致，运行时版本服务可正确读取 | `version-governance.md` | 已具备（当前根应用源码线为 `0.4.14`，最近正式 tag 仍为 `v0.2.0`，本轮 REM UI 定向回归通过） |
| 版本 | 当前工作区版本、最近正式 tag、SDK/Contracts 版本口径清楚 | `release-notes.md` | 已具备 |
| 测试 | `uv run pytest -q` 通过 | `test-plan.md` | 已具备（2026-05-18 复验为 `992 passed`） |
| 测试 | `uv run ruff check .` 通过 | `test-plan.md` | 已具备（2026-05-18 复验通过） |
| 运行 | `uv run python scripts/smoke_test_ui.py` 通过 | `test-plan.md` | 已具备（2026-05-01 复验通过；当前 smoke 覆盖 Shell 导航/页面数量与 Dashboard 异步刷新） |
| 构建 | Root / SDK / Contracts build 通过 | `test-plan.md` | 部分具备（2026-05-26 已产出 Root 0.4.3 wheel/sdist；当前 root 0.4.14 尚未刷新，本轮 SDK / Contracts 0.4.2 wheel/sdist 已构建并发布） |
| 构建 | 桌面客户端下载包（macOS / Windows）齐备 | `delivery-package.md` | 部分具备（2026-05-18 macOS Sparkle DMG / appcast 已生成并上传；Windows `PyInstaller onedir + Velopack` 发布链已落地，但当前批次仍缺 Windows 真机签名、安装、升级证据与正式下载地址） |
| 业务 | `ctrip` 真实站点 E2E 完成并记录结果 | `ctrip-real-site-e2e-closeout.md` + 真实环境验证记录 | 阻塞（当前只补齐了 DevLink 活跃事实、fresh ZIP 预检与历史登录日志，仍未完成本轮 DevLink + ZIP 双链真实站点闭环） |
| 业务 | 若本次批次包含环境候选 Service Job 队列能力，则已验证“运行中 / 等待中”口径、FIFO 补位、容量扩张补位、候选纯函数实时过滤、模块环境授权和等待超时收口 | `test-plan.md` + 对应测试记录 | 已具备（当前 HEAD 已纳入 `TASK-023` / `REQ-009` 变更，`TC-026` / `TC-027` 本地回归已完成；正式切版时仍需把这组证据绑定到发布批次） |
| 文档 | 根导航、文档索引、memory 映射同步完成 | `docs/index.md`、`document-index.md`、`.factory/memory/doc-map.md` | 已具备 |
| 文档 | docs-stratego 主文档指向当前已发布版本，未发布版本只在开发版入口，历史版本入口仍可访问 | `version-governance.md`、`0.4.0-guide-versioning-architecture.md` | 待正式发布前确认 |
| 运维 | 部署说明、运行手册、管理员指南可独立阅读 | `deployment-guide.md`、`operations-runbook.md`、`admin-guide.md` | 已具备 |
| 交付 | 交付包内容、签收对象和阻塞项清楚 | `delivery-package.md` | 待正式发布 |

## 3. 放行规则

- 有任何一项标记为“阻塞”，不得进入正式发布。
- 标记为“待正式切版”或“待正式发布”的项，只有在本次发布确实覆盖对应动作时才能关闭。
- 如果本次只是内部验证或文档收口，可记录为“未触发发布”，但不能伪装成已放行。

## 4. 当前阻塞项

1. `ctrip` 真实站点 E2E 仍未按 `ctrip-real-site-e2e-closeout.md` 完成本轮 DevLink + ZIP 双链回放并留证；当前只复验了 DevLink 活跃状态、fresh ZIP 预检和历史真实登录日志。
2. 当前 `0.4.14` 对应的 Git tag / GitHub release 资产与本次交付批次未在本轮复核闭环；SDK / Contracts 0.4.2 PyPI publish 已完成，macOS 0.4.3 客户端升级包已完成。
3. 当前虽已具备 Windows `PyInstaller onedir + Velopack` 发布链，但本轮仍缺 Windows 真机签名、安装、升级留证与正式下载地址，不能声称“Windows 交付包已放行”。

## 5. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-05-18 | 复验 0.4.1 fresh gate：全量测试、lint、三包 build、SDK/Contracts PyPI publish 与 macOS Sparkle 客户端升级包已完成；正式发布仍因 `ctrip` 真站 E2E、Windows 真机证据和 GitHub release / 交付批次未闭环保持 `No-Go` | Codex |
| 2026-05-01 | 追加 0.4.0 全面审查后的最新 gate：`886 passed`、lint、UI smoke、三包构建、SDK CLI help 与 macOS `package-desktop` 已复验；正式发布仍因 `ctrip` 真站 E2E、Windows 真机证据、publish 和交付批次未闭环保持 `No-Go` | Codex |
| 2026-05-18 | 发布候选版本提升到 `0.4.1`；版本、构建、publish 与客户端升级包已按新版本重跑留证 | Codex |
| 2026-05-18 | 根应用版本提升到 `0.4.2`，用于后续 Windows 修复版客户端升级包；Root build 和 Windows 真机升级证据仍需按新版本补齐 | Codex |
| 2026-05-26 | 根应用版本提升到 `0.4.3`，用于 REM 环境列表刷新误删环境修复；Root build 与 macOS Sparkle 更新包已补齐，Windows 真机升级证据仍需在 Windows 构建机补齐 | Codex |
| 2026-05-27 | 根应用版本提升到 `0.4.4`，用于 VirtualBrowser 启动就绪竞态、`addBrowser` relay 500 重试与脱敏诊断日志修复；正式 tag / release 资产仍需后续补齐 | Codex |
| 2026-05-30 | 根应用版本提升到 `0.4.5`，用于开发模块源码目录保留 `.venv/` 时跳过忽略目录 symlink 的客户端修复；正式 tag / release 资产仍需后续补齐 | Codex |
| 2026-06-07 | 根应用版本修正提升到 `0.4.6`，用于指纹浏览器生命周期串行化修复版；正式 tag / release、0.4.6 客户端包与真机升级证据仍需后续补齐 | Codex |
| 2026-06-09 | 根应用版本提升到 `0.4.7`，用于对象 cleanup 固定超时移除修复版；正式 tag / release、0.4.7 客户端包与真机升级证据仍需后续补齐 | Codex |
| 2026-06-11 | 根应用版本提升到 `0.4.8`，用于 IP 池最久未使用默认分配策略、最近使用时间记录与旧库迁移修复版；正式 tag / release、0.4.8 客户端包与真机升级证据仍需后续补齐 | Codex |
| 2026-06-12 | 根应用版本提升到 `0.4.9`，用于运行模板指定环境选择、DataTable 可见筛选排序和 IP 池条目人工状态等客户端改动；正式 tag / release、0.4.9 客户端包与真机升级证据仍需后续补齐 | Codex |
| 2026-06-13 | 根应用版本提升到 `0.4.10`，用于任务监控暂停后对象 cleanup 链路 `asyncio.CancelledError` 截断修复；正式 tag / release、0.4.10 客户端包与真机升级证据仍需后续补齐 | Codex |
| 2026-06-13 | 根应用版本提升到 `0.4.11`，用于 Hosted UI DataTable 自定义行按钮分发到同名 `@ui_action` 的客户端修复；正式 tag / release、0.4.11 客户端包与真机升级证据仍需后续补齐 | Codex |
| 2026-06-13 | 根应用版本提升到 `0.4.12`，用于 Hosted UI DataTable 行按钮显式 params 分发和任务暂停后绑定业务行 `run_status` 释放修复；正式 tag / release、0.4.12 客户端包与真机升级证据仍需后续补齐 | Codex |
| 2026-06-15 | SDK / Contracts 版本提升到 `0.4.2`，根应用版本同步提升到 `0.4.13`，用于发布已有环境导入 workflow 场景契约与代理读取能力；SDK / Contracts PyPI 发布与本轮验证证据已补齐 | Codex |
| 2026-06-15 | 根应用版本提升到 `0.4.14`，用于在环境管理列表展示环境绑定的代理 IP；正式 tag / release、0.4.14 客户端包与真机升级证据仍需后续补齐 | Codex |
| 2026-04-30 | 增补 docs-stratego 文档主版本 gate：发布前必须确认主入口指向当前已发布版本，历史版本保留，开发中版本不得成为默认主文档 | Codex |
| 2026-04-30 | 将 `REQ-009` 发布 gate 从固定资源池队列改为环境候选队列：候选纯函数、模块环境授权、FIFO 补位与等待超时收口是当前正式验证项 | Codex |
| 2026-04-22 | 追加 Windows 发布链现状：`package-windows-release` 与 Velopack 宿主更新入口已落地，但正式 gate 仍缺 Windows 真机签名、安装、升级证据，因此结论继续保持 `No-Go` | Codex |
| 2026-04-21 | 追加本轮 fresh gate：`523 passed`、lint、强化后的 UI smoke 与 workspace build 已复验；MMS 安装回滚与 UI 异步刷新验证已补齐，但 `ctrip` 真站 E2E、远端 release/交付批次闭环与 Windows 桌面包仍阻塞，因此结论继续保持 `No-Go` | Codex |
| 2026-04-20 | 追加本轮最终 gate 结论：`485 passed`、lint、UI smoke、三包构建与 macOS PyInstaller bundle 已复验，但 `ctrip` 真站 E2E、tag/release、交付批次与 Windows 桌面包仍阻塞，结论继续保持 `No-Go` | Codex |
| 2026-04-20 | 历史记录：曾修正固定资源池队列发布 gate；该 gate 已被 2026-04-30 环境候选 gate 替代 | Codex |
| 2026-04-19 | 历史记录：曾补记固定资源池 Service Job 条件式发布 gate；该 gate 已被 2026-04-30 环境候选 gate 替代 | Codex |
| 2026-04-19 | 追加本轮 fresh gate 结论：版本服务、全量测试、lint、UI smoke、三包构建、DevLink 活跃状态与 fresh ZIP 预检已复验，但真实站点 E2E、tag/release 与交付批次仍阻塞，因此结论保持 `No-Go` | Codex |
| 2026-04-02 | 新增正式验收检查清单，并登记当前基线状态 | Codex |
| 2026-04-17 | 按 `0.2.0` 发布基线修正版本检查项，明确当前剩余阻塞已转为 Git tag / 交付批次与真实站点 E2E | Codex |
