# CR-018 Review Feedback Triage

## CR-018-SPEC-001

- 反馈来源：task review
- 文件：`packages/crawler4j-contracts/src/crawler4j_contracts/hosted_ui.py`
- severity：Important
- 原文：`selection_mode` 被实现到 `crud`，但来源契约要求它位于 `DataTable` 顶层。

### 理解与核实

- 反馈要求：把允许键、TypedDict 和规范化从 `DataTableCrudSchema` 移到 `DataTableSchema` / `_normalize_inline_table_schema()`，并让无 CRUD 的 DataTable 也默认得到 `single`。
- 是否清楚：yes
- 是否技术正确：yes
- 证据：来源示例把 `selection_mode` 与 `table_id/columns/crud` 并列；当前 diff 未修改 `ALLOWED_INLINE_TABLE_SCHEMA_KEYS` 和 `DataTableSchema`，因此正确来源 schema 仍会被拒绝。
- 是否破坏既有功能：no；新字段尚未发布，省略时继续为 `single`。
- 是否与用户决策冲突：no
- 是否违反 YAGNI：no

### 处理决定

- Fixed：退回 task 1，以顶层 DataTable 契约补 RED/GREEN。

## CR-018-SPEC-002

- 反馈来源：task review
- 文件：`packages/crawler4j-sdk/src/v2_scanner.py`
- severity：Important
- 原文：`primary_keys` 检查会放行 `List[T]` 的 TypeVar 和 `list[str, int]`，不满足单一具体元素类型。

### 理解与核实

- 反馈要求：参数化列表必须恰好一个类型实参，拒绝模块内声明的 TypeVar；合法大写 `List` 用 `List[str]` / `List[int]` 覆盖。
- 是否清楚：yes
- 是否技术正确：yes
- 证据：当前 helper 只判断 `ast.Subscript` 根名与 slice 的宽泛类型；`Name("T")` 会被当作具体标量，`ast.Tuple` slice 也未被拒绝。
- 是否破坏既有功能：no；这是尚未发布的新 bulk handler 诊断，既有 CRUD 不使用该 helper。
- 是否与用户决策冲突：no
- 是否违反 YAGNI：no；只补来源明确要求的类型边界，不引入跨文件类型解析器。

### 处理决定

- Fixed：收集当前模块 `TypeVar(...)` 声明名或采用等价的最小静态判断，拒绝 TypeVar 与非单参数列表；补对应 RED/GREEN。

## CR-018-OVERALL-001

- 反馈来源：independent overall review
- 文件：`docs/04-project-development/04-design/api-design.md`
- severity：Important
- 原文：`API-021` 章节被插入到尚未结束的 `API-019` 表格中，导致后半段批量导入契约错误归属到 `API-021`。

### 理解与核实

- 反馈要求：保持 `API-019` 表格完整，把整段 `API-021` 移到 `API-019` 最后一行之后，再进入下一个 API 章节。
- 是否清楚：yes
- 是否技术正确：yes
- 证据：当前文件在 `API-019` 的“动作类型”行后出现 `## API-021`，而后续“导入来源 / Payload / 导入结果”等显然属于 `API-019` 的行落在新标题下。
- 是否破坏既有功能：no；只修正式文档结构，不改代码或契约内容。
- 是否与用户决策冲突：no
- 是否违反 YAGNI：no

### 处理决定

- Fixed：只移动 `API-021` 章节位置；重跑 docs-stratego、`git diff --check` 和目标文档结构核对，再交原整体 reviewer 复审。
