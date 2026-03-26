# TASK-003 恢复 `ctrip labor_workflow` 的当前运行时实现

- 状态：DONE
- 类型：TASK
- 优先级：P0
- 估算：2.0 人/天
- 关联 ID：`TASK-003`, `BUG-002`, `REQ-002`

## 目标

- 恢复外部 `ctrip` 模块当前仍依赖的旧自动化兼容路径
- 让 `labor_workflow` 不再因为缺失 `src.automation.*` 而 fallback 到登录流程

## 验收标准

- `src.automation.*` 兼容路径已恢复到当前仓库
- `labor_workflow` 不依赖 fallback 才能运行
- 补充对应测试或导入级验证
