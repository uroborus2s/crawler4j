# TASK-0409 建立 page action runtime

- 状态：TODO
- 负责人：待分配
- 优先级：P0
- 估算：1.5 人/天
- 关联 ID：`TASK-0409`, `TASK-0400`, `REQ-0400`, `API-012`, `TC-0400-008`

## 目标

- task 目录下的正式运行单元改为 `@page_action` 纯函数。
- Core 运行链按 workflow 调用 page action。
- 清理旧 `TASK + execute(ctx)` 运行入口。
