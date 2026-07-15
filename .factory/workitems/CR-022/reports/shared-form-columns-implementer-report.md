# CR-022 Shared Form Columns Implementer Report

- Work item: `CR-022`
- Increment: renderer shared label/input columns
- Status: `ready_for_independent_review`
- Date: 2026-07-15

## Outcome

CRUD Form 的每个逻辑列现在由同一个外层 `QGridLayout` 提供共享的 label/input 物理列。标签以全角冒号结尾并右对齐，输入控件横向扩展，因此同一逻辑列跨行共享标签右边缘和输入左边缘。

本增量不改变 Contracts schema、SDK、Core Form event/reset 协议、版本号或消费模块。既有 `crud.form.layout={"columns": 1|2|3, "gap": <non-negative int>}` 契约保持不变。

## Implementation

- 删除 CRUD Form 中每字段独立的 `QWidget + QFormLayout` 容器。
- 每个逻辑列映射为 `label_column=logical_column*2` 与 `input_column=label_column+1`。
- label 使用 `AlignRight | AlignVCenter`；input 物理列 stretch 为 `1`，输入 widget 横向 policy 为 `Expanding`。
- 字段仍按原顺序 row-major 填充；单列仍为一组共享 label/input 列。
- 滚动区、固定按钮行、屏幕边界、create default、update row、change/reset 和 submit 路径均未改变。
- 独立 review 发现超大合法 gap 会被误用为 label/input 内部水平间距；补充 geometry RED 后，把两类间距分开表达：label/input 固定沿用原 `6px` 内部 spacing，声明 gap 只作为后续逻辑列的 leading margin。单列不会被无意义 gap 挤出 viewport，宽屏三列仍保留合法 `gap=100`。

## TDD evidence

- RED：4 项共享列/单列/35 字段结构测试为 `4 failed, 31 deselected`。
- GREEN：相同子集 `4 passed, 31 deselected in 0.79s`。
- renderer 全文件：`35 passed in 1.84s`。
- CR-022 七文件目标集：`201 passed in 4.89s`。
- scoped Ruff：`All checks passed!`。
- review-fix GREEN：超大 gap geometry `1 passed, 34 deselected`；合法中等 gap `1 passed, 35 deselected`；最终 renderer `36 passed`、七文件 `202 passed`、SDK/MMS/UI `586 passed`、scoped Ruff 通过。

详见 `.factory/workitems/CR-022/evidence/shared-form-columns-tdd.md`。

## Consumer read-only evidence

消费侧只读复核报告：renderer `35 passed`、CR-022 七文件 `201 passed`、scoped Ruff 通过；消费模块 `crawler4j check full` 与页面 `9 tests` 通过，schema 无需变化。该结果只作为下游兼容补充证据，不替代本仓独立 review 和最终 gate；本增量未修改消费模块。

## Scope

- 产品代码仅修改 `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py`。
- 测试仅修改对应 renderer unit test。
- 同步 CR-022 requirements/plan/evidence、正式 Hosted UI 文档、release note 和 memory。
- 未修改 Contracts、SDK、`ctrip_crawler`、版本、lock、发布或远端状态。
