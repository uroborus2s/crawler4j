# 验收检查清单

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 草稿
**负责人：** 当前仓库维护者
**主要读者：** 发布负责人 | QA | Tech Lead
**上游输入：** `version-governance.md` | `release-notes.md` | `docs/04-project-development/06-testing-verification/test-plan.md` | `docs/04-project-development/08-operations-maintenance/deployment-guide.md`
**下游输出：** `delivery-package.md` | 发布决策 | `docs/04-project-development/08-operations-maintenance/operations-runbook.md`
**关联 ID：** `REL-003`, `REL-004`, `TASK-017`, `REQ-009`, `REQ-0401`, `NFR-003`
**最后更新：** 2026-04-30

## 1. 使用范围

本清单用于判断“当前工作区是否可以进入正式发布或交付阶段”。它不是测试计划的替代，而是发布前的最终 Gate。

## 2. 发布前最小检查项

| 类别 | 检查项 | 证据 | 当前基线状态 |
|---|---|---|---|
| 版本 | `packages/crawler4j/pyproject.toml` 与发布目标版本一致，运行时版本服务可正确读取 | `version-governance.md` | 已具备（2026-04-19 复验；当前为 `0.2.0`） |
| 版本 | 当前工作区版本、最近正式 tag、SDK/Contracts 版本口径清楚 | `release-notes.md` | 已具备 |
| 测试 | `uv run pytest -q` 通过 | `test-plan.md` | 已具备（2026-04-21 复验为 `523 passed`） |
| 测试 | `uv run ruff check .` 通过 | `test-plan.md` | 已具备（2026-04-21 复验通过） |
| 运行 | `uv run python scripts/smoke_test_ui.py` 通过 | `test-plan.md` | 已具备（2026-04-21 复验通过；当前 smoke 已覆盖 qasync Shell 生命周期与 Dashboard 异步刷新） |
| 构建 | Root / SDK / Contracts build 通过 | `test-plan.md` | 已具备（2026-04-21 复验通过） |
| 构建 | 桌面客户端下载包（macOS / Windows）齐备 | `delivery-package.md` | 阻塞（2026-04-20 已本地复验 macOS PyInstaller bundle；2026-04-22 已补齐 Windows `PyInstaller onedir + Velopack` 发布链，但当前批次仍缺 Windows 真机签名、安装、升级证据与正式下载地址） |
| 业务 | `ctrip` 真实站点 E2E 完成并记录结果 | `ctrip-real-site-e2e-closeout.md` + 真实环境验证记录 | 阻塞（当前只补齐了 DevLink 活跃事实、fresh ZIP 预检与历史登录日志，仍未完成本轮 DevLink + ZIP 双链真实站点闭环） |
| 业务 | 若本次批次包含环境候选 Service Job 队列能力，则已验证“运行中 / 等待中”口径、FIFO 补位、容量扩张补位、候选纯函数实时过滤、模块环境授权和等待超时收口 | `test-plan.md` + 对应测试记录 | 已具备（当前 HEAD 已纳入 `TASK-023` / `REQ-009` 变更，`TC-026` / `TC-027` 本地回归已完成；正式切版时仍需把这组证据绑定到发布批次） |
| 文档 | 根导航、文档索引、memory 映射同步完成 | `docs/index.md`、`document-index.md`、`.factory/memory/doc-map.md` | 已具备 |
| 文档 | docs-stratego 主文档指向当前已发布版本，未发布版本只在开发版入口，历史版本入口仍可访问 | `version-governance.md`、`0.4.0-guide-versioning-architecture.md` | 待实施 |
| 运维 | 部署说明、运行手册、管理员指南可独立阅读 | `deployment-guide.md`、`operations-runbook.md`、`admin-guide.md` | 已具备 |
| 交付 | 交付包内容、签收对象和阻塞项清楚 | `delivery-package.md` | 待正式发布 |

## 3. 放行规则

- 有任何一项标记为“阻塞”，不得进入正式发布。
- 标记为“待正式切版”或“待正式发布”的项，只有在本次发布确实覆盖对应动作时才能关闭。
- 如果本次只是内部验证或文档收口，可记录为“未触发发布”，但不能伪装成已放行。

## 4. 当前阻塞项

1. `ctrip` 真实站点 E2E 仍未按 `ctrip-real-site-e2e-closeout.md` 完成本轮 DevLink + ZIP 双链回放并留证；当前只复验了 DevLink 活跃状态、fresh ZIP 预检和历史真实登录日志。
2. 本地 `v0.2.0` Git tag 已存在，但远端 GitHub release 资产与本次交付批次未在本轮复核闭环。
3. 当前虽已具备 Windows `PyInstaller onedir + Velopack` 发布链，但本轮仍缺 Windows 真机签名、安装、升级留证与正式下载地址，不能声称“Windows 交付包已放行”。

## 5. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
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
