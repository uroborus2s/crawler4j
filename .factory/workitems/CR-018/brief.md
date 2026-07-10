# Hosted UI DataTable 多选批量编辑需求简报

- 项目：crawler4j
- Work item：`CR-018`
- 状态：`requirements_ready`（用户已明确要求按来源设计实现）
- 场景：`add_requirement`
- 版本：`0.1.0`
- 日期：2026-07-10
- 来源：用户指定的 `core-hosted-datatable-multi-select-bulk-update-request.md`

## 目标与用户故事

作为 Hosted UI 运营人员，我希望在当前页勾选一条或多条 `managed_dataset` 记录并一次修改相同字段，以便避免逐条编辑；作为模块开发者，我希望 Core 只传主键数组和 payload，以便业务校验、空值语义和数据库更新继续由模块负责。

## 主流程

1. 模块声明 `selection_mode="multi"`、`bulk_update_handler`、`toolbar.bulk_update`、`crud.primary_key` 和 `form.update_columns`。
2. 用户在当前页选择记录，点击“批量编辑”。
3. Core 打开不预填首行的 update 表单。
4. Core 从选中行提取、保序去重主键，并调用 handler：`(context, primary_keys, payload)`。
5. 成功后清选择并刷新；失败时保留页面与选择并显示原始业务错误。

## 异常流程与业务规则

- 任何选中行缺少主键时，Core 显示明确错误且不调用 handler。
- 0 行时批量按钮禁用；单条编辑 / 删除仅在恰好 1 行时启用。
- 声明 `bulk_update_handler` 且 `toolbar.bulk_update` 省略时默认显示批量按钮；显式 `False` 时隐藏；显式 `True` 但缺 handler 时配置无效并产生明确诊断。
- 声明 `bulk_update_handler` 时必须同时声明 `crud.primary_key` 和非空 `form.update_columns`。
- 行内编辑 / 删除只作用于点击行，不隐式作用于其它选中行。
- 空白可空文本字段传 `None`，Core 不根据字段名改写 payload。
- 仅支持当前已加载页；翻页或刷新后不保留选择。
- 同步路径可复用现有对话框；已有 event loop 时必须使用 `open_dialog_async()`。

## REQ / AC

- `REQ-012-001`：Contracts 暴露并严格规范化 `selection_mode=none|single|multi`，省略时为 `single`。
- `REQ-012-002`：CRUD 增加 `bulk_update_handler` 与 `toolbar.bulk_update`，复用 `form.update_columns`。
- `REQ-012-003`：Core 固定传递 `primary_keys` 和 `payload`，主键保序去重且缺失时 fail-fast。
- `REQ-012-004`：旧页面与同步 / 异步路径保持兼容，单条动作维持单条语义。
- `REQ-012-005`：SDK scanner 对 handler 引用、签名与参数类型给出字段路径明确的诊断。

SDK 固定签名中的第一个参数名必须为 `context`；`ctx` 不作为新 bulk handler 的兼容别名。`primary_keys` 接受 `list[T]` / `List[T]` 且元素类型具体，拒绝裸 `list`、`list[Any]`、`Any` 和 `Mapping`。

验收条件由 `TC-069` 覆盖：Contracts 规范化、SDK 诊断、多选按钮状态、主键提取、空值、成功 / 失败、同步 / 异步和既有 CRUD 回归。

## 非功能需求

- `NFR-012`：兼容性与非阻塞。未声明新字段的页面 100% 保持既有单选行为；异步路径不得调用阻塞式 `exec()`；所有新增分支必须有自动化回归。

## 非目标

- 跨分页选择、批量删除、任意 toolbar 表单、Core 直接批量写库、账号与分组业务规则。

## baseline 影响分析

- 领域：影响 Core MMS Hosted UI、Contracts、SDK scanner；模块业务数据库仍由模块 owner 管理。
- 架构：不改变 Core / 模块 owner 边界。
- 数据库：不改变 `managed_dataset` 表结构或 `ctx.db` API。
- API：新增 `API-021` Hosted UI DataTable Bulk Update Contract。
- UI：扩展 DataTable 选择模式、CRUD toolbar 和批量表单交互。

## 风险与回滚

- 风险：多选时单条 toolbar 误取第一行；通过按钮状态和 handler 防御测试锁定。
- 风险：schema 默认值改变 descriptor 序列化；运行行为仍为 `single`，通过旧页面回归锁定。
- 回滚：移除新 schema 字段和 renderer 分支即可；无数据库迁移。

## 未决问题

- 无。严格 payload 类型识别沿用现有 CRUD scanner 的“拒绝宽泛容器”边界，不在本轮引入跨文件类型解析器。
