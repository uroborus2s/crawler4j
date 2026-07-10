# Hosted UI DataTable 行按钮 open_page 实施计划

**目标：** 在不改变表格选择、CRUD 和既有 `ui_action` 行按钮的前提下，让 actions 列按钮打开页面并携带当前行参数。

**架构：** `SkyDataTable` 继续只发出 action id 与当前行；Core `ManagedPageRenderer` 从行内 action spec 判别 `open_page` 并复用既有整行导航处理器。动态行数据不进入 Contracts 静态 schema 归一化，因此本轮不扩展 SDK/Contracts。

**技术栈：** Python 3.12、PyQt6、pytest、uv、ruff

**工作项：** `CR-019`

**状态：** `ready_for_review`

## 输入与范围

- 已批准需求：`.factory/workitems/CR-019/brief.md`
- 上游变更：`.factory/workitems/changes/CR-013-hosted-ui-master-detail-row-navigation.md`
- 技术边界：`docs/04-project-development/04-design/technical-selection.md`
- 目标：识别扁平行按钮 spec 的 `type="open_page"`，解析显式 params 后导航。
- 非目标：修改 `SkyDataTable`、Contracts、SDK scanner、整行 `row_action`、发布版本。

## 文件与边界

| 类型 | 路径 | 职责 |
|---|---|---|
| 修改 | `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py` | 在行按钮分发点增加 `open_page` 分支 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py` | 锁定点击行、参数、无 ui_action/刷新副作用 |
| 文档 | `docs/03-developer-guide/v0.4.0/ui-and-data-table.md` | 说明行按钮导航 schema |
| 记忆 | `.factory/memory/tasks.summary.md` | 登记 TASK-038 状态与证据索引 |

- 接口归属：Core MMS Hosted UI renderer。
- 下游依赖：模块页面返回的 DataTable 行数据。
- 禁止耦合：不得让 `SkyDataTable` 解释业务 action，不得用 `crud.primary_key` 隐式生成导航参数。

## 任务 1：实现并验证行按钮导航

**任务切片：**

- 设计方案：在 `_handle_table_row_action` 找到 action spec 后，仅对规范化的 `type="open_page"` 提前调用 `_handle_row_action` 并返回。
- 接口设计：行按钮沿用扁平 `{id, label, type, page_id, params}`；无 `type` 继续默认 `ui_action`。
- UI：使用既有 actions 列按钮，无新增控件或视觉样式。
- 测试设计：点击第二行详情按钮，断言回调收到第二行参数，同时同名 `@ui_action` 未执行且源表未请求刷新。
- 开发：只增加一个分支并复用现有 helper。
- 单测：目标用例红转绿。
- review：独立检查兼容性、参数语义与 diff 最小性。
- 集成测试：运行 renderer、SkyDataTable 与 Hosted UI schema 邻近测试。

- [ ] RED：新增 `test_managed_page_renderer_row_button_opens_page_with_clicked_row_params`。
- [ ] 运行并确认 RED：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider -q packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py::test_managed_page_renderer_row_button_opens_page_with_clicked_row_params
```

期望：导航断言失败，因为当前实现误调用同 ID 的 `@ui_action`。

- [ ] GREEN：在 `_handle_table_row_action` 中识别 `open_page`，调用 `_handle_row_action(action_spec, row)` 后返回。
- [ ] 重跑目标测试并确认通过。
- [ ] 更新开发者文档、evidence、report、ledger 与任务摘要。
- [ ] 生成独立评审输入，作者状态只到 `ready_for_review`。

## 测试策略

- 红灯 / 绿灯：上述单用例命令。
- 邻近回归：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider -q packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py packages/crawler4j/tests/unit/test_ui/test_data_table.py packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py
```

- 静态检查：

```bash
uv run ruff check packages/crawler4j/src/core/mms/ui/managed_page_renderer.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py
git diff --check
```

- 全量回归：本轮不作为必需门；变更只触及 renderer 单一分发分支，且工作区存在另一发布任务的未提交版本漂移。以 renderer 整文件及相邻表格/契约测试覆盖。

## 文档、记忆与评审门

- 正式文档：补充 actions 列 `open_page` 示例和兼容规则。
- 记忆：只在 `tasks.summary.md` 登记任务、状态与验证摘要，避免覆盖当前发布任务正在修改的 `current-state.md`。
- Ledger：记录 RED、GREEN、验证、review 与提交 gate。
- 计划评审：`pending`
- 任务评审：`pending`
- 验证：`pending`
- 提交：`pending`
- 记忆同步：`pending`

## 计划自审

- 规格覆盖：AC-019-001 至 AC-019-004 均映射到任务 1。
- 占位符扫描：无占位符或未定义对象。
- 类型一致性：复用既有 `dict[str, Any]` action spec 与导航回调。
- 可构建性：路径、补丁形状、命令和期望结果完整。
- Shanforge 门禁：包含 RED/GREEN、evidence、独立 review、memory 与 ledger。

