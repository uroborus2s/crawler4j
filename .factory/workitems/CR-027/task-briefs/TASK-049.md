# TASK-049 使用 VirtualBrowser 自动匹配模式创建环境

- 状态：`ready_for_commit`
- 父工作项：`CR-027`
- 允许修改：
  - `packages/crawler4j/src/core/rem/virtualbrowser_fingerprint.py`
  - `packages/crawler4j/src/core/rem/provider.py`（仅 VirtualBrowser 创建、共享随机流程与对应指纹校验）
  - `packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_fingerprint.py`
  - `packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py`
  - `packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py`
  - `docs/02-user-guide/usage.md`（仅新建环境模式说明）
  - `.factory/workitems/CR-027/**`
  - `.factory/memory/agent-session.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/tasks.summary.md`
  - `.factory/memory/review-ledger.jsonl`
- 禁止：数据库或公共接口变更、其他 Provider 修改、远端操作。

## 验收

以父工作项最新验收为准；旧固定上海时区要求已由用户最新指令取代。

## 执行路由

- behavior_id: SB-EXECUTE
- workflow_id: execution-workflow
- write_policy: source_or_test_write
- work_item_id: CR-027
- task_card_id: TASK-049
- wbs_id: TASK-049
- task_complexity: standard
- risk_level: medium
- execution_authorized: true
- current_gate: create_exact_local_commit
- execution_model: gpt-5.6-terra
- dispatch_role: worker
- dispatch_required: true
- dispatch_mode: subagent
- requested_reasoning_effort: medium
- fork_turns: none
- route_reason: 用户明确授权局部默认配置变更，需同步创建/校验路径，无生产或持久环境操作。
- code_shape: 不新增嵌套命名函数，不新增无独立职责的单调用点 helper；保留现有测试栈。
