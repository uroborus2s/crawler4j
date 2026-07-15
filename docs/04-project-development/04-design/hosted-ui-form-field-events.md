# Hosted UI 公共字段事件与 Form Reset 设计

**文档状态：** 已实现
**关联 ID：** `API-023`, `CR-022`, `TASK-041`
**最后更新：** 2026-07-15

## 1. 结论

Hosted UI 的 `Input`、`Select` 和 DataTable CRUD Form 字段共享同一套可选 `on_change` 事件。模块通过 `@ui_action` 接收纯数据事件；Form 场景只暴露 Core 生成的短生命周期 `form_id`，不暴露 Qt dialog、widget 或其它真实前端对象。

模块是否重置、如何计算新初始值、传入哪些值均由模块决定。Core 只执行 `ui.form.reset` 的通用状态操作，不解释 handler 返回值，不包含业务分支。

## 2. Schema 与 handler

字段事件只接受对象形声明：

```python
"on_change": {
    "type": "ui_action",
    "name": "handle_field_change",
}
```

它可用于独立字段：

```python
{
    "type": "Select",
    "id": "preset",
    "label": "方案",
    "options": ["basic", "advanced"],
    "on_change": {"type": "ui_action", "name": "handle_field_change"},
}
```

也可用于 `DataTable.columns[]` 中被 `crud.form.create_columns/update_columns` 引用的字段。字符串简写、`workflow`、`page_action`、`params` 和 effect 协议均不属于该契约。

handler 固定接收 `(context, event: HostedFieldChangeEvent)`：

```python
from crawler4j_contracts import HostedFieldChangeEvent, TaskContext, ui_action


@ui_action(name="handle_field_change")
def handle_field_change(context: TaskContext, event: HostedFieldChangeEvent) -> None:
    ...
```

SDK scanner 会校验 action 引用、确定参数和 `HostedFieldChangeEvent` 类型注解。

## 3. 事件 payload

Form 内事件：

```python
{
    "component": {"id": "accounts", "type": "Select"},
    "field": "preset",
    "event": "change",
    "value": "advanced",
    "previous_value": "basic",
    "scope": {
        "kind": "form",
        "form_id": "<opaque Core handle>",
        "mode": "create",  # 或 "update"
        "values": {"preset": "advanced", "enabled": False},
    },
}
```

独立字段事件使用：

```python
{
    "component": {"id": "preset", "type": "Select"},
    "field": "preset",
    "event": "change",
    "value": "advanced",
    "previous_value": "basic",
    "scope": {"kind": "standalone"},
}
```

`standalone` scope 不包含 `form_id`、`mode` 或 `values`。Core 日志不得记录完整 `scope.values`。

## 4. `ui.form.reset`

Form handler 可以主动调用：

```python
context.tools.call(
    "ui.form.reset",
    form_id=event["scope"]["form_id"],
    initial_values={
        "preset": "advanced",
        "priority": 0,
        "enabled": False,
        "note": "",
        "marker": "undefined",
    },
)
```

成功返回 `{"ok": True}`。`initial_values` 是整张 Form 的新初始映射：Core 用它同时重建当前值和初始值，清除 dirty 与 validation 状态，但不提交，不调用 CRUD handler，也不计算默认值。`0`、`False`、`""` 和字面量 `"undefined"` 按原值保留。未知字段以 `FORM_INITIAL_VALUES_INVALID` 拒绝，不做模糊忽略。

Form 初次打开时，create 模式读取 DataTable column 的 `default`；update 模式优先读取当前 row 的实际字段值。长 Form 使用内部滚动容器，操作按钮保持在滚动区外。

CRUD Form 可选声明通用多列布局：

```python
"form": {
    "create_columns": [...],
    "update_columns": [...],
    "layout": {"columns": 3, "gap": 12},
}
```

`layout.columns` 必须是精确整数 `1`、`2` 或 `3`，`bool` 不作为整数接受；`layout.gap` 可省略，若提供则必须是精确非负整数。未声明 `layout` 时兼容旧行为，保持一列。renderer 按字段声明顺序逐行填充网格；每个逻辑列由共享的 label/input 两个物理列组成，label 以全角冒号结尾并右对齐，input 共享统一左边缘且横向扩展。共享 grid 把 label/input 内部紧凑间距与逻辑列 gap 分开表达：声明 gap 只施加到第二、第三逻辑列前，并继续作为行间距。可用屏幕宽度不足时自动降低有效列数；合法超大 gap 降为单列后不再产生无意义的水平空白。对话框宽高受 renderer 所在屏幕可用区域约束，表单内容继续滚动，操作按钮不进入滚动区。

## 5. 安全与并发

- `form_id` 由 Core 使用不可预测随机值生成，绑定 module、page、renderer session、具体 Form 和五分钟 TTL。
- 关闭、过期、伪造或越权 handle 统一返回 `ui.form.reset rejected: FORM_HANDLE_REJECTED`，不泄露 handle 是否存在。
- 非 Form action 调用 reset 返回 `ui.form.reset rejected: FORM_SCOPE_UNAVAILABLE`。
- 每次字段变化递增 Form revision；绑定旧 revision 的 reset 返回 `FORM_EVENT_STALE`，renderer 静默丢弃，避免旧 handler 覆盖新选择。
- 每次字段事件使用隔离的 UI action session，避免并发 handler 改写共享 `TaskContext.tools`。
- handler 失败时保留当前 Form 和用户已选值，并走现有 Hosted UI 错误展示路径。

## 6. 版本与本地联调

本变更不发布包，也不修改版本号：Contracts 保持 `0.4.3`，SDK 保持 `0.4.4`。crawler4j workspace 的 `[tool.uv.sources]` 已直接使用本地 workspace 包。

外部模块在正式包发布前可把虚拟环境临时指向本仓源码：

```bash
uv pip install --python .venv/bin/python \
  --editable /Users/uroborus/PythonProject/crawler4j/packages/crawler4j-contracts \
  --editable /Users/uroborus/PythonProject/crawler4j/packages/crawler4j-sdk
```

需要持久化联调来源时，在模块 `pyproject.toml` 的 `[tool.uv.sources]` 中为两个包配置本地 `path` 和 `editable = true`，再执行 `uv sync`。
