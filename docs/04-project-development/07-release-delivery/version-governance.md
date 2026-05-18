# 版本治理规则

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 发布负责人 | Tech Lead | Dev | QA  
**上游输入：** `packages/crawler4j/pyproject.toml` | Git tag | 子包 `pyproject.toml` | docs-stratego 源仓导航
**下游输出：** `release-notes.md` | `deployment-guide.md` | `docs/index.md` | `.factory/project.json`
**关联 ID：** `CR-001`, `TASK-004`, `REQ-004`, `REQ-0401`, `NFR-002`
**最后更新：** 2026-05-18

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
| 根应用包版本 | `0.4.1` | 当前仓库 HEAD 已切到 0.4.1 发布候选版本 |
| 根应用运行时版本 | `0.4.1` | 由运行时代码从包元数据或 `packages/crawler4j/pyproject.toml` 解析 |
| 最近正式发布 tag | `v0.2.0` | 最新已知正式发布 |
| SDK | `0.4.1` | 当前工作区 SDK 版本；CLI 命令树、脚手架与开发者文档已同步到 0.4.x，并已按 0.4.1 发布到 PyPI |
| Contracts | `0.4.1` | 当前工作区 Contracts 版本；共享契约与 SDK / Core README、发布文档口径已同步收口，并已按 0.4.1 发布到 PyPI |
| docs-stratego 主文档版本 | 待正式发布前确认 | 当前源码文档入口已把 0.4.x 作为当前主线、0.3.x 作为历史维护；发布站点切换仍需随正式发布动作确认 |

## 3. 为什么这样定义

- 过去的问题不是“版本号多少”，而是同一份仓库里同时存在根包版本、运行时版本和 tag 口径漂移。
- 当前工作区已经切到 `0.4.1`，但 Git tag 仍停留在 `v0.2.0`；如果不显式分层，维护者会误以为 `0.4.1` 已正式打 tag 并发布。
- 版本治理文档的职责不是制造第二事实源，而是明确“当前源码版本”和“最近正式发布”之间的关系。

## 4. 发布前动作

在下一次正式发布根应用前，至少完成：

1. 确认 `packages/crawler4j/pyproject.toml`、运行时版本显示和 README 仍统一指向目标正式版本 `0.4.1`
2. 更新 `docs/04-project-development/07-release-delivery/release-notes.md`
3. 复验 `uv run pytest -q`
4. 复验 `uv run python scripts/smoke_test_ui.py`
5. 复验 Root / SDK / Contracts build
6. 为根应用补打对应 `0.4.1` Git tag 与正式 release 资产
7. 若发布会切换文档主版本，则同步更新 `docs/index.md`、对应 `version.yaml` 和 docs-stratego 历史版本入口

## 5. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
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
