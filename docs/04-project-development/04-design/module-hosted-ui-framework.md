# 模块宿主管理页与纯 UI 框架设计

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | Core 开发 | SDK 开发 | QA | 模块开发者  
**关联 ID：** `API-002`, `API-008`  
**最后更新：** 2026-04-24

## 1. 结论

模块 UI 已正式收口为“宿主纯 UI 组件 + 外部纯数据”模式。

唯一正式契约如下：

- `module.yaml.ui_extension.pages[]` 只声明左侧导航菜单入口：`id`、`label`、`icon`
- `pages/*.py` 或 `pages/<group>/*.py` 直接导出 `PAGE: PageSpec`，作为可路由页面注册表
- 页面 schema 只允许使用宿主提供的 `Page`、`Section`、`Text`、`Button`、`DataTable`
- 页面数据全部由 `load_handler` 或 `DataTable.query_handler` 返回结构化对象
- 宿主只负责 schema 校验、路由、渲染和通用交互，不再负责模块业务数据语义

本次设计明确删除：

- `entry`
- `core:data_table`
- `ui.declare_data_table`
- `ui.get_data_table`
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
ui_extension:
  pages:
    - id: dashboard
      label: 今日运营看板
      icon: "📊"
    - id: accounts
      label: 账号管理
      icon: "👤"
```

约束：

- `id` 必须是 `snake_case`
- 允许字段只有 `id`、`label`、`icon`
- 清单只描述“宿主导航里有哪些页面”，不描述路由类型

### 4.2 页面源码入口

模块统一在 `pages/*.py` 或 `pages/<group>/*.py` 里导出 `PAGE`：

```python
from crawler4j_contracts import PageSpec

PAGE = PageSpec(
    id="dashboard",
    label="今日运营看板",
    icon="📊",
    schema=build_dashboard_page_schema(),
)
```

不再存在：

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
- `DataTable`

其中：

- `Card` 是正式的卡片容器组件，只负责统一外壳和布局
- `Section` 继续承担普通分组语义
- `Section.variant="card"` 只保留为兼容别名，新的 schema 统一优先使用 `Card`
- `Card` 当前已支持 `title_align`、`content_align`、`content_vertical_align`、`min_height`、`padding`

### 4.4 数据入口

页面数据只有两种正式入口：

1. `load_handler(context, page_id, params=None) -> dict`
2. `query_handler(context, table_id, query, params=None) -> dict`

其中：

- `load_handler` 为页面整体提供数据
- `DataTable` 通过 `binding`、`rows` 或 `query_handler` 获取表格数据
- `query_handler` 负责搜索、排序、分页等表格查询逻辑

### 4.5 动作入口

宿主当前只公开：

- `reload`
- `open_page`

`open_page` 的目标统一为 `page_id`，不再允许 `entry`。

## 5. 责任边界

### 5.1 宿主负责

- 扫描 `pages/` 下的 `PAGE` 页面注册表
- 只用 `ui_extension.pages[]` 渲染左侧菜单
- 校验 `PAGE.schema`
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

- `module.yaml.data.resources[]` + `ctx.db.from_(...)` / `ctx.db.into(...).replace(...)`
- `module.yaml.data.views[]` / `queries[]` + `ctx.db.from_(...)` / `ctx.db.named(...).bind(...).execute()`
- `custom_table` 的已声明联表、分组和聚合查询

这些能力负责数据事实源，但不拥有模块页面结构。

## 6. 持久化与运行时实现

### 6.1 页面 schema 生命周期

正式 Hosted UI 链路直接扫描 `pages/` 下导出的 `PAGE`，并把所有页面注册到运行时 descriptor。`module.yaml.ui_extension.pages[]` 只影响左侧菜单，不是页面注册表。

不再把以下对象作为正式渲染事实源：

- `data.db.module_pages`
- `module_data_table_views`

### 6.2 运行时工具面

保留：

- `ui.get_page`

删除：

- `ui.declare_page`
- `ui.declare_data_table`
- `ui.get_data_table`

### 6.3 模块详情页

模块详情页只按 `page_id` 打开页面：

- 菜单项来自 `ui_extension.pages[]`
- 页面实例来自 `pages/` 中导出的 `PAGE`
- 页面跳转统一走 `open_page(page_id, params)`
- `open_page` 可打开任意已注册 `PAGE`，不要求目标页面配置为菜单项

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

- `page create`，默认创建菜单页面；`--no-menu` 只创建可路由页面文件
- `page list`

删除：

- `data-table create`
- `data-table list`

`check full` 需要校验：

- `ui_extension.pages[]` 是否合法
- `ui_extension.pages[]` 中的菜单页面是否存在对应 `PAGE`
- 每个页面文件是否导出合法且唯一的 `PAGE`
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
