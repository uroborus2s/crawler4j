# TASK-042 Release Candidate Independent Rereview

- Work item: `TASK-042`
- Task: Contracts `0.4.4` / SDK `0.4.5` / client-root `0.4.39` release candidate fixes
- reviewer_type: `independent_subagent`
- reviewer_id: `/root/cr022_independent_review`
- reviewer_independence_evidence: reviewer 未参与版本升级、发布候选实现或 root sdist 修复；本轮仅复核原 review、文件化 review response/TDD/release evidence、当前相关 diff 与重建产物，并独立运行 scoped tests、manifest/hash/dry-run/PyPI checks。未执行上传、提交、推送或状态关闭。
- review_status: `approved`
- next_gate_status: `pending_human_confirmation`
- author_self_check_score: `n/a`
- review_score: `100`

## Score

- 需求符合度：`30 / 30`
- 架构一致性：`20 / 20`
- 测试充分性：`20 / 20`
- 代码质量：`20 / 20`
- 文档与记忆同步：`10 / 10`

## Findings

### Critical

- 无。

### Important

- 无未解决项。

### Minor

- 无未解决项。

## Resolved Findings

- 原 `Important` 已关闭：desktop/updates 保存目录从 Hatch package root 移到 workspace root；重建 root sdist 为 `37,279,993` bytes、`529` entries，独立扫描没有 `desktop`、`updates` 或 `tmp*` subtree。post-build manifest gate 要求 root 只生成一个 sdist，并拒绝 archive path 含 preserved desktop/update component；对应 preservation-boundary 与 contaminated-sdist 两组 RED/GREEN 已文件化。
- 原 docs `Minor` 已关闭：release notes、release evidence、`.factory/project.json` 与 memory 均统一为 `pages=87 contracts=0`。
- 原 reproducibility `Minor` 已关闭：release evidence 已记录完整六文件命令、`--offline --no-sync` 选项、exit code `0` 和 `175 passed`；独立复跑得到相同计数。

## Spec Review

- root wheel/sdist 版本仍为 `0.4.39`；重建 sdist 的 PKG-INFO 要求 `crawler4j-contracts>=0.4.4,<0.5.0`，与源码和 wheel 一致。
- Contracts `0.4.4`、SDK `0.4.5` 产物未被修复误改；六个最终 SHA256 与刷新后的 release evidence 全部一致。
- root sdist 内容污染已从根因和产物两端关闭：临时保存目录不再进入 package root，构建后还有独立 archive manifest fail-closed gate。
- 当前范围仍只准备 Contracts -> SDK PyPI 发布；root 仅构建，未创建 desktop installer、root PyPI project、tag 或 GitHub Release。
- 13 项 full-unit 环境基线继续与 changed scope 分开记录；修复后全量计数增加到 `1235 passed` 是新增打包回归测试导致，13 项类别没有被写成通过。
- 文档、project facts、release evidence 与 memory 已同步最终产物、测试计数和 docs count。

## Quality Review

- 修复位置位于 workspace build owner，没有通过手工删除 archive 内容或放宽构建范围绕过问题。
- manifest gate 使用 tar member path components 检查 preserved directory names，并在 sdist 数量不为一时失败；回归覆盖保存目录边界与污染包拒绝行为。
- 重建 artifact manifest、体积、metadata 和 hash 均与 evidence 一致；未发现新的 Critical、Important 或 Minor 问题。

## Verification

- release-focused 六文件精确命令：exit code `0`，`175 passed in 0.74s`，`0 failed / 0 errors / 0 skipped`。
- packaging regression 文件：exit code `0`，`63 passed in 0.11s`，`0 failed / 0 errors / 0 skipped`。
- root sdist：`37,279,993` bytes、`529` entries；独立 `rg '(^|/)(desktop|updates|tmp[^/]*)(/|$)'` 返回 exit `1` 且无输出，表示没有匹配污染 subtree。
- 六产物 SHA256：独立结果与 release evidence 全部一致；root sdist 为 `376b3e1e44ed585c1599da0f0f3a06fc3e0d95b765e5f117baff1c9f2dacc627`，root wheel hash 保持不变。
- root sdist PKG-INFO：`crawler4j 0.4.39`、Python `>=3.12`、Contracts `>=0.4.4,<0.5.0`。
- Contracts/SDK publish dry-run：均 exit code `0`，各精确检查 wheel/sdist 两文件。
- PyPI JSON preflight：Contracts target `404`、SDK target `404`、root project `404`，exit code `0`。
- `uv lock --check` 与 `git diff --check`：exit code `0`。
- 未重复 full unit；采用刷新 evidence 的 `1235 passed` 加 13 项既有环境基线，只把独立 scoped commands 用于本轮批准结论。

## Gate

`pending_human_confirmation`

本结论仅表示独立 reviewer 通过修复后的发布候选；不等于人工确认，也不授权上传、提交、推送或将 TASK-042 标记为 done。
