# CR-013 Hosted UI 主从表行导航与关联详情页支持

- 状态：DONE
- 类型：CR
- 优先级：P0
- 估算：2.0 人/天
- 关联 ID：`CR-013`, `API-008`
- 提出日期：2026-04-23

## 变更动机

- 当前 Hosted UI V1 的 `Button.action` 只支持 `reload` / `open_page`，但 `DataTable` 不支持行级动作。
- 当前页面跳转只传 `entry`，不传当前记录上下文，目标页/表无法知道“用户点的是哪一条主记录”。
- 当前 `core:data_table` 只能直接展示整个 dataset/resource，不能按导航参数过滤关联记录，因此无法落地标准主从表场景。
- 模块作者若要实现“点击主表记录后看关联详情表”，只能退回自定义 UI 或非正式实现，违背 Hosted UI V1 的收口目标。

## 变更范围

- 为 Hosted UI `DataTable` 和 `core:data_table` 增加正式的行级导航动作能力。
- 为 Hosted UI 页面导航增加受控 `params` 传递，不开放任意脚本或表达式。
- 允许目标 `core:page` 通过 `load_handler(context, page_id, params)` 消费导航参数。
- 允许目标 `core:data_table` 通过受控 schema 声明，按导航参数过滤关联记录。
- 为模块详情页的宿主页实例复用链补齐“同一入口 + 不同参数”的刷新与上下文切换能力。

## 非目标

- 不支持任意 Python/JS 表达式求值。
- 不支持多级联动状态管理或跨页面共享可写状态。
- 不把 `core:data_table` 升级成复杂查询页面或通用搜索 DSL。
- 不在本轮引入树表、嵌套表、抽屉面板或同屏双表布局。

## 方案摘要

- 行级动作统一收口为 `row_action`，其动作类型第一版只开放 `open_page`。
- 导航参数统一收口为受控 `params`，其中行级参数只允许从当前 row 按字段映射提取。
- `ModuleDetailPage` 负责保存并下发当前入口的导航参数；页面实例继续按 menu/page 复用，不为每次点击新建页面。
- `ManagedPageRenderer` 在 `load_handler` 调用时透传当前导航参数。
- `ModuleDataTablePage` 增加基于导航参数的受控过滤能力，用于展示关联详情表。

## 完成判定

- 模块可以声明“点击主表记录 -> 打开另一张 `core:page` 或 `core:data_table`”。
- 目标页能拿到点击记录的参数上下文。
- 目标详情表能按参数过滤关联记录，而不是只能显示全表。
- 同一详情页在连续点击不同主记录时会刷新到最新上下文，不需要关闭重开模块详情页。
- 相关 Core/SDK/unit docs/test/.factory 均同步。
