# 发布说明

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 草稿  
**负责人：** 当前仓库维护者  
**主要读者：** 发布负责人 | QA | 维护者  
**上游输入：** Git tag | `docs/04-project-development/02-discovery/current-state-analysis.md` | 本地构建结果  
**下游输出：** 后续正式 release notes | `delivery-package.md`（待需要时补齐）  
**关联 ID：** `REL-001`, `REL-002`, `BUG-001`, `CR-001`  
**最后更新：** 2026-03-31  

## 1. 最新已知正式发布

### `REL-001` `v0.1.1`

- Tag 时间：2026-01-03
- Tag 标题：`Release v0.1.1: Fix discard logic and account blacklisting`
- 关联提交：`f3aa4626e007cb39414073c28370faf31164f05b`

## 2. 当前仓库相对正式发布的状态

- 当前工作区根应用版本：`0.1.2.dev20260326`
- 当前运行时版本：`0.1.2.dev20260326`
- 最近正式发布 tag：`v0.1.1`
- SDK 当前版本：`2.0.0`
- Contracts 当前版本：`1.0.1`
- 当前工作区已明确区分“未发布开发版”和“最近正式发布”
- SDK 当前口径已删除 `DataService` 兼容层，旧模块需要升级到 `ctx.db` 最小数据接口

## 3. 2026-03-26 本地验证结论

| 项目 | 结果 |
|---|---|
| Root wheel/sdist build | 通过 |
| SDK wheel/sdist build | 通过 |
| Contracts wheel/sdist build | 通过 |
| Docs markdown tree | 通过 |
| Root script 与 UI smoke | 通过 |
| PyInstaller 出包 | 通过 |
| Root release 元数据一致性 | 通过 |
| 默认 `ruff` gate | 通过 |

## 4. 当前不建议直接发布的原因

- 当前根应用版本仍是未发布开发版 `0.1.2.dev20260326`
- `ctrip` 真实站点 E2E 与正式 release closeout 仍未完成

## 5. 下一版发布前必须满足

- 按 [版本治理规则](version-governance.md) 将根应用从开发版切到正式版本
- 更新 Git tag 与 release notes
- 决定真实站点 E2E 与 release closeout 的先后顺序，并完成至少一轮闭环
- 至少复验 `uv run pytest -q`、根应用 smoke、Root / SDK / Contracts build

## 6. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-26 | 建立基线 release notes | Codex |
| 2026-03-26 | 按统一版本规则区分当前工作区版本与最近正式发布 | Codex |
| 2026-03-31 | 记录 SDK `2.0.0` 破坏性升级和模块数据接口升级要求 | Codex |
