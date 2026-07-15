# CR-022 Hidden Form Scrollbar Task Review

- Work item: `CR-022`
- Task: `任务 2B：Renderer 长 Form 隐藏式滚动条`
- reviewer_type: `independent_subagent`
- reviewer_id: `/root/cr022_independent_review`
- reviewer_independence_evidence: reviewer 未参与本增量实现，只读取独立评审任务指定的文件化 requirements、plan、implementer report、verification evidence、相关文档、代码测试与当前 diff；未读取实现者会话历史，未修改产品实现或测试。
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

## Spec Review

- CRUD Form 的水平、垂直策略均为 `ScrollBarAlwaysOff`，原生滚动槽双向隐藏。
- 实现保留原 `QScrollArea`、`widgetResizable=True`、内容 widget 和滚动范围；35 字段测试等待垂直 `maximum() > 0`，并验证 Page Down 与程序化设置滚动位置均有效，没有把隐藏误实现为禁用滚动。
- 确认/取消按钮仍由外层 dialog layout 管理，并由断言证明不是 scroll area 的后代。
- 产品代码仅修改垂直 scrollbar policy 一行；create/update/default/on_change/reset、共享多列布局与 submit 路径未改变，相关 renderer 与七文件目标回归通过。
- 大 gap 用例注入固定 `800x800` screen geometry，只固定产品算法原本依赖的外部屏幕输入；它仍断言降为单列、spacing 受几何约束及 input 留在真实 viewport。宽屏 `gap=100` 的独立既有测试继续覆盖多列路径，因此该调整没有掩盖产品缺陷。
- 当前 diff 未修改 Contracts、SDK、schema、消费模块、版本或 lock，也未加入业务特化。
- requirements、plan、verification evidence、正式文档与 `.factory/memory/` 已同步。

## Findings

### Critical

- 无。

### Important

- 无。

### Minor

- 无。

## Quality Review

- 改动使用 Qt 原生 scrollbar policy，无新组件、新配置或额外抽象，符合 renderer owner 边界。
- 测试同时覆盖策略、非零范围、键盘滚动、程序化滚动、固定按钮与屏幕约束，验证的是可见行为而非仅实现细节。
- 补充 Qt `QScrollArea` 探针在双向 `ScrollBarAlwaysOff` 下得到垂直范围 `0..1682`，wheel 事件使 value 从 `0` 变为 `60`，支持滚轮能力保留的判断。

## Verification

- hidden-scrollbar 单项：exit code `0`，`1 passed, 35 deselected in 0.49s`。
- renderer 全文件：exit code `0`，`36 passed in 2.19s`。
- CR-022 七文件目标集：exit code `0`，`202 passed in 5.37s`。
- SDK/MMS/UI 邻近回归：exit code `0`，`586 passed in 14.08s`。
- scoped Ruff：exit code `0`，`All checks passed!`。
- `UV_CACHE_DIR=/tmp/crawler4j-uv-cache uv lock --check`：exit code `0`，`Resolved 78 packages`。
- `git diff --check`：exit code `0`，无输出。
- 本轮未重复全量 unit；其 13 项既有环境基线失败采用输入包证据，不用于 changed-scope 通过结论。上述独立 pytest 命令为 `0 failed`、`0 errors`、`0 skipped`。

## Gate

`pending_human_confirmation`

本结论只表示独立 reviewer 通过，不将 work item 标记为 done，也不替代人工确认与最终 gate。
