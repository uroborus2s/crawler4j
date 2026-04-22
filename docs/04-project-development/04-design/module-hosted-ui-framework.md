# 模块宿主管理页与最小化 UI 框架设计

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | Core 开发 | SDK 开发 | QA | 模块开发者  
**上游输入：** `system-architecture.md` | `module-boundaries.md` | `api-design.md` | `ctrip_crawler` UI 现状分析  
**下游输出：** `docs/04-project-development/05-development-process/implementation-plan.md` | `docs/04-project-development/06-testing-verification/test-plan.md` | `docs/03-developer-guide/ui-and-data-table.md`
**关联 ID：** `API-002`, `API-008`, `CR-011`
**最后更新：** 2026-04-22

## 1. 背景

当前模块 UI 接入仍保留“模块直接导出 `ui:*` 页面类，由宿主动态实例化真实 `QWidget`”的链路。这个链路带来三个结构性问题：

- 模块作者可以直接依赖 `PyQt6`，UI 契约实际上等同于“允许外部模块执行宿主 UI 代码”。
- 宿主必须额外维护 trust gate / allowlist，才能在安装模块与 DevLink 调试之间做来源级放行。
- SDK `page create`、模块 manifest、MMS 页面加载器和开发者文档都围绕代码型页面展开，导致宿主 UI 与模块代码强耦合。

这与当前的新要求冲突：

- 模块不得直接使用 `PyQt6`。
- 模块只能使用宿主提供的 UI 组件。
- 宿主不再为模块 UI 做安全拦截，而是从契约层禁止外部 UI 代码注入。

因此，本次重构不是“替换几个 import”，而是替换整条模块 UI 契约。

## 2. 设计目标

### 2.1 必达目标

- 废弃 `micro_app` / `ui:*` / `QWidget` 注入链路。
- 模块只声明宿主管理页 schema，由宿主统一渲染。
- 模块 UI 公开能力收口为最小化框架 V1，不做通用前端运行时。
- 宿主移除 trust gate、allowlist 和 `trusted` 语义。
- `ctrip_crawler` 当前所有页面都能由第一版宿主控件完整承载。

### 2.2 非目标

- 不做旧模块兼容。
- 不保留代码型页面脚手架。
- 不开放任意模块 action handler、任意表达式或任意自定义组件。
- 不在第一版支持图表、树、标签页、富文本、文件上传、日期选择器等复杂控件。

## 3. 核心决策

### 3.1 UI 契约从“模块返回控件”改为“模块声明页面”

模块不再向宿主返回任何 `QWidget`、`QDialog` 或其他 `PyQt6` 对象。模块只能通过运行时工具声明：

- `ui.declare_page(page_id, schema=...)`
- `ui.declare_data_table(view_id, schema=...)`

宿主只识别两类入口：

- `core:page:<page_id>`
- `core:data_table:<view_id>`

宿主内部仍可继续使用 `PyQt6` 实现真实界面，但这是宿主内部技术栈，不再是模块公开契约的一部分。

### 3.2 UI Extension 统一改为 pages 列表

`ui_extension` 不再声明 `type`、`entry`、`detail_menu`、`trusted` 等旧字段，而是统一收口为页面清单：

```yaml
ui_extension:
  pages:
    - id: dashboard
      label: 今日运营看板
      icon: "📊"
      entry: "core:page:dashboard"
    - id: accounts
      label: 账号管理
      icon: "👤"
      entry: "core:data_table:accounts"
    - id: labor_accounts
      label: 劳保账号管理
      icon: "🛠"
      entry: "core:data_table:labor_accounts"
    - id: xc_accounts
      label: XC 账号管理
      icon: "🧩"
      entry: "core:data_table:xc_accounts"
```

页面列表既描述模块详情页导航，也约束宿主允许加载的 UI 类型。

### 3.3 第一版公开控件固定为 5 个

基于 `ctrip_crawler` 的真实 UI 面，第一版宿主公开控件只需要：

- `Page`
- `Section`
- `Text`
- `Button`
- `DataTable`

其中 `DataTable` 是复合控件，而不是一个“表格壳”。

### 3.4 DataTable 内建两种模式

- `readonly`
  - 用于 dashboard 内部的只读统计表。
- `managed_crud`
  - 用于宿主托管的记录管理页，支持新增、编辑、删除、刷新。

`managed_crud` 的第一版字段类型最少支持：

- `text`
- `number`
- `int`
- `bool`
- `select`

第一版明确不支持：

- `date` / `datetime`
- `radio` / `checkbox`
- `tree`
- `chart`
- `file_upload`
- `rich_text`

### 3.5 页面动作只开放宿主内建动作

为避免第一版又回到“宿主执行任意模块 UI 代码”，`Button.action` 只开放少量宿主内建动作：

- `reload`
- `open_page`

页面展示数据通过同步本地 hook 加载，不开放通用事件脚本。

## 4. 页面与数据契约

### 4.1 模块运行时声明入口

模块统一在 `module_runtime.py` 里通过 `declare_ui(ctx)` 声明页面和数据表：

```python
def declare_ui(ctx):
    ctx.tools.call("ui.declare_page", page_id="dashboard", schema=build_dashboard_page_schema())
    ctx.tools.call("ui.declare_data_table", view_id="accounts", schema=build_account_table_schema())
    ctx.tools.call("ui.declare_data_table", view_id="labor_accounts", schema=build_labor_account_table_schema())
    ctx.tools.call("ui.declare_data_table", view_id="xc_accounts", schema=build_xc_account_table_schema())
```

### 4.2 宿主页 schema 示例

```python
def build_dashboard_page_schema():
    return {
        "type": "Page",
        "layout": {"direction": "column", "gap": 16},
        "load_handler": "load_dashboard_page",
        "children": [
            {
                "type": "Section",
                "variant": "plain",
                "children": [
                    {"type": "Text", "style": "title", "text": "今日运营看板"},
                    {"type": "Text", "style": "subtitle", "text": "账号与黑号状态总览"},
                    {"type": "Button", "label": "刷新", "action": {"type": "reload"}},
                ],
            },
            {
                "type": "Section",
                "title": "核心指标",
                "layout": {"kind": "grid", "columns": 4},
                "children": [],
            },
        ],
    }
```

第一版 schema 只允许使用宿主固定字段和固定组件类型，不支持模块自定义扩展字段解释器。

### 4.3 数据加载规则

页面 schema 上的 `load_handler` 指向模块本地同步 hook：

```python
def load_dashboard_page(ctx, page_id, params=None) -> dict:
    ...
```

返回值是纯结构化数据，由宿主完成：

- 绑定到 `Text`、指标卡和只读表格
- 处理空态和异常态
- 触发 `reload` 后重新加载

模块可以继续提供数据聚合 helper，但 helper 只返回数据，不参与 UI 渲染。

## 5. 最小化 UI 框架 V1

### 5.1 `Page`

- 顶层滚动容器。
- 支持 `column`、`row`、`grid` 三种布局属性。
- 第一版不单独公开布局组件，布局只作为 `Page` / `Section` 属性存在。

### 5.2 `Section`

- 带标题的分组容器。
- 支持 `plain`、`group`、`card` 三种外观。
- 可嵌套 `Text`、`Button`、`DataTable` 和其他 `Section`。

### 5.3 `Text`

- 支持 `title`、`subtitle`、`body`、`meta` 四种样式。
- 支持固定文本和简单数据绑定。
- 第一版不支持富文本、Markdown 渲染和可编辑文本。

### 5.4 `Button`

- 只提供普通动作按钮。
- 当前只需要 `reload` 和 `open_page` 两种动作。
- 宿主负责 loading、去重点击和错误提示。

### 5.5 `DataTable`

- 统一承担只读表格和宿主管理表格两类场景。
- 内建：
  - 列定义
  - 显示字段
  - `create_fields` / `update_fields`
  - 必填校验
  - `add` / `edit` / `delete` / `refresh`
  - `create_handler` / `update_handler`

第一版不再额外对模块暴露 `Form`、`Modal`、`Field` 等独立控件；这些都内聚在 `DataTable(managed_crud)` 内部。

## 6. `ctrip_crawler` 覆盖性验证

### 6.1 当前页面范围

`ctrip_crawler` 当前需要承载的页面只有四个：

- `dashboard`
- `accounts`
- `labor_accounts`
- `xc_accounts`

其中后三个已经天然符合宿主托管数据表模式。

### 6.2 Dashboard 映射

当前 dashboard 的实际结构可直接映射到 V1：

- 标题、副标题 -> `Text`
- 刷新按钮 -> `Button(action=reload)`
- 4 个 KPI 卡片 -> `Section(card)` + `Text`
- 2 张只读统计表 -> `DataTable(readonly)`
- 页脚说明 -> `Text(meta)`

因此，`ctrip_crawler` 不需要额外要求：

- 图表控件
- 标签页
- 任意表单页面
- 任意脚本交互
- 模块自定义绘制

## 7. 宿主侧重构边界

### 7.1 必须新增

- `ui.declare_page`
- `ui.get_page`
- 宿主页 schema 存储
- `ManagedPageRenderer`
- 宿主页数据加载与刷新调度

### 7.2 必须删除

- `micro_app`
- `ui:*`
- `ModuleCustomPageLoader`
- trust gate / allowlist / `trusted`
- 代码型页面脚手架和 `ui/` 目录作为正式契约

### 7.3 不需要重写

- 宿主内部 `PyQt6` 技术栈
- ATM / workflow / task 执行链
- 已存在的 `core:data_table` 持久化与 CRUD 机制本体

## 8. 旧代码清理清单

### 8.1 Core / 宿主

- 删除模块详情页中的代码型页面加载分支。
- 删除 `ui_loader.py` 与相关异常类型。
- 删除 `mms.ui.allowlist` 设置项、配置入口和错误提示文案。
- 删除以模块来源为依据的 UI 安全放行逻辑。

### 8.2 SDK / CLI

- 删除 `page create` 生成 `PyQt6` 页面模板的能力。
- 删除 `micro_app` 与 `ui:PageClass` 校验逻辑。
- 把页面脚手架改成 `declare_ui()` + `build_*_page_schema()` 骨架。

### 8.3 模块模板与开发文档

- 删除示例模块中的 `ui/` 目录。
- 删除所有“模块直接 import `PyQt6`”的开发文档、代码样例和脚手架说明。
- 把“代码型页面”从正式开发者指南中移除，改为宿主页和数据表双路径。

### 8.4 `ctrip_crawler`

- 删除 `ui/dashboard.py`
- 删除 `ui/__init__.py`
- 将 dashboard 改为宿主页 schema + `load_dashboard_page()`

## 9. 实施拆分与难度

### 9.1 工作包

1. 契约层
   - 重写 `ui_extension` 数据模型和 manifest 解析。
   - 新增 `ui.declare_page` 契约。
2. 宿主渲染层
   - 新增宿主页存储和渲染器。
   - 重写模块详情页入口装配。
3. SDK 与脚手架
   - 重写 `page create`
   - 重写 `check structure/full` 对 UI 契约的校验
4. 模块样板与验收
   - 以 `ctrip_crawler` 迁移为第一批样板
   - 补齐对应文档和测试

### 9.2 复杂度评估

- 不做兼容后，整体属于中等规模重构，不是平台级重写。
- 若严格按 V1 最小控件集收口，预计 `5.5-7.5` 人天。
- 最大风险不在代码实现，而在于第一版 schema 是否被设计得过宽。

## 10. 验收标准

- 仓内不再存在模块 `ui:*` 页面加载链路。
- 仓内不再存在对外模块 UI 的 trust gate / allowlist。
- SDK 与文档不再指导模块作者编写 `PyQt6` 页面。
- `ctrip_crawler` 的 dashboard 和 3 张账号表可完全由宿主控件承载。
- 第一版公开控件稳定固定为 `Page`、`Section`、`Text`、`Button`、`DataTable`。
- `DataTable` 的 V1 字段类型固定为 `text`、`number`、`int`、`bool`、`select`。
- 文档、memory 与后续实施计划基于同一口径推进，不再保留“旧方案仍是正式契约”的模糊表述。

## 11. 设计结论

模块 UI 重构的关键不在“换一个 UI 库名”，而在于切断宿主执行外部 UI 代码的权力。只要模块还能把真实控件对象交给宿主，安全拦截就删不掉；只有把模块 UI 收口为宿主页 schema，trust gate 才能从根上消失。

`ctrip_crawler` 证明第一版不需要复杂组件系统。以 `Page`、`Section`、`Text`、`Button`、`DataTable` 这 5 个宿主控件为边界，已经足够承载当前真实业务模块页面，并且能把后续实现范围压在可控区间内。

## 12. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-22 | 新增正式设计页，收口模块宿主管理页与最小化 UI 框架 V1 的重构方案 | Codex |
