# 0.4.0 模块架构规则

本文固定 `core-native-v2` 模块的目录、DDD 边界和动作调用规则。新模块和迁移模块都按本页执行。

## 根目录固定规则

模块根目录只放框架识别的固定入口，不新增根级 `adapters/`、`helpers/`、`services/` 或 `utils/`。

| 根目录 | 允许内容 | DDD 含义 |
|---|---|---|
| `interfaces/` | `@interface` | 领域端口或能力抽象 |
| `objects/` | `@component` | 可注入业务对象、应用服务、领域服务或端口实现 |
| `workflows/` | `@workflow` | 应用用例编排入口 |
| `tasks/` | `@page_action` | 浏览器页面自动化动作 |
| `pages/` | `@page`、`@ui_action` | Hosted UI 页面与用户操作适配器 |
| `data/` | `@data_table`、`@data_view` | 持久化表、只读视图和 read model 契约 |
| `candidates/` | `@env_candidates` | 运行环境候选纯函数 |
| `cleanups/` | `@env_cleanup_candidates` | 批量环境清理候选纯函数 |

需要私有 helper 时，放到所属固定目录内，并用下划线命名，例如 `tasks/_browser.py`、`pages/_widgets.py`、`objects/_mapping.py`、`data/_sql.py`。不要把跨层 helper 聚合到根目录。

## DDD 分层

`@workflow` 是应用层入口，负责调用 component、选择顺序、处理错误和返回 `TaskResult`。它不直接写 UI schema，也不直接塞 SQL 字符串。

`@component` 是业务能力的承载点。外部 API client、规则引擎、页面业务用例、账号状态服务等都优先放在 `objects/` 下，用 `@component` 或普通私有类表达。component 可以组合 `interfaces/` 端口，也可以调用 `ctx.db` 或 `ctx.run_page_action(...)`。

`@page_action` 是浏览器页面动作门面，只表达一个可观测页面动作，例如打开页面、点击、填写、读取 DOM、下载文件。它不是业务服务，也不是 Hosted UI handler。

`@ui_action` 是 Hosted UI 用户操作门面，只响应按钮、CRUD handler、导出、刷新和表单提交。它不操作浏览器页面，不调用 `ctx.run_page_action(...)`。

`@data_table` / `@data_view` 是数据契约，不写业务流程。业务读写通过 `ctx.db` 执行，数据表 schema 只声明稳定字段和宿主需要理解的索引、绑定字段、存储模式。

## Page Action 调用规则

允许调用路径只有：

```text
workflow/component -> ctx.run_page_action("action_name", **kwargs) -> @page_action
```

禁止调用路径：

```text
@page_action -> ctx.run_page_action(...) -> @page_action
@ui_action -> ctx.run_page_action(...) -> @page_action
Hosted UI Button -> type="page_action"
```

如果一个页面动作需要拆公共步骤，不要把公共步骤也声明成 `@page_action`。使用以下方式：

- 无浏览器 I/O：抽普通纯函数，例如 `tasks/_parsing.py`
- 有浏览器 I/O：抽普通 browser adapter 函数或类，例如 `tasks/_browser.py`
- 有业务决策：抽到 `objects/` 的 component 或 use case
- 多个可观测页面步骤：由 workflow/component 顺序调用多个 `ctx.run_page_action(...)`

运行时会拒绝 `page_action -> page_action` 嵌套调用，以避免隐藏动作链、递归、取消语义和日志归因混乱。

## Hosted UI 规则

页面 schema 由 `@page` 返回，按钮和 CRUD handler 使用 `type: "ui_action"`。`@page(schema=...)` 可用 `crawler4j_contracts.PageSchema` 标注；合法按钮 action type 只有 `reload`、`open_page` 和 `ui_action`。

```python
{
    "type": "Button",
    "label": "创建账号",
    "action": {"type": "ui_action", "name": "create_account_from_ui"},
}
```

`@ui_action` 可以读取表单参数、调用 `ctx.db` 或普通服务函数，最后返回 JSON-like 结果。它不是 workflow/component 对象图节点，不能通过装饰器注入 component；需要复用业务逻辑时，把逻辑放到普通函数、服务对象或正式运行面里。涉及真实浏览器页面时，应由 workflow/component 调用 `@page_action`，不要从 Hosted UI 直接驱动浏览器。

DataTable CRUD handler 名称仍写在 `crud.create_handler`、`crud.update_handler`、`crud.delete_handler`，但这些字段指向的是 `@ui_action` 名称。入参固定为：create 接收 `payload`，update 接收 `crud.primary_key` 同名参数和 `payload`，delete 接收 `crud.primary_key` 同名参数。

## 旧模块迁移规则

迁移旧模块时，根目录 `adapters/` 和 `helpers/` 不保留。

- 浏览器驱动 helper 移到 `tasks/_browser.py` 或按站点拆到 `tasks/<scene>/_browser.py`
- 页面 schema 片段移到 `pages/_widgets.py`
- 表格字段、视图 SQL 和 seed helper 移到 `data/_*.py`
- 业务规则、账号状态、订单/酒店/任务用例移到 `objects/` component 或 component 私有 helper
- 外部服务 client 若是业务依赖，放到 `objects/` 并通过 `@component` 注入；若只是某个 page action 的技术细节，放到 `tasks/_*.py`

判断标准：能被 workflow 复用并承载业务语言的，放 `objects/`；只服务一个浏览器动作的，放 `tasks/`；只服务 Hosted UI 的，放 `pages/`；只服务数据契约的，放 `data/`。
