# TASK-042 Release Candidate Task Review

- Work item: `TASK-042`
- Task: Contracts `0.4.4` / SDK `0.4.5` / client-root `0.4.39` release candidate
- reviewer_type: `independent_subagent`
- reviewer_id: `/root/cr022_independent_review`
- reviewer_independence_evidence: reviewer 未参与本轮版本或发布实现，仅依据独立评审任务列出的 task brief、plan、implementer report、verification evidence、ledger、当前 diff 与构建产物进行审查；未读取实现者会话历史，未执行上传、提交、推送或发布状态变更。
- review_status: `changes_requested`
- next_gate_status: `changes_requested`
- author_self_check_score: `n/a`
- review_score: `82`

## Score

- 需求符合度：`23 / 30`
- 架构一致性：`17 / 20`
- 测试充分性：`15 / 20`
- 代码质量：`19 / 20`
- 文档与记忆同步：`8 / 10`

## Spec Review

- 源码事实一致：Contracts `0.4.4`、SDK `0.4.5`、root `0.4.39`；SDK/root 均要求 `crawler4j-contracts>=0.4.4,<0.5.0`，README、pyproject、`.factory/project.json` 与 `uv.lock` 对应版本一致。
- Contracts/SDK wheel 与 sdist 文件名、METADATA/PKG-INFO、依赖和记录的 SHA256 均独立核对一致；两包 publish dry-run 各只检查两个目标文件并成功。
- PyPI 官方 JSON 端点独立复核：Contracts `0.4.4`、SDK `0.4.5` 与 root `crawler4j` 项目均返回 HTTP `404`；当前未发生正式上传。
- 当前 diff 未修改消费模块或产品实现；发布范围仍是 Contracts -> SDK，root 只构建，不含桌面安装、tag 或 GitHub Release。
- 13 项 full-unit 失败在 evidence 中明确拆分为 5 项 sandbox debug path 和 8 项 read-only REM/proxy state DB 基线；当前改动为版本、依赖和文档，独立变更范围回归通过，未发现 changed-scope failure 被混入该基线。
- root wheel 元数据与体积合理，但 root sdist 被项目根内临时桌面 bundle 污染，因此“三包构建产物可作为发布候选”的验收尚未成立。

## Findings

### Critical

- 无。

### Important

- [`packages/crawler4j/dist/crawler4j-0.4.39.tar.gz`; `.factory/workitems/TASK-042/evidence/release.md:22`] root sdist 为 `166MB`，包含 `crawler4j-0.4.39/tmpk16q5yre/desktop/macos/Crawler4j.app/...` 共 `2186` 个临时 bundle 条目，包括 Qt/Python 动态库；evidence 却把该 sdist 及其哈希登记为有效构建结果。该产物越过“root build only、无 desktop installer”边界，也使 root sdist 质量 gate 失真。正式发布或提交前必须清除/排除项目根内临时构建目录，重建 root wheel/sdist，复核 manifest/体积/元数据并刷新 SHA256 与 evidence；应增加拒绝 `tmp*/desktop/**` 等非预期内容的产物测试。

### Minor

- [`docs/04-project-development/07-release-delivery/release-notes.md:44`] 文档记录 docs-stratego 为 `pages=86 contracts=0`，而 release evidence 与 `.factory/project.json` 均记录本轮结果为 `pages=87 contracts=0`；发布文档需统一为实际结果。
- [`.factory/workitems/TASK-042/evidence/release.md:37`] 聚焦回归只记录 `165 passed`，没有保留可复现的 pytest 命令与 exit code。独立 reviewer 已补跑相关范围 `174 passed`，但正式发布证据仍应补齐原命令或用可复现的新鲜命令替换该摘要。

## Quality Review

- Contracts/SDK 候选本身的版本、依赖、元数据、哈希与 dry-run 没有发现问题。
- root sdist 污染说明现有构建验证只检查“生成文件成功”，没有检查产物 manifest、异常目录或尺寸；这是发布候选必须补齐的质量门。
- 全量 13 项环境基线的边界说明可接受；本 review 未重复依赖环境状态的全量 unit，并以当前 diff、独立聚焦回归和输入包基线证据交叉核对 changed scope。
- 当前没有执行任何不可逆发布动作，changes requested 可在 upload 前安全处理。

## Verification

- 版本/Contracts/SDK/packaging 独立聚焦集：exit code `0`，`174 passed in 0.46s`，`0 failed / 0 errors / 0 skipped`。
- `uv lock --check`：exit code `0`，`Resolved 78 packages`。
- Contracts publish dry-run：exit code `0`，精确检查 `0.4.4` wheel/sdist 两文件。
- SDK publish dry-run：exit code `0`，精确检查 `0.4.5` wheel/sdist 两文件。
- 六个产物 SHA256：独立计算结果与 release evidence 全部一致。
- 三个 wheel 与三个 sdist 的 METADATA/PKG-INFO：名称、版本、Python 要求及 SDK/root Contracts lower bound 与源码一致。
- PyPI JSON preflight：Contracts target `404`、SDK target `404`、root project `404`，命令 exit code `0`。
- artifact manifest：root wheel `938KB`、`143` files；root sdist `166MB`，其中临时 desktop bundle `2186` files，确认阻塞问题。
- `git diff --check`：exit code `0`，无输出。
- 未重复 full unit；输入包记录 `1234 passed` 加 13 项既有环境基线，本结论不把这些 13 项写成通过，也不据此批准候选。

## Gate

`changes_requested`

在 root sdist 重建、哈希/evidence 刷新及文档不一致修正后，需要重新进行独立 release-candidate review。不得据本 review 上传、提交、推送或把 TASK-042 标记为 done。
