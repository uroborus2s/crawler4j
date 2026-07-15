# CR-022 Shared Form Columns TDD Evidence

## Root cause

- 症状：三列 Form 中，同一逻辑列的标签冒号和输入框左边缘跨行交错。
- 直接原因：外层 `QGridLayout` 的每个 item 是一个独立 `field_container`，其内部各自创建 `QFormLayout`。
- 根源原因：label/input 宽度计算被隔离在字段级 layout 中，同一逻辑列没有共享的 label/input 物理列。
- 修复点：外层 grid 为每个逻辑列直接分配 label/input 两个物理列；label 右对齐，input 列 stretch。
- 防回归：结构、alignment/stretch、跨行 geometry、单列和 35 字段测试。
- 兜底/降级：否。

## RED

```bash
UV_CACHE_DIR=/tmp/crawler4j-uv-cache QT_QPA_PLATFORM=offscreen \
uv run pytest -q -p no:cacheprovider \
  packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py \
  -k 'crud_form_without_layout or crud_form_grid_uses_shared or crud_form_shared_columns or crud_form_many_fields'
```

真实结果：`4 failed, 31 deselected`。旧单列 6 字段只有 6 个 grid item，35 字段只有 35 个 item；共享 input 物理列不存在。

## GREEN

- 同一 4 项：`4 passed, 31 deselected in 0.79s`。
- renderer 全文件：`35 passed in 1.84s`。
- CR-022 七文件目标集：`201 passed in 4.89s`。
- 目标 Ruff：`All checks passed!`。

## Independent review regression

独立 reviewer 发现，共享物理列使声明式超大 gap 同时进入 label/input 内部间距；响应式降为单列后 input 被挤出关闭横向滚动的 viewport。

- 补充 RED：`1 failed, 34 deselected`，`input_right=1017 > viewport.width=654`。
- 修复：grid 物理列间距归零；每个 label 用 `6px` 右侧 content margin 表达内部 label/input spacing，仅后续逻辑列用声明 gap 作为左侧 content margin。这样单列不携带无意义的逻辑列 gap，三列仍精确保留声明值。
- 补充 GREEN：`1 passed, 34 deselected in 0.51s`。
- 合法中等 gap 契约 RED：统一 `24px` cap 被回归测试拒绝，`1 failed, 35 deselected`。
- 合法中等 gap 契约 GREEN：`gap=100` 在宽屏三列中保留为后续逻辑列左 margin，内部 spacing 为 `6px`，`1 passed, 35 deselected in 0.59s`。
- 最终 renderer：`36 passed in 1.87s`。
- 最终七文件目标集：`202 passed in 5.01s`。
- 最终 SDK/MMS/UI 邻近回归：`586 passed in 13.87s`。
- 修复后目标 Ruff：`All checks passed!`。

根因见 `shared-form-columns-large-gap-root-cause.md`。

## Consumer read-only evidence

消费侧报告：renderer `35 passed`、CR-022 七文件 `201 passed`、scoped Ruff 通过；消费模块 `crawler4j check full` 和页面 `9 tests` 通过，schema 无需变化。该证据不替代本仓 gate，且本任务未修改消费模块。

## Scope

实现只修改 Core renderer 和 renderer 测试；未修改 Contracts、SDK、消费模块或 schema。
