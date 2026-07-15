# CR-022 Shared Form Columns Review-fix Verification

## Review finding RED

```bash
UV_CACHE_DIR=/tmp/crawler4j-uv-cache QT_QPA_PLATFORM=offscreen \
uv run pytest -q -p no:cacheprovider \
  packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py \
  -k 'layout_clamps_large_valid_gap'
```

结果：exit code `1`，`1 failed, 34 deselected`；`input_right=1017`，viewport width `654`。

## Review fix GREEN

相同命令：exit code `0`，`1 passed, 34 deselected in 0.51s`。

## Contract-preservation RED/GREEN

新增宽屏三列 `gap=100` 回归后，统一 `24px` cap 实现结果：exit code `1`，`1 failed, 35 deselected`，实际 `grid.horizontalSpacing()=24`。

分离内部与逻辑列间距后，相同用例：exit code `0`，`1 passed, 35 deselected in 0.59s`；grid physical spacing 为 `0`，后续逻辑列 label left margin 为 `100`，label/input 内部 right margin 为 `6`，geometry 间距断言通过。

## Regression

- renderer 全文件：exit code `0`，`36 passed in 1.87s`。
- CR-022 七文件：exit code `0`，`202 passed in 5.01s`。
- SDK/MMS/UI 邻近回归：exit code `0`，`586 passed in 13.87s`。
- scoped Ruff：exit code `0`，`All checks passed!`。

## Result

`passed`。两项 review regression 已完成 RED/GREEN，最终宽回归通过；等待独立复评和全量 gate。
