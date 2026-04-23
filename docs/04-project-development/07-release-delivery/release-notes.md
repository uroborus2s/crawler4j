# 发布说明

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 草稿  
**负责人：** 当前仓库维护者  
**主要读者：** 发布负责人 | QA | 维护者  
**上游输入：** Git tag | `docs/04-project-development/02-discovery/current-state-analysis.md` | 本地构建结果  
**下游输出：** 后续正式 release notes | `delivery-package.md`（待需要时补齐）  
**关联 ID：** `REL-001`, `REL-002`, `BUG-001`, `CR-001`  
**最后更新：** 2026-04-17  

## 1. 最新已知正式发布

### `REL-001` `v0.1.1`

- Tag 时间：2026-01-03
- Tag 标题：`Release v0.1.1: Fix discard logic and account blacklisting`
- 关联提交：`f3aa4626e007cb39414073c28370faf31164f05b`

## 2. 当前仓库相对正式发布的状态

- 当前工作区根应用版本：`0.3.0`
- 当前运行时版本：`0.3.0`
- 最近正式发布 tag：`v0.1.1`
- SDK 当前版本：`0.5.2`
- Contracts 当前版本：`0.3.0`
- 当前工作区已切到 `0.3.0` 发布目标，但尚未补打正式 Git tag / release 资产
- `crawler4j-sdk 0.5.2` 已于 2026-04-24 完成本地构建并发布到 PyPI
- SDK 当前口径已收敛到 `TaskContext.tools` 统一工具接口，模块侧不再使用专用 `ctx.db` / `ctx.captcha` 字段
- 当前工作区已进一步收敛到“ATM hooks + `TaskSignal`”单一生命周期链；`TaskFlow.on_complete/on_error` 与 `TaskScript` 私有 callbacks 已删除

## 3. 2026-04-17 本地复核结论

| 项目 | 结果 |
|---|---|
| 版本相关单测（`test_version_service.py`、`test_vscode.py`） | 通过（`5 passed`） |
| Root wheel/sdist build | 通过（产物：`crawler4j-0.2.0`） |
| SDK wheel/sdist build | 通过（产物：`crawler4j_sdk-0.4.0`） |
| Contracts wheel/sdist build | 通过（产物：`crawler4j_contracts-0.2.0`） |
| Docs markdown tree | 通过（`docs-stratego source validate --repo-path .`） |

## 4. 当前不建议直接发布的原因

- `0.2.0` 对应的 Git tag、正式 release notes 与交付批次仍未完成
- `ctrip` 真实站点 E2E 与正式 release closeout 仍未完成

## 5. 下一版发布前必须满足

- 按 [版本治理规则](version-governance.md) 复验 `0.2.0` 仍是目标正式版本，且 README / 包描述 / release 文档不再混用旧口径
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
