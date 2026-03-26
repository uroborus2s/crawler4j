# BUG-002 `ctrip labor_workflow` 因旧依赖缺失退化为登录流程

- 状态：DONE
- 类型：BUG
- 优先级：P0
- 估算：2.0 人/天
- 关联 ID：`BUG-002`, `REQ-002`, `TASK-003`
- 发现日期：2026-03-26

## 问题

外部 `ctrip` 模块中的 labor 相关 task script 曾在运行时导入：

- `src.automation.workflows.labor_claim_task`
- `src.automation.workflows.ctrip_search`
- `src.automation.workflows.labor_login`
- `src.automation.workflows.labor_submit`

这些路径在当前仓库中一度不存在，导致 `labor_workflow` 会直接退化为 `login_workflow`。

## 证据

- 已恢复 `src.automation.workflows.*`、`src.core.models.*` 与 `src.utils.hotel_matcher` 的兼容路径
- 打包模块隔离 smoke 现已确认：`labor_workflow` 不再因为缺少 `src.automation` 而退化

## 影响

- 已消除“导入缺失即退化”的硬阻塞
- 真实站点 E2E 仍需后续独立验证

## 验收标准

- `labor_workflow` 不再依赖旧路径
- 不再通过 fallback 才能完成流程
- 增加相应验证
