# CR-022 Shared Form Columns Review Fix Report

- Feedback: `CR-022-R2-I1`
- Severity: Important
- Status: `ready_for_independent_rereview`

共享网格把原本只分隔逻辑 field container 的声明 gap 扩展成 label/input 内部间距。超大合法 gap 在降为单列后仍使 input 超出 viewport。临时统一 cap 会反过来改写宽屏合法中等 gap，因此最终修复把两类边界分开：label/input 内部沿用 `6px`，声明 gap 仅作用于后续逻辑列 leading margin。纵向 gap、列数容量、窗口边界、schema 和业务协议不变。

新增回归既通过 input 到 scroll viewport 的坐标映射检查字段可访问，也用宽屏 `gap=100` 的 content margin 与 geometry 检查声明值未被统一 cap。

验证结果见 `.factory/workitems/CR-022/evidence/shared-form-columns-review-fix-verification.md`。
