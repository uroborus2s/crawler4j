# CR-018 / TASK-036 Task 2 验证证据

- Actor: Codex implementer
- Date: 2026-07-10 (Asia/Shanghai)
- Status: passed
- Claim: Core Renderer 支持 DataTable 多选批量编辑，且翻页/刷新不保留旧选择。

## RED

命令：

```bash
QT_QPA_PLATFORM=offscreen uv run pytest packages/crawler4j/tests/unit/test_ui/test_data_table.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py -q -p no:cacheprovider
```

首次沙箱内执行因 uv 缓存路径权限失败（exit 2），随后按相同命令在获准环境重跑。真实行为 RED：exit 1，`5 failed, 33 passed in 1.25s`。

预期与实际失败原因一致：

- `request_refresh()` 未清除选择。
- Core 将 DataTable 选择模式固定为 `single`。
- bulk toolbar/handler 尚不存在。
- 多选下行内 CRUD 未显式使用点击行。

## GREEN

最终新鲜验证命令与结果：

```bash
QT_QPA_PLATFORM=offscreen uv run pytest packages/crawler4j/tests/unit/test_ui/test_data_table.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py -q -p no:cacheprovider
```

- exit code: 0
- result: `38 passed in 1.14s`
- failures: 0
- errors: 0
- skipped: 0

```bash
uv run ruff check packages/crawler4j/src/core/mms/ui/managed_page_renderer.py packages/crawler4j/src/ui/components/data_table.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py packages/crawler4j/tests/unit/test_ui/test_data_table.py
```

- exit code: 0
- result: `All checks passed!`

```bash
git diff --check
```

- exit code: 0
- output: empty

## 验收核对

1. DataTable 顶层 `selection_mode` 透传；省略保持 `single`：通过。
2. handler 存在时默认展示“批量编辑”，显式 `False` 隐藏，`render=row_actions` 不隐藏：通过。
3. bulk 按 0/1+ 行禁用/启用；单条编辑/删除仅恰好 1 行启用，handler 防御多选：通过。
4. bulk 表单使用 `form.update_columns`、`row=None`；空白文本为 `None`，payload 字段名原样保留：通过。
5. 成功清选择并触发一次刷新；失败保留选择、不刷新、显示原始异常文本：通过。
6. 已有 event loop 从同步入口调度异步路径；异步表单仅走 `open_dialog_async`，`QDialog.exec` 被测试设为失败哨兵且未调用：通过。
7. 多选下行内编辑/删除使用点击行的原始主键：通过。
8. 手动 `request_refresh` 与翻页均清除旧选择：通过。

批量 action 边界测试还验证：Core 仅传 `{"primary_keys": [...], "payload": {...}}`；主键保留 `int`/`str` 原类型并按 `selected_rows()` 顺序去重；任一选中行缺主键时调用次数为 0。

## 偏离与风险

- 未运行超出 task brief 的全仓测试；已完整执行 brief 指定的定向测试、Ruff 与 diff 检查。
- 无数据库改动，无新增依赖。
