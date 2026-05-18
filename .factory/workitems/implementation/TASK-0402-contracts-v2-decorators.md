# TASK-0402 建立 Contracts v2 装饰器契约

- 状态：DONE
- 负责人：Codex
- 优先级：P0
- 估算：1.0 人/天
- 关联 ID：`TASK-0402`, `TASK-0400`, `REQ-0400`, `API-012`, `TC-0400-001`

## 目标

- 在 `crawler4j-contracts` 中提供 `@interface/@component/@workflow/@page_action/@data_table/@data_view`。
- 装饰器只附加元数据，不实例化业务对象。
- 0.4.x 根导出面不再暴露 `TaskSpec` / `WorkflowSpec` / `EnvSelectorSpec`。

## 完成记录

- 已新增 `decorators.py`、更新根导出与回归测试。
- 定向测试纳入第一批 0.4.0 质量门。
