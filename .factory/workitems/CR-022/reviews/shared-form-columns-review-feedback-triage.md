# CR-022 Shared Form Columns Review Feedback Triage

## Feedback Item

- ID: `CR-022-R2-I1`
- 反馈来源: task review
- 原文: 共享物理列后超大合法 gap 会把 label/input 内部间距扩展到接近窗口宽度，输入控件移出无横向滚动的 viewport。
- 文件: `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py`
- severity: Important

## 理解

- 反馈要求: 保留 Contracts 的合法 gap 契约与响应式降列，同时确保 input 不被共享 label/input spacing 挤出 viewport；补真实 geometry 回归。
- 是否清楚: yes
- 需要澄清的问题: 无。

## 技术核实

- 是否技术正确: yes
- 证据: 新增 geometry 断言稳定得到 `input_right=1017 > viewport.width=654`；根因报告见 `evidence/shared-form-columns-large-gap-root-cause.md`。
- 是否会破坏现有功能: 当前实现会破坏超大 gap 下的表单可访问性；统一 cap 又会破坏宽屏合法中等 gap，最终修复必须分开表达内部与逻辑列间距。
- 是否与用户决策冲突: no；用户要求窗口不超屏且字段完整可访问。
- 是否违反 YAGNI: no；这是已允许输入和已有 AC 的直接回归。
- 当前实现是否有历史或兼容原因: 原 `form_gap` 只作用于逻辑 field container 之间；共享物理列后语义发生了非预期扩展。

## 处理决定

- Fixed：grid physical spacing 设为 `0`；label 右 margin 固定 `6px` 表达内部 spacing，逻辑列 2/3 的 label 左 margin 使用声明 gap。纵向 spacing、响应式容量和 schema 不变。

## 验证

- RED：`1 failed, 34 deselected`，输入右边界超出 viewport。
- 复评 RED：统一 `24px` cap 不能保留宽屏合法 `gap=100`，`1 failed, 35 deselected`。
- GREEN：修复后记录于 `evidence/shared-form-columns-review-fix-verification.md`。
