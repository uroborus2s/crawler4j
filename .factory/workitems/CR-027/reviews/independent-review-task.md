# TASK-049 独立评审输入

- behavior_id: SB-REVIEW
- workflow_id: review-workflow
- write_policy: state_or_gate_write
- work_item_id: CR-027
- task_card_id: TASK-049
- current_gate: needs_independent_review
- dispatch_id: CR027-TASK049-auto-20260906-reviewer
- reviewer_type: independent_subagent
- model: gpt-5.6-terra
- reasoning_effort: high
- fork_turns: none
- human_confirmation_required: false

只读范围：本目录父工作项 brief、task brief、evidence/auto-fingerprint.md；本次 5 个 Python 文件及必要直接调用方；docs/02-user-guide/usage.md 与 .factory/memory 中 CR-027 状态；仅限这些路径的 git diff。源码写集见 TASK-049.md。
禁止写入任何文件、修改 Git、访问真实浏览器/代理/账号/数据库或外部服务。不继承实施者会话，不仅凭报告作结论。

审查 Spec 与 Quality：默认模式是否到达最终创建/主动刷新；自动占位/保存值是否不再误判；明确自定义值、版本与必要结构检查是否保留；手动定位修复与代理流程是否受影响；测试是否实际覆盖这些语义。
审查需要特别确认：全文件 code shape exit 1 来自已有 fixtures/lambda，本轮无新增；是否接受基线例外。真实运行/203 修复未验证，是否接受这一本地变更验证边界。

请返回中文 findings（路径/行号/severity）、approved 或 changes_requested、独立性说明、五维评分、N/A/基线例外接受或拒绝以及 human_confirmation_required。不要改实现或 ledger。
