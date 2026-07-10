# TASK-038 验证证据

- 日期：2026-07-10
- 状态：`ready_for_review`

## RED

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider -q packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py::test_managed_page_renderer_row_button_opens_page_with_clicked_row_params
```

结果：`1 failed`。失败断言为 `opened_pages == []`，证明当前行按钮误走 `ui_action` 而未打开目标页。

## GREEN 与邻近回归

- 同一目标命令：`1 passed in 0.47s`。
- renderer + SkyDataTable + Hosted UI schema：`73 passed in 1.36s`。
- 目标 Ruff：`All checks passed!`。
- `git diff --check`：通过。

邻近回归包含未声明 `type` 的自定义 `@ui_action` 行按钮、CRUD 行按钮、SkyDataTable 当前行信号，以及整行 `row_action` 的有参/无参导航。

## 未运行项

- 未运行全量 unit：改动只触及 renderer 单一分发分支，且当前工作区存在独立发布任务的未提交版本漂移；以 renderer 整文件和相邻表格/契约测试作为本任务门禁。

