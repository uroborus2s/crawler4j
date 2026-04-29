# TASK-027 实现 Hosted UI 主从表行导航与关联详情页能力

- 状态：DONE
- 负责人：Codex
- 优先级：P0
- 估算：2.0 人/天
- 关联 ID：`TASK-027`, `CR-013`, `API-008`

## 目标

- 让 Hosted UI 的表格组件支持“点击主表记录后打开关联详情表/页”的正式交互。
- 保持 Hosted UI V1 的收控边界，不重新引入自定义 UI 代码执行。
- 在不打散现有页面实例复用链的前提下，补齐参数化导航。

## 范围

- SDK Hosted UI schema：
  - 行级动作 `row_action`
  - 受控导航 `params`
  - 详情表按导航参数过滤的 schema 声明
- Core UI：
  - `ManagedPageRenderer` 行点击导航
  - `ModuleDataTablePage` 行点击导航与参数过滤
  - `ModuleDetailPage` 路由参数分发、同页刷新
- 测试：
  - `ManagedPageRenderer`
  - `ModuleDataTablePage`
  - `ModuleDetailPage`
  - 必要时 Hosted UI/runtime capability 定向回归
- 文档与 memory 同步：
  - Hosted UI 设计/开发者文档
  - `implementation-plan.md`
  - `test-plan.md`
  - `execution-log.md`
  - `.factory/memory/current-state.md`

## 非目标

- 不引入复杂查询语言。
- 不提供任意动作类型，行级动作第一版只支持导航。
- 不承诺本轮支持同屏 master-detail 布局。

## 验收标准

- 行点击可打开目标 `core:page` / `core:data_table`。
- 导航参数可由主表当前 row 受控映射生成并传到目标页面。
- `load_handler` 能收到 params，`core:data_table` 能基于 schema 过滤 records。
- 同一目标页在不同主记录之间切换时不会残留旧 params。
- 相关单测通过，现有 Hosted UI V1 回归不破坏。
