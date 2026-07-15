# Hosted UI 公共字段 change 事件与安全 Form Reset 实施计划

> **给执行者：** 只交付 Core / Contracts / SDK / 前端渲染器通用能力；消费模块、平台模板、业务默认值、发布与推送均不在本计划内。

**目标：** 为 Hosted UI `Input` / `Select` 及 CRUD Form 字段提供统一 `on_change` 事件，并允许模块通过安全短生命周期 handle 主动调用 `ui.form.reset` 重置当前 Form。

**架构：** Contracts 定义公共字段事件、事件 payload、独立字段组件和 reset 结果类型；SDK scanner 校验 handler 引用与固定 `(context, event)` 签名。Core renderer 持有真实 Qt Form 状态，Core registry 只向模块暴露绑定 module/page/renderer-session/form/revision 的 opaque handle；runtime tool 在绑定的 form change action surface 中执行通用 reset，模块不获得 Qt 对象，Core 不解释业务返回值。

**技术栈：** Python 3.12、PyQt6、qasync/asyncio、crawler4j-contracts `0.4.3`（本地 workspace 源码）、crawler4j-sdk `0.4.4`（本地 workspace 源码）、pytest、ruff、uv。

**工作项：** `CR-022`

**任务：** `TASK-041`

**状态：** `validation_complete`（首轮能力已由提交 `86a01b1a` 落地；renderer-only 共享 label/input 对齐增量已完成 TDD、独立复评与最终 gate）

## 输入

- 用户批准需求：本会话完整职责边界、安全/并发要求和九项验收条件。
- 工作项简报：`.factory/workitems/CR-022/brief.md`。
- 相关摘要：`.factory/memory/{runtime-brief,architecture,api,requirements,tasks}.summary.md`。
- 已读取事实：Hosted UI framework、bulk update design、`hosted_ui.py`、`v2_scanner.py`、`runtime_capabilities.py`、`module_ui_runtime.py`、`managed_page_renderer.py`、`data_table.py` 与目标测试。

## 范围

### 目标

- 公共字段事件 schema：`on_change={"type": "ui_action", "name": <handler>}`。
- 固定 `HostedFieldChangeEvent` 和 `HostedFieldChangeActionSchema` Contracts 类型。
- Form scope 安全 handle、五分钟 TTL、close 失效、scope 绑定与同字段 latest-wins revision。
- 通用 `ui.form.reset(form_id, initial_values)`；替换 current/initial values 并清 dirty/validation。
- 独立 `Select` / `Input` 组件和 CRUD 字段复用同一事件抽象。
- 未声明 `on_change` 的页面、DataTable、CRUD 和字段保持旧行为。
- create Form 使用字段 `default`，update Form 使用 row 实际值；长 Form 内容区滚动且操作按钮固定可见。
- CRUD Form 可选 `layout={"columns": 1|2|3, "gap": <可选非负整数>}`；默认一列，逐行填充，窄屏降列且窗口受屏幕边界约束。
- 每个逻辑列使用共享 label/input 物理列；label 右对齐、input 统一左边缘并横向扩展，不改变 schema 或表单事件/状态协议。

### 非目标

- 不修改任何消费模块。
- 不加入平台、设备、模板、preset case、业务默认值或 handler effect 协议。
- 不发布 Contracts / SDK、不修改版本号、不 push。
- 不把真实 Qt widget、dialog 或 form controller 放入事件 payload、TaskContext runtime 或模块可见对象。

## 最终契约

### 字段 schema

```python
"on_change": {
    "type": "ui_action",
    "name": "handle_field_change",
}
```

- 独立组件使用 `{"type": "Select", "id": ..., "options": [...], "on_change": ...}` 或 `{"type": "Input", "id": ..., "on_change": ...}`。
- CRUD Form 继续由 `DataTable.columns[]` 定义字段；相同 `on_change` 属性可放在 form-compatible column 上。
- 不提供字符串 shorthand，不接受 workflow/page_action，不接受 params/effect。

### handler 与事件

```python
@ui_action(name="handle_field_change")
async def handle_field_change(
    context: TaskContext,
    event: HostedFieldChangeEvent,
) -> None:
    ...
```

Form payload：

```python
{
    "component": {"id": "accounts", "type": "Select"},
    "field": "preset",
    "event": "change",
    "value": new_value,
    "previous_value": old_value,
    "scope": {
        "kind": "form",
        "form_id": opaque_handle,
        "mode": "create",  # 或 "update"
        "values": current_values,
    },
}
```

Standalone payload 的 `scope` 固定为 `{"kind": "standalone"}`，不含 `form_id`、`mode` 或 `values`。

### reset tool

```python
result = context.tools.call(
    "ui.form.reset",
    form_id=event["scope"]["form_id"],
    initial_values={...},
)
```

- 成功返回 `{"ok": True}`。
- `initial_values` 必须为 mapping；未知字段被拒绝，不做模糊忽略。
- 非法、过期、关闭或越权 handle 统一抛出稳定 `RuntimeError("ui.form.reset rejected: FORM_HANDLE_REJECTED")`，避免 handle 存在性 oracle。
- 非 Form action 调用抛出 `RuntimeError("ui.form.reset rejected: FORM_SCOPE_UNAVAILABLE")`。
- 旧 revision 调用抛出内部稳定 `FORM_EVENT_STALE`，renderer 对已经过时的 action 静默丢弃，不覆盖新值。

### CRUD Form layout

```python
"crud": {
    "form": {
        "create_columns": [...],
        "update_columns": [...],
        "layout": {"columns": 3, "gap": 12},
    },
}
```

- `columns` 为必填精确整数，只允许 `1`、`2`、`3`；`bool` 不作为整数接受。
- `gap` 可省略，提供时必须是精确非负整数。
- 省略 `layout` 时 normalize 结果与 renderer 行为保持旧的一列语义。
- renderer 按字段顺序逐行填充；窄屏按可用宽度降低有效列数，不改变字段、事件、reset 或提交协议。

### 本地联调与版本

- 本 work item 不改版本：Contracts `0.4.3`、SDK `0.4.4`。
- 当前仓 `pyproject.toml [tool.uv.sources]` 与 workspace 已把两者指向 `packages/crawler4j-contracts` / `packages/crawler4j-sdk` editable 源码。
- Core 内联调命令：`uv run pytest ...`；外部消费模块在 Core 未发布前应通过 uv path source / editable 安装指向这两个本地目录，不从现有 PyPI 版本期待新类型。

## 文件

| 类型 | 路径 | 职责 |
| --- | --- | --- |
| 修改 | `packages/crawler4j-contracts/src/crawler4j_contracts/hosted_ui.py` | 公共事件/action/scope/Input/Select/字段 schema 与规范化 |
| 修改 | `packages/crawler4j-contracts/src/crawler4j_contracts/__init__.py` | 导出公共类型 |
| 修改 | `packages/crawler4j-sdk/src/v2_scanner.py` | on_change handler 引用、固定签名与事件类型诊断 |
| 新建 | `packages/crawler4j/src/core/mms/ui/hosted_form.py` | Form controller、opaque handle registry、scope/revision/TTL/reset 语义 |
| 修改 | `packages/crawler4j/src/core/atm/runtime_capabilities.py` | `ui.form.reset` action-surface 工具注册与调用绑定 |
| 修改 | `packages/crawler4j/src/core/mms/ui/module_ui_runtime.py` | 把 renderer-owned form tool binding 注入隔离 action session |
| 修改 | `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py` | Input/Select 渲染、CRUD form controller、事件 payload、错误路径与 lifecycle |
| 测试 | `packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py` | Contracts 规范化和非法 schema |
| 测试 | `packages/crawler4j/tests/unit/test_sdk/test_contracts_exports.py` | 公共类型导出 |
| 测试 | `packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py` | handler 引用/签名/type gate |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py` | tool 可见面与拒绝语义 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_mms/test_module_ui_runtime.py` | action context 工具注入与隔离 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py` | Form/standalone 事件、reset、failure、并发与兼容回归 |
| 文档 | `docs/04-project-development/04-design/hosted-ui-form-field-events.md` | 安全与并发设计事实 |
| 文档 | `docs/04-project-development/04-design/{module-hosted-ui-framework,api-design}.md` | 公共组件/API baseline 更新 |
| 文档 | `docs/03-developer-guide/v0.4.0/ui-and-data-table.md` | 模块作者契约和本地联调示例 |
| 追踪 | `.factory/workitems/CR-022/`、`.factory/memory/{api,architecture,requirements,tasks,tests}.summary.md` | evidence、report、review、ledger 与恢复索引 |

## 边界

- 层级：Contracts -> SDK 静态诊断；renderer -> Core registry -> runtime tool -> 模块 `@ui_action`。
- 领域：MMS Hosted UI 与公共 Core runtime capability。
- 接口归属方：Contracts / SDK / Core MMS / UI renderer 维护者。
- 下游依赖：使用 `@page` / `@ui_action` 的 `core-native-v2` 模块。
- 禁止耦合：Core 不计算默认值、不识别模板/设备/平台/业务字段，不用 handler 返回 effect 决定 reset。

## 任务 1：Contracts 与 SDK 公共契约

**任务切片：**

- 设计方案：新增公共 FieldEvent TypedDict 族；`DataTableColumnSchema` 与独立 Input/Select 复用 `FieldEventSchema`。
- 接口设计：固定对象形 `on_change` 与 `(context, event: HostedFieldChangeEvent)`。
- UI：N/A；本任务只处理可序列化契约和静态诊断，渲染在任务 2。
- 测试设计：合法 normalize/export、未知键、非 ui_action、missing handler、错参数/宽泛 event 类型。
- 开发：修改 Contracts 与 scanner，不修改 runtime。
- 单测：三个 SDK/Contracts 目标文件。
- review：核对向后兼容、错误 location 与公共/非 DataTable 专属归属。
- 集成测试：和 Core 目标集共同执行。
- 失败断言：缺事件类型、接受 effect/params、只在 DataTable 私有分支实现或旧 schema 归一化改变均失败。

- [x] RED：新增 schema/export/scanner 测试，确认缺少新类型/未知字段/缺诊断失败。
- [x] GREEN：实现公共 schema、normalize、export 与 scanner diagnostics。
- [x] 定向验证：三个目标文件转绿。

## 任务 2：Core Form registry、runtime tool 与 renderer

**任务切片：**

- 设计方案：renderer 每实例生成 session token；打开 Form 时 registry 生成 `secrets.token_urlsafe` handle 并存 controller 弱引用、module/page/session、TTL 与 revision。
- 接口设计：tool capability 绑定当前 field event form/revision；reset 只接收 `form_id`、`initial_values`。
- UI：独立 Input/Select 沿用 `StyledLineEdit` / `StyledComboBox`；CRUD Form 内容区使用可选 1–3 列逐行网格和滚动容器，窄屏降列且按钮区固定可见；reset block signals，不递归触发 change。
- 测试设计：Form/standalone payload、reset 状态、falsy 值、create default/update row、35 字段三列/滚动、默认单列、窄屏降列、closed/expired/forbidden、rapid change、handler error、无 on_change 回归。
- 开发：新增 `hosted_form.py` 并最小接入现有 action surface、bridge 和 renderer。
- 单测：hosted form controller/registry、runtime capabilities、bridge、renderer。
- review：重点审计 handle oracle、scope 绑定、widget 泄漏、日志 values、乱序 session。
- 集成测试：Contracts + SDK + Core 合并目标集。
- 失败断言：真实 Form 对象进入模块、未绑定 action 可 reset、旧调用覆盖新值、truthy fallback 丢值、失败触发 submit 均失败。

- [x] RED：新增验收用例并确认因工具不存在、payload 缺字段、create default 未读取、无滚动容器或状态不可观察而失败。
- [x] GREEN：实现 controller/registry/tool binding、独立字段渲染、CRUD 字段事件、create/update 初始化、长表单滚动、多列响应式布局和 latest-wins。
- [x] 定向验证：七个目标文件 `199 passed`。

## 任务 2A：Renderer 共享 label/input 物理列视觉修正

**任务切片：**

- 根因：当前外层 grid 的每个 item 是包含独立 `QFormLayout` 的 field container，各 container 分别计算 label 宽度，无法形成同逻辑列共享对齐线。
- 最小实现：外层 `QGridLayout` 为每个逻辑列分配 `label/input` 两个物理列；直接添加 `QLabel` 与输入 widget，删除字段级 `QFormLayout` container。
- 对齐：label 使用 `AlignRight | AlignVCenter` 且文本以全角冒号结尾；input 列设置 stretch，widget 使用横向 expanding policy。
- TDD：先证明旧结构只有逻辑列 item 且包含独立 container；再断言三列六物理列、label/input 列位置、alignment/stretch、跨行 geometry、单列与 row-major 回归。
- 回归：复跑 renderer 全文件和 CR-022 七文件目标集，确认 create/update/default/on_change/reset/滚动/按钮不变。

- [x] RED：4 项测试失败；旧 grid 仅 6/35 个 field container item，缺少共享 input 列。
- [x] GREEN：以直接 label/input grid placement 完成最小 renderer 修正。
- [x] 定向验证：共享列 4 passed、renderer 35 passed、CR-022 七文件 201 passed、目标 Ruff 通过。
- [x] 独立 review RED：超大合法 gap 下 input geometry 超出无横向滚动的 viewport。
- [x] review fix GREEN：内部 `6px` 与声明式逻辑列 gap 分离；超大 gap 可访问性和宽屏 `gap=100` 保留测试分别转绿。

## 任务 2B：Renderer 长 Form 隐藏式滚动条

**任务切片：**

- 根因：CRUD Form 的垂直 `QScrollArea` 使用 `ScrollBarAsNeeded`，长表单会显示平台原生滚动槽和箭头。
- 最小实现：水平与垂直策略统一为 `ScrollBarAlwaysOff`；保留同一个 `QScrollArea`、内容尺寸和滚动范围。
- TDD：35 字段 Form 先断言双向滚动条隐藏而失败，再断言垂直范围非零且可改变滚动位置。
- 回归：按钮继续位于滚动区外，create/update/default/on_change/reset、多列布局与字段提交不变。

- [x] RED：垂直策略实际为 `ScrollBarAsNeeded`，隐藏式滚动断言失败。
- [x] GREEN：垂直策略改为 `ScrollBarAlwaysOff`，长表单仍保留有效滚动范围。

## 任务 3：正式文档、证据与收口

**任务切片：**

- 设计方案：新增单一通用设计文档，更新既有 framework/API/developer guide，不复制消费模块逻辑。
- 接口设计：登记最终 schema、payload、tool、错误与本地 workspace 联调。
- UI：N/A；只记录任务 2 已测试的 UI 行为，不新增视觉资产。
- 测试设计：合并目标集、相关 SDK/MMS/UI 回归、全量 unit、ruff、lock、diff 和特化词扫描。
- 开发：仅文档与执行证据。
- 单测：运行新鲜完整命令并保留 exit code。
- review：独立审计安全、兼容和范围。
- 集成测试：全量 unit；基线失败必须按归因分开记录。
- 失败断言：缺任一用户验收项、出现业务特化、无新鲜验证或未解释基线失败均失败。

- [x] 更新正式文档、evidence、report、review input、ledger 与 memory。
- [x] 运行定向、邻近、全量、ruff、`uv lock --check`、`git diff --check` 和特化扫描。

## 测试策略

- RED：Contracts/scanner 与 Core 两批新增测试分别确认失败原因。
- GREEN：同一目标测试转绿。
- 定向回归：上述七个测试文件。
- 邻近回归：`packages/crawler4j/tests/unit/test_sdk/`、`test_core/test_mms/`、`test_ui/`。
- 全量回归：`QT_QPA_PLATFORM=offscreen uv run pytest packages/crawler4j/tests/unit -q -p no:cacheprovider`。
- 静态检查：目标文件 `uv run ruff check ...`、`uv lock --check`、`git diff --check`。
- 特化扫描：仅扫描本 work item 代码/schema/文档 diff，禁止新增消费模块、平台/设备模板或业务 preset 逻辑。
- 未运行：消费模块 E2E、平台真机、包发布与 push；均超出用户授权范围。

## 文档与本地联调

- 正式文档：新设计文档 + framework/API baseline + v0.4.0 developer guide。
- 本地模块：通过 uv path source 指向 `packages/crawler4j-contracts`，SDK 开发依赖指向 `packages/crawler4j-sdk`；具体命令以最终验证证据为准。
- `.factory/memory/`：只同步 CR-022 状态、契约摘要和 evidence/review 路径。
- 流水账：`.factory/workitems/CR-022/ledger.jsonl`。

## 评审门

- 计划评审：`covered_by_user_approved_scope`
- 任务评审：首轮 `approved`（独立 reviewer `98/100`）；共享列增量 `approved`（独立 reviewer `100/100`）
- 验证：renderer 36 passed、七文件 202 passed、邻近 586 passed；全量 13 项范围外环境基线已登记；Ruff/lock/docs/diff/scope gate 通过
- 本地提交：`authorized_by_project_agents`
- 记忆同步：`complete`

## 计划自审

- 规格覆盖：AC-022-001..018 全部映射到任务 1/2/2A/3。
- 占位符扫描：无未定义 placeholder。
- 发现占位语则失败：通过。
- 缺测试设计则失败：通过。
- UI N/A 说明：任务 1/3 不渲染 UI；任务 2 明确视觉行为。
- 类型一致性：`on_change`、`event`、`form_id`、`initial_values` 在 Contracts/SDK/Core/文档一致。
- 可构建性：文件、补丁形状、测试命令、错误 code 与版本/联调方式均明确。
- Shanforge 门禁：包含 RED/GREEN、evidence、独立 review、verification、memory、ledger 与本地提交，排除发布/push。
