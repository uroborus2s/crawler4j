# CR-022 Shared Form Columns Large-gap Root Cause

- Work item: `CR-022`
- Source: incremental independent review
- Affected path: CRUD Form renderer shared label/input grid
- Status: `root_cause_found`

## Symptom and reproduction

合法超大 `crud.form.layout.gap` 在响应式降为单逻辑列后，首个输入控件仍被放到 viewport 之外，且横向滚动条固定关闭，用户无法访问输入控件。

失败测试：

```bash
UV_CACHE_DIR=/tmp/crawler4j-uv-cache QT_QPA_PLATFORM=offscreen \
uv run pytest -q -p no:cacheprovider \
  packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py \
  -k 'layout_clamps_large_valid_gap'
```

真实结果：`1 failed, 34 deselected`；`input_right=1017`，`scroll.viewport().width()=654`。

## Investigation

- 最近变化：CRUD Form 从每字段独立 `QFormLayout` 改为外层共享 label/input 物理列。
- 旧结构：外层 `QGridLayout.horizontalSpacing` 只位于不同 field container 之间；单逻辑列没有横向 container 间距。container 内 label/input 使用固定 `6px` spacing。
- 新结构：同一个 `QGridLayout.horizontalSpacing` 同时位于 label 与 input 两个物理列之间。
- 数据流：Contracts 精确保留合法 gap -> renderer 按屏幕 clamp 为 `form_gap` -> column capacity 降为一列 -> `setHorizontalSpacing(form_gap)` 仍把大 gap 插入 label/input 之间 -> grid 最小宽度超过 viewport -> horizontal scrollbar 关闭使 input 不可访问。

## Root cause

- 直接原因：声明式逻辑列间 gap 被错误复用于共享 label/input 的内部间距。
- 根源原因：布局从“每逻辑列一个 container”改成“每逻辑列两个物理列”后，未重新区分逻辑列 gap 与字段内部 label/input spacing。
- 最小假设验证：新增输入 geometry 必须落在 scroll viewport 内的断言后，旧实现稳定失败且数值直接证明越界。

## Fix boundary

- 修复点：共享 grid 物理 spacing 设为零；label 右 content margin 沿用 `6px` 内部间距，只有后续逻辑列 label 的左 content margin 使用声明 gap。声明 gap 继续用于纵向 spacing、逻辑列容量与 dialog 尺寸计算。
- 防回归：超大合法 gap 在降为单列后，首个输入控件左右边界都必须位于 viewport。
- 不改变 Contracts schema、normalize、版本、消费模块或业务语义。
