# CR-022 Shared Form Columns Review Response

## Fixed

### CR-022-R2-I1

Fixed. 共享 grid 现在分别表达两类间距：label/input 使用原有 `6px` 内部间距，声明 gap 仅放在第二、第三逻辑列的 leading margin。合法超大 gap 降为单列后不再把 input 推离 viewport；宽屏三列仍保留合法 `gap=100`，没有统一截断声明值。纵向 spacing、响应式列容量、dialog 尺寸和 Contracts schema 不变。

Verified:

- geometry RED：`1 failed, 34 deselected`，`input_right=1017 > viewport.width=654`。
- geometry GREEN：`1 passed, 34 deselected in 0.51s`。
- 中等 gap cap RED：`1 failed, 35 deselected`，旧临时修复返回 `grid.horizontalSpacing()=24`。
- 中等 gap GREEN：`1 passed, 35 deselected in 0.59s`；后续逻辑列 margin `100`，内部 margin `6`。
- 最终 renderer：`36 passed in 1.87s`。
- 最终 CR-022 七文件：`202 passed in 5.01s`。
- 最终 SDK/MMS/UI 邻近回归：`586 passed in 13.87s`。
- scoped Ruff：`All checks passed!`。

Evidence:

- `.factory/workitems/CR-022/evidence/shared-form-columns-large-gap-root-cause.md`
- `.factory/workitems/CR-022/evidence/shared-form-columns-review-fix-verification.md`
