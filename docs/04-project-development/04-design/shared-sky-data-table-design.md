# 共享表格组件 SkyDataTable 重构设计

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | Core 开发 | UI 开发 | QA | 模块开发者  
**上游输入：** `module-hosted-ui-framework.md` | `CR-013` | 现有宿主表格与 Hosted UI 表格分裂现状  
**下游输出：** `implementation-plan.md` | `test-plan.md` | `CR-015` | `TASK-029`  
**关联 ID：** `API-010`, `CR-015`, `TASK-029`  
**最后更新：** 2026-04-23

## 1. 背景

当前仓库里存在两套表格路径：

- 宿主内部页面主要使用旧 `SkyDataTable`，但它依赖 `set_data`、`set_render_callback` 与内部客户端过滤逻辑。
- 模块 Hosted UI 的 `core:data_table` 和内联 `DataTable` 仍直接使用 `SkyTableWidget`，没有统一查询状态和纯 UI 边界。

这导致三个问题：

- 表格边界不清晰，组件同时承担了渲染、搜索和局部数据处理职责。
- 搜索、排序、分页没有统一的查询契约。
- 宿主和模块不能共享同一套表格组件与列定义方式。

## 2. 设计目标

### 2.1 必达目标

- 仓库内只保留一套正式共享表格组件：`SkyDataTable`
- 组件是纯 UI，不直接查数据库、不直接调用模块 runtime
- 搜索、排序、分页统一转化为查询请求
- 外部 provider / adapter 负责取数并把结果回灌给组件
- 宿主内部表格和模块 Hosted UI 表格都使用同一套组件
- 删除旧 `SkyDataTable` 业务 API 与 `SkyTableWidget` 业务组件

### 2.2 非目标

- 不保留旧 schema 兼容层
- 不保留 `set_render_callback`
- 不在组件内部实现 `managed_resource` / `query_handler` 的数据访问
- 不把数据库视图能力和本次共享组件重构绑成一个任务

## 3. 核心决策

### 3.1 组件边界固定为纯 UI

`SkyDataTable` 只负责：

- 搜索框
- 列头排序状态
- 分页条
- loading / empty / error 展示
- 行点击与行级动作事件
- 查询状态维护与查询请求发射

`SkyDataTable` 不负责：

- 查询数据库
- 调模块 hook
- 组装业务行数据
- 决定 CRUD 行为

### 3.2 统一查询契约

组件向外发出的查询输入：

```python
{
    "search_text": "abc",
    "sort": [{"field": "updated_at", "direction": "desc"}],
    "page": 1,
    "page_size": 20,
    "params": {"account_id": "A-001"},
}
```

外部 provider 返回的结果：

```python
{
    "rows": [...],
    "total": 123,
    "page": 1,
    "page_size": 20,
}
```

组件使用 `request_id` 丢弃过期返回，避免异步乱序覆盖。

### 3.3 统一列契约

列定义固定为声明式 schema，不再允许 render callback。

V1 支持列类型：

- `text`
- `number`
- `bool`
- `badge`
- `actions`

其中 `actions` 列的数据来自行级动作数组，点击后组件只发 `row_action_requested(action_id, row)`。

### 3.4 统一宿主适配层

组件统一，但 provider 不统一：

- 宿主内部页面：页面自己维护 provider，常见模式是“加载本地列表 -> 本地过滤/排序/分页 -> 回灌组件”
- `core:data_table`：由 `ModuleDataTablePage` 适配 `managed_resource` / `query_handler`
- 内联 `DataTable`：由 `ManagedPageRenderer` 适配 `binding` / `rows` / `query_handler`

## 4. 组件 API

正式共享组件 API：

```python
class SkyDataTable(QWidget):
    query_requested = pyqtSignal(int, dict)
    row_clicked = pyqtSignal(dict)
    row_action_requested = pyqtSignal(str, dict)
    selection_changed = pyqtSignal(list)

    def set_schema(self, schema: dict) -> None: ...
    def set_query(self, query: dict) -> None: ...
    def request_refresh(self) -> None: ...
    def apply_result(self, request_id: int, result: dict) -> None: ...
    def apply_error(self, request_id: int, message: str) -> None: ...
    def set_loading(self, loading: bool) -> None: ...
```

旧 API `set_data`、`set_render_callback`、`add_widget_to_toolbar` 全部删除。

## 5. Hosted UI 新契约

### 5.1 `core:data_table`

`ui.declare_data_table` 新 schema 固定为：

- `title`
- `columns`
- `features`
- `data_source`
- `row_action`
- `crud`

其中：

- `data_source.type=managed_resource` 由宿主读取正式资源并提供默认 CRUD
- `data_source.type=query_handler` 由模块自己提供查询回调，默认只读

### 5.2 内联 `DataTable`

页面组件 `DataTable` 新 schema 固定为：

- `table_id`
- `columns`
- `features`
- `data_source`
- `row_action`

`data_source.type` 支持：

- `binding`
- `rows`
- `query_handler`

内联 `DataTable` 必须显式声明 `data_source`，不再接受顶层 `binding` / `rows` 兼容写法。

## 6. 实施步骤

1. 新建 `CR-015 / TASK-029`，固化破坏性重构边界
2. 重写 `SkyDataTable`
3. 删除旧 `SkyTableWidget`
4. 迁移宿主内部正式表格页面
5. 重写 Hosted UI DataTable schema 与宿主 adapter
6. 清理旧测试与旧文档，补齐新组件和 Hosted UI 定向回归
7. 同步 `docs/`、`.factory/memory/` 与执行记录

## 7. 验收标准

- 仓库正式用户可见表格统一使用 `SkyDataTable`
- 组件内部没有任何数据库访问和模块 runtime 调用
- 搜索、排序、分页统一通过查询请求触发
- 宿主和模块共享同一套列定义与结果结构
- 旧表格组件和旧 schema 已删除
