# 模块宿主管理页与纯 UI 框架设计

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | Core 开发 | SDK 开发 | QA | 模块开发者  
**关联 ID：** `API-002`, `API-008`, `API-019`, `API-023`
**最后更新：** 2026-07-15

## 1. 结论

模块 UI 已正式收口为“宿主纯 UI 组件 + 外部纯数据”模式。

唯一正式契约如下：

- `pages/*.py` 或 `pages/<group>/*.py` 使用 `@page(...)` 装饰页面 load handler，作为唯一页面注册表
- `@page(menu=True)` 声明左侧导航菜单入口；`menu=False` 只注册可路由页面
- 页面 schema 只允许使用宿主提供的 `Page`、`Card`、`Section`、`Text`、`Input`、`Select`、`Button`、`DataTable`
- 页面数据全部由 `load_handler` 或 `DataTable.query_handler` 返回结构化对象
- 页面业务按钮和 CRUD handler 通过 `@ui_action` 声明的函数执行，参数按 kwargs 绑定；CRUD 的主键参数名来自 `crud.primary_key`，SDK 扫描期校验 create/update/delete handler 的确定签名和输入类型注解
- 页面级和 `DataTable` 工具栏可声明自定义按钮；批量导入这类宿主复合动作由 `API-019` 定义，宿主负责读取 Excel/CSV/剪贴板并只把结构化 payload 交给模块
- `@page_action` 只服务 workflow/component 驱动的浏览器页面操作，Hosted UI schema 不接受 `page_action`
- 宿主只负责 schema 校验、路由、渲染和通用交互，不再负责模块业务数据语义

本次设计明确删除：

- `entry`
- `core:data_table`
- `ui.declare_data_table`
- `ui.get_data_table`
- `module.yaml.ui_extension`
- `PageSpec`
- 独立数据表页面持久化
- 任何兼容桥或旧边界保留措施

## 2. 背景

旧 Hosted UI V1 仍然保留了“宿主页 + 宿主管理数据表页”双入口模型。这个模型存在三个问题：

1. UI 路由和数据语义绑定过深，宿主需要理解模块的数据表模式。
2. 模块无法真正按“外部组装页面、宿主纯渲染”的边界工作。
3. `entry`、`core:data_table`、`ui.declare_data_table` 会把页面导航、表格容器和数据语义耦合成一套难以演进的协议。

新要求是：

- 宿主 UI 模块只提供纯 UI 模式
- 所有页面组装逻辑和数据都由外部实现
- 不保留任何兼容层

因此，本次重构不是“给旧模型补一个新写法”，而是彻底删除旧模型。

## 3. 设计目标

### 3.1 必达目标

- 模块 UI 只剩页面声明，不再有页面类型分叉
- 宿主只公开纯 UI 组件契约
- 页面数据全部由模块或 Core 其它模块提供
- 宿主不再处理模块数据表业务语义
- CLI、运行时、持久化、模块详情页、文档和测试全部切到新契约

### 3.2 非目标

- 不做旧模块兼容
- 不保留 `entry` 到 `page_id` 的桥接
- 不保留旧数据表页存储、路由、刷新链
- 不在第一版开放自定义前端运行时

## 4. 核心契约

### 4.1 Manifest

```yaml
runtime_api: core-native-v2
name: hotel_demo
version: 0.1.0
upgrade_source:
  repo: your-org/hotel_demo
```

约束：

- `module.yaml` 不再声明页面、菜单或 UI 扩展
- 运行能力和页面都由装饰器扫描发现
- 如果出现 `ui_extension`，SDK/Core 应按已移除字段拒绝

### 4.2 页面源码入口

模块统一在 `pages/*.py` 或 `pages/<group>/*.py` 里用 `@page` 装饰页面 load handler：

```python
from crawler4j_contracts import TaskContext, page

@page(
    name="dashboard",
    label="今日运营看板",
    icon="📊",
    menu=True,
    schema={
        "type": "Page",
        "title": "今日运营看板",
        "children": [],
    },
)
def load_dashboard_page(
    context: TaskContext,
    page_id: str,
    params: dict | None = None,
) -> dict:
    ...
```

不再存在：

- `PAGE: PageSpec`
- `module_runtime.py` 里的 `declare_ui`
- `ui.declare_page`
- `ui.declare_data_table`
- `ui.get_data_table`

### 4.3 页面 schema

页面 schema 的顶层固定为：

- `type="Page"`
- `title`
- `load_handler`
- `children`
- `layout`

组件固定为：

- `Page`
- `Card`
- `Section`
- `Text`
- `Button`
- `Input`
- `Select`
- `DataTable`

其中：

- `Card` 是正式的卡片容器组件，只负责统一外壳和布局
- `Section` 继续承担普通分组语义
- `Section.variant="card"` 只保留为兼容别名，新的 schema 统一优先使用 `Card`
- `Card` 当前已支持 `title_align`、`content_align`、`content_vertical_align`、`min_height`、`padding`

### 4.4 数据入口

页面数据只有两种正式入口：

1. `load_handler(context, page_id, params=None) -> dict`
2. `query_handler(context, query: HostedDataTableQuery) -> HostedDataTableQueryResult`

其中：

- `load_handler` 为页面整体提供数据
- `DataTable` 通过 `binding`、`rows` 或 `query_handler` 获取表格数据
- `query_handler` 负责搜索、排序、分页等表格查询逻辑；`DataTable.columns` 中的搜索和排序列必须分别显式声明 `searchable=True` / `sortable=True`；`DataTable.table_id` 只用于宿主识别页面内组件，不作为 handler 入参，也不表示数据库资源名

### 4.5 动作入口

宿主当前只公开：

- `reload`
- `open_page`
- `ui_action`

普通 `Button.action` 的页面跳转目标统一为 `page_id`，不再允许 `entry`。页面 / `DataTable` toolbar 额外支持 `workflow` 和 `open_import_dialog`，用于后台任务和批量导入这类宿主复合动作。

### 4.6 Toolbar 与批量导入入口

页面和 `DataTable` 可声明 `toolbar.actions[]`，用于放置页面级或表格级自定义按钮。普通用户命令继续优先走 `@ui_action`；需要启动长耗时流程时，可由宿主调度 workflow；需要导入本地文件或剪贴板数据时，必须通过宿主导入弹窗。

批量导入入口遵守以下边界：

- 模块 schema 只声明按钮、`target_type` 和提交动作，不读取本地文件。
- 宿主导入弹窗读取 `.xlsx/.csv`、剪贴板或可选手工输入，并转换为标准 import payload。
- 宿主只把 `source_type/source_name/target_type/rows[]` 结构化数据交给模块，不传本地路径、文件句柄或二进制内容。
- `@page_action` 不参与 Hosted UI 批量导入；浏览器页面动作仍只由 workflow/component 通过 `ctx.run_page_action(...)` 调用。

详细协议见 [Hosted UI 批量导入方案](hosted-ui-batch-import-design.md)。

## 5. 责任边界

### 5.1 宿主负责

- 扫描 `pages/` 下的 `@page` 页面声明
- 只用 `@page(menu=True)` 渲染左侧菜单
- 校验 `@page.schema`
- 基于 `page_id` 做页面路由和刷新，允许跳转到未出现在左侧菜单的详情页或二级页
- 渲染宿主控件
- 执行通用表格交互和按钮动作

### 5.2 模块负责

- 组装页面 schema
- 实现 `load_handler`
- 实现内联表格 `query_handler`
- 调用 `ctx.db` fluent API 和其它 Core 能力准备页面数据
- 处理业务动作与数据语义

### 5.3 Core 其它能力负责

- `@data_table` + `ctx.db.from_(...)` / `ctx.db.into(...).replace(...)`
- `@data_view` + `ctx.db.from_("view_id").execute()`
- `custom_table` 的已声明联表、分组和聚合查询

这些能力负责数据事实源，但不拥有模块页面结构。

## 6. 持久化与运行时实现

### 6.1 页面 schema 生命周期

正式 Hosted UI 链路直接扫描 `pages/` 下的 `@page` 装饰器，并把所有页面注册到 v2 运行时 descriptor。`@page(menu=True)` 只影响左侧菜单，不是页面注册表边界。

不再把以下对象作为正式渲染事实源：

- `data.db.module_pages`
- `module_data_table_views`

### 6.2 运行时工具面

保留：

- `ui.get_page`
- `ui.form.reset`，仅在 Hosted UI action surface 注册；只有绑定当前 Form change 事件的 handle 可执行

DataTable CRUD Form 可选使用 `crud.form.layout={"columns": 1|2|3, "gap": <非负整数>}` 声明通用多列网格；省略时保持一列。renderer 按字段顺序逐行填充，并根据屏幕可用宽度降列，滚动内容与固定操作区的职责不变。

删除：

- `ui.declare_page`
- `ui.declare_data_table`
- `ui.get_data_table`

公共字段事件、Form scope、安全 handle 与 reset 的完整协议见 [Hosted UI 公共字段事件与 Form Reset 设计](hosted-ui-form-field-events.md)。

### 6.3 模块详情页

模块详情页只按 `page_id` 打开页面：

- 菜单项来自 `@page(menu=True)`
- 页面实例来自 `pages/` 中的 `@page` 声明
- 页面跳转统一走 `open_page(page_id, params)`
- `open_page` 可打开任意已注册页面，不要求目标页面配置为菜单项

## 7. `DataTable` 的位置

`DataTable` 现在只是页面组件，不再是宿主页型。

它承担两类场景：

- 只读列表 / 统计表
- 可编辑业务表格

但不再承载以下宿主职责：

- 数据资源路由规则
- 独立页面事实源
- 业务 CRUD 语义判定

这些都回到模块或 `ctx.db` 能力层处理。

## 8. CLI 与校验链

CLI 只保留：

- `page create`，默认生成 `@page(menu=True)`；`--no-menu` 生成 `@page(menu=False)`
- `page list`

删除：

- `data-table create`
- `data-table list`

`check full` 需要校验：

- `module.yaml` 没有 `ui_extension`
- 每个页面文件是否声明合法且唯一的 `@page`
- `@page.schema` 是否合法
- `load_handler` 是否存在且同步
- 内联表格 `query_handler` 是否存在且同步

## 9. 迁移结论

当前纯 UI 契约已经是唯一正式实现。任何旧式：

- `entry`
- `core:data_table`
- `ui.declare_data_table`
- 数据表页面兼容路由
- 数据表 schema 独立存储

都已被视为遗留实现并正式删除。
