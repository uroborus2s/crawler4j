# Hosted UI 公共表单字段 change 事件与安全 Form Handle 需求简报

- 项目：crawler4j
- Work item：`CR-022`
- 状态：`validation_complete`
- 来源：用户明确实现指令
- 场景：`add_requirement`
- 文档版本：`0.4.0`
- 日期：2026-07-15
- 目标协议：Core `0.4.0` / `core-native-v2`

## 版本历史

| 版本 | 修改内容 | 日期 | 修改人 | 审核 | 批准 |
| --- | --- | --- | --- | --- | --- |
| `0.1.0` | 初版：公共字段 change 事件、Form 上下文、安全 handle 与主动 reset 命令 | 2026-07-15 | Codex | 待独立评审 | 用户已明确要求实现 |
| `0.2.0` | 增补 create default、update row 优先级和长表单滚动可访问性 | 2026-07-15 | Codex | 待独立评审 | 用户在消费侧联调后明确补充 |
| `0.3.0` | 增补模块声明的 1–3 列通用 Form 布局、窄屏降列和窗口屏幕边界 | 2026-07-15 | Codex | 待独立评审 | 用户基于长表单真实界面明确补充 |
| `0.4.0` | 增补同逻辑列共享 label/input 物理列、标签右对齐和输入框统一左边缘 | 2026-07-15 | Codex | 待独立评审 | 用户基于三列真实宿主截图明确补充并要求 TDD |
| `0.5.0` | 长表单改为隐藏可见滚动槽，同时保留内容滚动能力 | 2026-07-15 | Codex | 待独立评审 | 用户基于真实宿主截图明确补充 |

## 目标

作为 Hosted UI 模块作者，我希望公共表单字段可声明 `on_change` 模块事件，并在事件处理中通过安全、短生命周期的 Form Handle 主动重置当前表单，以便模块自行完成字段联动，而不把业务模板或真实前端对象带入 Core 协议。

## 非目标

- 不修改任何消费模块。
- 不加入平台、设备模板或 preset 等业务逻辑。
- 不让 Core 根据 handler 返回的业务 effect 决定重置。
- 不跨进程传递真实 Qt/前端 Form 对象。
- `ui.form.reset` 不提交表单，不调用 create/update handler，不做业务默认值计算。

## 用户故事与需求

### REQ-022-001：公共字段可选 change 事件

- 优先级：P0
- 公共字段至少覆盖 `Select`；若 `Input` 与其共享同一字段事件抽象，则统一支持。
- `on_change` 是公共组件事件，字段未声明时行为完全不变。
- change 观察信息必须包含组件/字段标识、`event="change"`、`value`、`previous_value` 和 scope。

### REQ-022-002：容器感知的事件上下文

- 优先级：P0
- create/update Form 中的事件提供 `scope.kind="form"`、不可伪造 Form Handle、form mode 和当前 form values。
- Form 外字段提供 `scope.kind="standalone"` 或现有等价语义，且不得携带可用 Form Handle。
- 不记录完整表单 values。

### REQ-022-003：通用 `ui.form.reset` 命令

- 优先级：P0
- 模块 handler 可主动调用 `context.tools.call("ui.form.reset", form_id=<handle>, initial_values=<mapping>)`；SDK 可提供等价的类型安全 proxy，但底层仍调用该通用命令。
- reset 同时替换当前值和初始值，清除 dirty 与校验错误；不得提交、调用 create/update handler 或内置业务判断。
- `0`、`False`、空字符串和字面量 `"undefined"` 必须精确保留。

### REQ-022-004：Handle 安全、生命周期与并发

- 优先级：P0
- Form Handle 只能操作创建它的模块、页面、用户会话和仍打开的表单；关闭后失效。
- 非法、过期或越权 handle 返回稳定错误，且不操作任何其他 Form。
- 快速连续 change 遵循现有异步序列控制，旧调用不得覆盖新选择。
- handler 失败时保留当前表单，并走既有错误展示路径。

### REQ-022-005：通用 Form 初始化与长表单可访问性

- 优先级：P0
- create Form 按键存在性读取 DataTable column `default`，精确保留假值；update Form 优先使用 row 实际值，不被 default 覆盖。
- reset 后仍以模块传入的 `initial_values` 重建整张 Form。
- 多字段 Form 内容区可滚动，确认/取消按钮保持可见，不按业务字段做布局特化。

### REQ-022-006：声明式多列 Form 布局

- 优先级：P0
- `crud.form.layout` 可声明 `columns` 为精确整数 `1`、`2`、`3`，以及可选精确非负整数 `gap`；`bool`、其它数值、字符串和范围外列数必须拒绝。
- 未声明 layout 时保持一列；多列按字段顺序逐行填充。
- 屏幕宽度不足时 renderer 自动降低有效列数，并保证对话框宽高不超过屏幕可用区域；操作按钮保持在滚动区外。
- 布局不得改变 create default、update row、change/reset 与提交契约。

### REQ-022-007：Form 字段标签与输入框列对齐

- 优先级：P0
- 同一逻辑列的所有字段必须共享一个 label 物理列和一个 input 物理列，不得由每个字段各自计算 label 宽度。
- 标签文本以全角冒号结尾，按 `AlignRight | AlignVCenter` 右对齐；输入控件从共享 input 列的统一左边缘开始，并可横向扩展。
- 三个逻辑列对应六个物理列，字段仍按声明顺序逐行填充；单列对应两个物理列。
- 该视觉修正不得改变 schema、字段身份、create/update/default、on_change/reset、滚动或按钮区语义。

### REQ-022-008：长 Form 隐藏式滚动

- 优先级：P0
- CRUD Form 的水平和垂直滚动槽不显示，避免原生滚动条破坏宿主视觉一致性。
- 内容仍可通过滚轮、触控板、键盘或程序化滚动完整访问，操作按钮继续固定在滚动区外。
- 不新增 schema，不改变字段、布局、初始化、change/reset 或提交语义。

## 验收标准

- `AC-022-001`：Form 内 Select 的 `on_change` 调用模块 handler，事件包含准确字段标识、新旧值、form scope/handle/mode/values。
- `AC-022-002`：Form 外 Select 正常调用 handler，但没有 Form Handle。
- `AC-022-003`：handler 通过 `ui.form.reset` 重设当前 Form，当前值与初始值均更新，dirty 和 validation 被清理。
- `AC-022-004`：reset 精确保留 `0`、`False`、`""`、`"undefined"`。
- `AC-022-005`：关闭、过期、伪造以及跨模块/页面/会话 handle 均被稳定拒绝。
- `AC-022-006`：快速连续 change 不发生旧调用覆盖新结果。
- `AC-022-007`：未配置 `on_change` 的既有 CRUD/Form/Select 行为与相关回归保持通过。
- `AC-022-008`：Contracts schema、SDK scanner/校验、Core 工具注册和 renderer 测试覆盖最终协议。
- `AC-022-009`：本变更源码、schema 与文档不包含消费模块、平台/设备模板或业务 preset 特化。
- `AC-022-010`：create Form 精确保留字段 default；update Form 优先使用 row 实际值。
- `AC-022-011`：约 35 个字段的 Form 可完整滚动访问且操作按钮区保持可见。
- `AC-022-012`：Contracts 接受 1–3 列与可选非负 gap，拒绝 0、4、bool、非整数和负 gap。
- `AC-022-013`：未声明 layout 保持一列；35 字段 columns=3 时逐行生成 3 列、12 行，按钮不在滚动区且窗口不超过屏幕。
- `AC-022-014`：窄屏自动降列，多列布局下 create default、update row、on_change/reset 与提交行为不变。
- `AC-022-015`：三列 Form 的 grid 使用六个共享物理列；label 位于 0/2/4，input 位于 1/3/5。
- `AC-022-016`：所有 label 以全角冒号结尾并包含 `AlignRight`；input 物理列具有 stretch。
- `AC-022-017`：同一逻辑列跨行 label 右边缘一致、input 左边缘一致，字段顺序保持 row-major。
- `AC-022-018`：单列、create/update/default、on_change/reset、滚动与按钮相关回归不变。
- `AC-022-019`：35 字段 Form 的水平/垂直滚动条策略均为始终隐藏，垂直滚动范围仍有效且操作按钮不进入滚动区。

## 非功能需求

- `NFR-022-SEC`：Form Handle 使用 Core 生成的不可预测标识，并绑定 module/page/session/form 生命周期；验证为负向单元测试。
- `NFR-022-CONC`：同一字段 change 采用 latest-wins 或项目现有等价序列语义；验证为可控乱序完成测试。
- `NFR-022-PRIV`：日志不得输出完整 form values；验证为代码审查与敏感词/日志断言。
- `NFR-022-COMPAT`：未声明 `on_change` 的 schema 归一化结果与运行行为不变；验证为既有测试及新增兼容回归。
- `NFR-022-RESP`：Form 列数必须适配屏幕可用宽度，不允许窗口超出可用区域；验证为窄屏 renderer 测试。
- `NFR-022-VIS`：同一逻辑列标签和输入框必须具有稳定共享对齐线；验证为 grid 结构与 widget geometry 断言。
- `NFR-022-SCROLL`：长 Form 隐藏滚动槽不得禁用内容滚动；验证为隐藏策略与非零滚动范围断言。

## 领域模块映射与接口边界

- Contracts owner：声明并规范化公共字段 `on_change` 与事件 payload 类型。
- SDK owner：扫描/校验模块事件 handler 签名与 manifest 产物（若现有 scanner 覆盖此类引用）。
- Core MMS owner：`@ui_action` 调用、Hosted UI runtime capability、Form Handle 生命周期和 `ui.form.reset` 工具授权。
- 前端渲染器 owner：字段 change 观察、scope/values 采集、dirty/validation/reset 语义与异步 latest-wins。
- 模块 owner：决定是否 reset、计算 initial values，并主动调用通用命令。
- 数据库：无影响；不新增持久化表。

## baseline 影响分析

- 领域：不新增领域；扩展现有 Contracts / SDK / Core MMS / renderer 职责。
- 架构：在现有 Hosted UI `@ui_action` 与 runtime tools 边界内加入安全 Form Handle；不改变 Core runtime owner。
- API：新增可选 schema 字段、change 事件 payload 和 `ui.form.reset` 工具命令，均为向后兼容扩展。
- UI：扩展公共字段事件、Form 状态控制和通用多列 Form 对齐 baseline；不引入字段级或消费模块布局特化。
- 数据库：无影响。
- baseline 变更建议：更新现有 Hosted UI 设计/开发者文档即可，不另建领域或数据库 baseline work item。

## 风险与回滚

- 风险：handle 注册表生命周期泄漏、跨页面越权、乱序 handler reset、truthy fallback 丢失假值。
- 缓解：作用域绑定、关闭注销、稳定错误、序列 token、显式 sentinel/键存在性判断和负向测试。
- 回滚：移除可选 `on_change`、Form Handle 注册表与工具命令；无数据迁移。
- 未决问题：无。具体字段事件抽象和工具挂载点以现有架构审查结果为准。
