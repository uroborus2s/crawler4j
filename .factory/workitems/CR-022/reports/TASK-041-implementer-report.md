# TASK-041 Implementer Report

- Work item: `CR-022`
- Task: `TASK-041`
- Status: `review_approved_validation_complete`
- Date: 2026-07-15

## Outcome

已在 Contracts、SDK、Core Hosted UI runtime、renderer、测试和开发文档内完成公共字段 change 与安全 Form reset。未修改消费模块、版本号、发布配置或远端状态。

最终字段声明为 `on_change={"type":"ui_action","name":"<handler>"}`；handler 固定接收 `(context, event: HostedFieldChangeEvent)`。Form scope 提供 opaque `form_id`、mode 和当前 values；standalone scope 不提供 handle。模块主动调用 `context.tools.call("ui.form.reset", form_id=..., initial_values=...)`，Core 只重建整张 Form 的 current/initial values 并清 dirty/validation。

## Implementation

- Contracts：新增 `InputSchema`、`SelectSchema`、公共 field event/action/scope/reset 类型并扩展 DataTable form-compatible columns。
- SDK：scanner 校验 action 引用、确定 `(context, event)` 签名和 `HostedFieldChangeEvent` 注解。
- Core：新增 Form controller、不可预测 handle registry、module/page/session/form/TTL/revision 绑定和稳定错误。
- Runtime：`ui.form.reset` 只注册到 Hosted UI action surface；字段事件使用隔离 action session。
- Renderer：独立 Input/Select 与 CRUD 字段共享事件分发；create 使用 exact column default，update 优先 row；reset 阻断信号递归；长 Form 支持默认单列或声明式 1–3 列逐行布局、窄屏降列、内容滚动和固定操作区。
- Contracts layout：`crud.form.layout={"columns":1|2|3,"gap":<可选非负整数>}`，严格拒绝 bool、非整数、越界列数和负 gap。
- Review fixes：响应式计算使用 renderer 所在屏幕而非固定主屏；合法超大 gap 在 Contracts 中精确保留，在 Qt renderer 中按当前屏幕几何收敛，避免整数溢出并保持降列语义。
- Docs：同步设计、API baseline、开发者指南、导航与 release change record；明确 Contracts `0.4.3` / SDK `0.4.4` 不变和本地 editable 联调命令。

## Security and concurrency

- Handle 使用随机 token，绑定 module/page/renderer session/具体 Form，默认 TTL 五分钟，关闭即注销。
- 伪造、过期、关闭、跨 module/page/session 均返回 `FORM_HANDLE_REJECTED`。
- 非 Form reset 返回 `FORM_SCOPE_UNAVAILABLE`；未知字段返回 `FORM_INITIAL_VALUES_INVALID`。
- 每个 change 增加 revision；旧 handler reset 返回 `FORM_EVENT_STALE` 并由 renderer 静默丢弃。
- 不把 dialog/widget/controller 放入事件、context runtime 或日志；不记录完整 form values。

## Verification available to reviewer

- Contracts/SDK 首批 RED：新类型/normalize/scanner 测试出现预期失败，随后转绿。
- Core registry 首批 RED：`hosted_form` 模块缺失导致预期 collection error，随后转绿。
- Renderer RED：create default、滚动容器、form/standalone event、failure 和 rapid change 共 6 个预期失败，随后转绿。
- 当前七个目标文件：`199 passed in 4.50s`；独立 reviewer 同集复跑 `199 passed in 4.45s`。
- 目标 Ruff：`All checks passed!`。
- 独立 review 后最终 gate 已执行并记录于 `.factory/workitems/CR-022/evidence/final-verification.md`。

## Consumer integration evidence

消费模块维护方在不修改 Core 的独立工作区中，使用本地 editable Contracts/SDK 完成最终协议联调：

- 页面 schema 使用 `crud.form.layout={"columns":3,"gap":12}`，manifest lock 保留该结构，`crawler4j check full` 通过。
- 模块按 `HostedFieldChangeEvent` 接收字段事件，并由 handler 主动调用 `ui.form.reset`；其模块定向结果为 `262 passed`。
- 消费侧只读复核本仓七个 Core 定向文件为 `197 passed`，Contracts schema + renderer 子集为 `81 passed`。

这些是下游联调补充证据，不替代本 work item 的独立 review 与最终 Core gate；本任务未修改消费模块。

## Known boundaries

- 不发布 Contracts / SDK，不改变 `0.4.3` / `0.4.4`。
- 不执行消费模块 E2E、真机验证、push 或发布。
- `ui.form.reset` 不提交，不调用 CRUD handler，不解释 handler 返回 effect。
