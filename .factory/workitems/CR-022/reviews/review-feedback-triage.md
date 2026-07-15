# CR-022 Review Feedback Triage

## Feedback Item CR-022-RF-001

- 反馈来源：task review
- 原文：CRUD Form 响应式布局使用 `QApplication.primaryScreen()`，多显示器下不能保证按 renderer/dialog 所在屏幕降列或限制窗口边界。
- 文件：`packages/crawler4j/src/core/mms/ui/managed_page_renderer.py`
- severity：Important

## 理解

- 反馈要求：使用当前 renderer 所在屏幕的可用区域计算有效列数与对话框宽高，只有无法取得时才回退主屏，并补非主屏回归。
- 是否清楚：yes
- 需要澄清的问题：无

## 技术核实

- 是否技术正确：yes
- 证据：当前实现直接读取 `QApplication.primaryScreen()`；在主屏宽、renderer 位于窄副屏时会高估列容量与最大宽度，违反 AC-022-013/014 和 NFR-022-RESP。
- 是否会破坏现有功能：no；单屏结果不变，改动只修正屏幕选择来源。
- 是否与用户决策冲突：no
- 是否违反 YAGNI：no；用户明确要求窄屏降列且窗口不超出所在屏幕。
- 当前实现是否有历史或兼容原因：无；这是本次新增布局代码。

## 处理决定

- Fixed：改用 `self.screen()`，仅在无法取得当前屏幕时回退 `QApplication.primaryScreen()`；测试同时提供宽主屏与窄 renderer 屏，证明不会误用主屏。

## 验证

- 验证命令与真实结果：见 `../evidence/review-fix-verification.md`。

## Feedback Item CR-022-RF-002

- 反馈来源：task review
- 原文：Contracts 接受任意非负 Python `int` gap，但 Qt spacing 仅接受 C++ int；合法超大 gap 会在打开 Form 时抛 `OverflowError`。
- 文件：`packages/crawler4j/src/core/mms/ui/managed_page_renderer.py`
- severity：Important

## 理解

- 反馈要求：不收窄已批准的 schema 契约；renderer 将声明 gap 收敛到当前屏幕可用几何内的 Qt 安全 spacing，并补合法超大 gap 回归。
- 是否清楚：yes
- 需要澄清的问题：无

## 技术核实

- 是否技术正确：yes
- 证据：`QGridLayout.setHorizontalSpacing` / `setVerticalSpacing` 接收 Qt `int`，而 Contracts 的非负 Python `int` 无上界；直接传入 `2147483648` 会溢出。
- 是否会破坏现有功能：no；常规 gap 原样保留，仅对超过当前屏幕可用尺寸、无法实际展示的值做响应式收敛。
- 是否与用户决策冲突：no；保留任意非负整数 schema，并符合屏幕边界要求。
- 是否违反 YAGNI：no；反馈提供了合法输入的确定崩溃路径。
- 当前实现是否有历史或兼容原因：无；这是本次新增布局代码。

## 处理决定

- Fixed：Contracts 继续精确保留合法 gap；renderer 在获得当前屏幕几何后，把实际 spacing 限制到可用宽高范围，避免 Qt int 溢出并对不可展示的大间距降列。

## 验证

- 验证命令与真实结果：见 `../evidence/review-fix-verification.md`。

## Feedback Item CR-022-RF-003

- 反馈来源：task review
- 原文：大 gap Contracts 回归遗漏 `crud.primary_key`，先被既有 schema gate 拒绝，未执行目标断言。
- 文件：`packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py`
- severity：Minor

## 技术核实

- 是否技术正确：yes
- 证据：独立 reviewer 七文件复跑为 `1 failed, 198 passed`，失败为 `crud.primary_key` 非法；测试 fixture 未满足既有 CRUD 必填契约。
- 是否会破坏现有功能：no
- 是否与用户决策冲突：no
- 是否违反 YAGNI：no

## 处理决定

- Fixed：补入合法 `primary_key="account_id"`，使测试实际到达并断言超大非负 gap 精确保留。

## 验证

- 验证命令与真实结果：见 `../evidence/review-fix-verification.md`。

## Feedback Item CR-022-RF-004

- 反馈来源：task review
- 原文：`independent-review-task.md` 的范围文字仍为 `AC-022-001..011`，未同步最终扩展到 `AC-022-014`。
- 文件：`.factory/workitems/CR-022/reviews/independent-review-task.md`
- severity：Minor

## 技术核实

- 是否技术正确：yes；实际 review 已覆盖新增条目，但恢复文档范围文字滞后。
- 是否会破坏现有功能：no
- 是否与用户决策冲突：no
- 是否违反 YAGNI：no

## 处理决定

- Fixed：把任务范围同步为 `AC-022-001..014`。

## 验证

- 文档 diff 与 `git diff --check` 纳入最终 gate。
