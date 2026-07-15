# CR-022 Hidden Form Scrollbar Implementer Report

- Work item: `CR-022`
- Increment: renderer hidden Form scrollbars
- Status: `ready_for_independent_review`
- Date: 2026-07-15

## Outcome

CRUD 长 Form 保留原有内部滚动容器，但水平和垂直滚动条策略统一为 `ScrollBarAlwaysOff`。长内容仍具有有效滚动范围，并通过 Page Down 与程序化滚动回归验证；按钮区仍固定在滚动容器外。

## Implementation

- `ManagedPageRenderer._build_crud_form_dialog()` 只把垂直策略从 `ScrollBarAsNeeded` 改为 `ScrollBarAlwaysOff`。
- 没有新增自定义滚动组件、样式表、schema 或配置项。
- 保留 `QScrollArea`、`widgetResizable=True`、无水平滚动、表单网格、屏幕约束和固定按钮布局。
- renderer 测试断言隐藏策略与真实滚动能力，并固定一个既有用例的屏幕几何以避免显示器相关漂移。

## Verification

- TDD RED：`1 failed`，准确暴露垂直策略仍为 `ScrollBarAsNeeded`。
- TDD GREEN：目标用例 `1 passed`。
- renderer：`36 passed`。
- CR-022 七文件：`202 passed`。
- SDK/MMS/UI：`586 passed`。
- Ruff、lock、docs、diff check 均通过。
- 全量 unit 为 `1234 passed` 加 13 项已登记的范围外环境基线失败。

详见 `.factory/workitems/CR-022/evidence/hidden-form-scrollbar-final-verification.md`。

## Scope

- Contracts / SDK / schema / versions: unchanged.
- Consumer modules: unchanged.
- Business specialization: none.
- Publish / push: none.
