# CR-022 Hosted UI 公共表单字段 change 事件

- 状态：IMPLEMENTED_VALIDATION_PENDING
- 需求事实源：`.factory/workitems/CR-022/brief.md`
- 范围：Contracts、SDK、Core MMS、Hosted UI renderer、对应测试与必要开发文档
- 排除：消费模块、设备/平台模板、业务默认值与发布

本变更为公共 Hosted UI 能力：字段声明可选 `on_change`，Core 为 Form 场景提供安全短生命周期 handle，模块可主动调用通用 `ui.form.reset`，renderer 负责通用 reset 状态语义和 latest-wins 并发保护。

消费侧联调追加的公共 renderer 要求已纳入：create Form 使用字段 `default`、update Form 优先 row 实际值，长 Form 内容区滚动且按钮保持可见；`crud.form.layout` 可声明 1–3 列与可选 gap，窄屏自动降列。
