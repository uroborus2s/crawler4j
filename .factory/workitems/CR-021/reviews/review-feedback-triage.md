# Review Feedback Triage

## CR-021-FB-001

- 反馈来源：human
- 原文：当前绑定 IP 池的也没展示。先找到这个问题的真正的原因
- severity：Critical
- 反馈要求：撤回“只限制当前池导致缺失”的结论，解释同池条目仍不显示的真实条件。
- 是否清楚：yes
- 是否技术正确：yes
- 证据：同池两个可用未过期条目的聚焦测试通过；弹窗另有停用/过期过滤。
- 处理决定：Fixed（更正调查结论，不修改产品代码）。
- 验证命令：`uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_edit_env_dialog.py::test_edit_env_dialog_applies_selected_ip_with_explicit_button -q`
- 真实结果：`1 passed in 0.49s`
