# 发布说明

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 草稿  
**负责人：** 当前仓库维护者  
**主要读者：** 发布负责人 | QA | 维护者  
**上游输入：** Git tag | `docs/04-project-development/02-discovery/current-state-analysis.md` | 本地构建结果  
**下游输出：** 后续正式 release notes | `delivery-package.md`（待需要时补齐）  
**关联 ID：** `REL-001`, `REL-002`, `BUG-001`, `CR-001`  
**最后更新：** 2026-05-18

## 1. 最新已知正式发布

### `REL-001` `v0.2.0`

- Tag 时间：2026-04-20
- Tag 标题：`release: v0.2.0`
- 关联提交：`2d914f48566647304e6a14053063dadb5b305ef1`

## 2. 当前仓库相对正式发布的状态

- 当前工作区根应用版本：`0.4.1`
- 当前运行时版本：`0.4.1`
- 最近正式发布 tag：`v0.2.0`
- SDK 当前版本：`0.4.1`
- Contracts 当前版本：`0.4.1`
- 当前工作区已切到 `0.4.1` 源码版本线，准备作为 `0.4.0` 分支并入 `main` 前的正式发布候选
- `crawler4j-sdk 0.4.1` 与 `crawler4j-contracts 0.4.1` 已按 `contracts -> sdk` 依赖顺序完成 PyPI 发布
- SDK 当前口径已收敛为“数据库唯一入口 `ctx.db`，非数据库宿主能力继续通过 `ctx.tools.call(...)` 调用”；模块侧不再使用专用 `ctx.captcha` 字段
- 当前 0.4.x 工作区已移除 `hooks/*.py` 生命周期运行链；模块流程控制通过 workflow 主体返回 `TaskResult`，workflow/component 可选实现 `setup(ctx, workflow)` 和 `cleanup(ctx, outcome)`，环境回收由宿主收口

## 3. 当前证据状态

| 项目 | 结果 |
|---|---|
| 版本相关单测（`test_version_service.py`、`test_vscode.py`） | 历史通过（2026-04-17 `5 passed`）；本轮未重跑 |
| Root wheel/sdist build | 通过（2026-05-18 `uv run build` 产出 `crawler4j 0.4.1` wheel/sdist） |
| SDK wheel/sdist build | 通过（2026-05-18 `uv run build` 产出 `crawler4j-sdk 0.4.1` wheel/sdist） |
| SDK publish | 通过（2026-05-18 `uv run publish crawler4j-sdk` 上传 0.4.1 到 PyPI） |
| Contracts wheel/sdist build | 通过（2026-05-18 `uv run build` 产出 `crawler4j-contracts 0.4.1` wheel/sdist） |
| Contracts publish | 通过（2026-05-18 `uv run publish crawler4j-contracts` 上传 0.4.1 到 PyPI） |
| Desktop PyInstaller / macOS Sparkle bundle | 通过（2026-05-18 `uv run deploy-macos-internal-release` 产出 `Crawler4j.app`、`Crawler4j-0.4.1.dmg`、`appcast.xml` 并上传 macOS 更新目录） |
| Full test / lint / smoke | 通过（2026-05-18 `991 passed`，`ruff check .`、`uv lock --check`、`git diff --check` 通过） |
| Docs markdown tree | 历史通过（`docs-stratego source validate --repo-path .`）；本轮未重跑 |

## 4. 当前不建议直接发布的原因

- `0.4.1` 对应的 Git tag、正式 release notes 与交付批次仍未完成
- `ctrip` 真实站点 E2E 与正式 release closeout 仍未完成
- macOS 内部升级包已完成，本轮仍缺 Windows 真机签名、安装和自更新留证
- Windows 真机签名、安装和自更新留证仍未完成

## 5. 下一版发布前必须满足

- 按 [版本治理规则](version-governance.md) 复验 `0.4.1` 仍是目标正式版本，且 README / 包描述 / release 文档不再混用旧口径
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
