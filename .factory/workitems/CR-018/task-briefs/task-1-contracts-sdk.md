# 任务 1 简报：Contracts 与 SDK 契约

## 工作项

- 工作项：`CR-018`
- 父任务：`TASK-036`
- 状态：`approved`
- 依赖：无
- 上游：`.factory/workitems/CR-018/brief.md`

## 目标

让 Hosted UI schema 严格接受 `selection_mode`、`bulk_update_handler`、`toolbar.bulk_update`，并让 SDK scanner 对批量 handler 引用、固定签名和宽泛参数类型给出明确诊断。

## 设计、接口、UI、测试

- 设计方案：只扩展现有 DataTable CRUD TypedDict、normalizer 和 `_validate_page_crud_handlers()`。
- 接口：`bulk_update_handler(context, primary_keys, payload)`，其中 `primary_keys` 必须为带具体元素类型的 `list[T]` / `List[T]`，payload 沿用现有 CRUD 的具体类型检查边界。
- UI：N/A；本任务不渲染界面，只定义 schema 与静态诊断。
- 测试：先新增 selection 默认 / 非法值、bulk toolbar 默认 / 显式关闭 / 缺 handler 组合、缺 primary key / update columns、合法 / 非法 handler 签名与类型用例并确认 RED，再写最小 GREEN。

必须逐条断言：

- `bulk_update_handler` 存在且 toolbar 开关省略时保留默认显示语义，显式 `False` 保留关闭语义。
- `toolbar.bulk_update=True` 缺 handler，以及 handler 缺 `primary_key` / 非空 `update_columns` 时产生明确的 Contracts / scanner 错误路径。
- 首参必须精确命名 `context`；`ctx`、错序、默认参数、kw-only、`*args` / `**kwargs` 均失败。
- `primary_keys` 接受 `list[str]`、`list[int]`、`List[T]`；拒绝无注解、裸 `list`、`list[Any]`、`Any`、`Mapping`。
- payload 沿用现有 CRUD 约束，拒绝裸 `dict`、`Mapping`、`Any`。

## 允许修改

- `packages/crawler4j-contracts/src/crawler4j_contracts/hosted_ui.py`
- `packages/crawler4j-sdk/src/v2_scanner.py`
- `packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py`
- `packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py`
- `.factory/workitems/CR-018/evidence/task-1.md`
- `.factory/workitems/CR-018/reports/task-1.md`

## 禁止修改

- Core Renderer、数据库层、业务模块、正式文档和 memory。

## 验证命令

```bash
uv run pytest packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py -q -p no:cacheprovider
uv run ruff check packages/crawler4j-contracts/src/crawler4j_contracts/hosted_ui.py packages/crawler4j-sdk/src/v2_scanner.py packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py
```

期望：新增用例和既有 CRUD scanner 用例全部通过，ruff 无错误。

## 输出与状态

- 写 RED / GREEN 真实命令结果到 `evidence/task-1.md`。
- 写实现、文件和自检到 `reports/task-1.md`。
- 实现者最多返回 `ready_for_review`，不得自批 approved。
