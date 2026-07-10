# Task 2 Review Input

## 范围

- Task：Core Renderer 多选批量编辑
- Brief：`.factory/workitems/CR-018/task-briefs/task-2-core-renderer.md`
- Requirement：`.factory/workitems/CR-018/brief.md`
- Upstream：task 1 Contracts / SDK 已通过 Spec + Quality Review。

## Diff

- `managed_page_renderer.py`：选择模式透传、bulk toolbar、按钮状态、批量同步 / 异步调用、单条多选防护与点击行语义。
- `data_table.py`：`request_refresh()` 发起查询前清除当前选择。
- 两个目标测试文件：按钮 / payload / 失败 / async / 行内动作 / 刷新分页回归。

## Evidence

- `.factory/workitems/CR-018/evidence/task-2.md`
- RED：`5 failed, 33 passed`。
- GREEN：`38 passed`。
- 目标 ruff 与 `git diff --check` 通过。

## Spec Review 重点

- Core params 是否严格只含 `primary_keys` 与 `payload`，并保持类型、顺序和去重。
- 缺主键、失败、取消、成功各分支是否满足选择 / 刷新契约。
- 0 / 1 / 多选时 bulk 与单条按钮状态是否正确。
- `render=row_actions`、显式关闭 bulk、点击行 edit/delete、同步 / 异步路径是否符合来源要求。
- 手动刷新、搜索 / 筛选 / 排序和翻页是否不跨结果集保留选择。

## N/A

- 数据库与业务模块：N/A，Core 只调用模块 handler。
- 正式 docs / memory：由 task 3 统一同步。
