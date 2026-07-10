# Hosted UI DataTable 当前页批量编辑设计

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 评审中
**负责人：** 当前仓库维护者
**主要读者：** 架构 | Core 开发 | SDK 开发 | QA | 模块开发者
**上游输入：** `REQ-012` | `NFR-012` | `API-006` | `API-008` | 已批准的 `CR-018` / `TASK-036` 任务简报
**下游输出：** `api-design.md` | `implementation-plan.md` | `test-plan.md` | Contracts / SDK / Core 实现
**关联 ID：** `REQ-012`, `NFR-012`, `API-021`, `CR-018`, `TASK-036`, `TC-069`
**最后更新：** 2026-07-10

## 版本信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `API-021-DESIGN` |
| 文档类型 | 技术设计 |
| 当前版本 | `0.1.0` |
| 当前状态 | `pending_human_confirmation`（独立整体 review 99/100；保留范围外版本文档 concern） |
| 最近更新 | 2026-07-10 |

## 1. 结论

Hosted UI `DataTable` 的批量编辑是当前已加载页内的宿主交互能力。Contracts 声明选择模式与批量 handler，SDK 在模块扫描阶段验证配置和签名，Core 只收集选择、生成表单 payload 并调用模块 `@ui_action`。业务校验、`managed_dataset` 查询和 `ctx.db` 写入始终由模块负责。

当前实现事实：

- `DataTable.selection_mode` 位于表格顶层，只接受 `none | single | multi`，省略时归一为 `single`。
- CRUD 内新增 `toolbar.bulk_update` 与 `bulk_update_handler`，批量表单复用 `form.update_columns`。
- handler 固定接收 `(context, primary_keys, payload)`；`primary_keys` 是具体元素类型的 `list[T]` / `List[T]`，payload 使用具体 `TypedDict` 或 dataclass 风格类型。
- Core 只传 `primary_keys` 与 `payload`，不传整行，不读取或写入模块数据库。
- 当前选择按显示 / 选择顺序提取主键并保序去重；去重保持类型边界，例如整数 `7` 与字符串 `"7"` 不是同一主键。
- 刷新、搜索、筛选、排序、切换页码或分页大小都会经过表格刷新链并清除选择；不保留跨页状态。

## 2. 目标

- 让模块用声明式 schema 开启当前页多选与批量编辑。
- 复用现有 CRUD update 表单和 `@ui_action` 调用链，不建立第二套 toolbar 表单协议。
- 保护单条编辑 / 删除和行内动作语义，避免多选时默认取第一行。
- 同时覆盖同步宿主路径与已有 event loop 下的非阻塞异步路径。
- 保持未声明新字段的旧页面继续使用单选和原 CRUD 行为。

## 3. 非目标

- 不支持跨分页保留选择或跨页批量提交。
- 不提供批量删除、任意 toolbar 参数表单或批量字段专用列配置。
- 不改变 `managed_dataset` 物理结构、`ctx.db` API 或数据写入事务模型。
- 不把账号、手机号、任务分组、公共组等业务规则放入 Contracts、SDK 或 Core。
- 不声明任何具体业务模块已经接线，也不把业务模块 E2E 作为 `CR-018` 已完成事实。

## 4. Schema 契约

最小声明示例：

```python
from typing import TypedDict

from crawler4j_contracts import page, ui_action


class AccountUpdatePayload(TypedDict, total=False):
    name: str
    note: str | None


@page(
    name="accounts",
    schema={
        "type": "Page",
        "children": [
            {
                "type": "DataTable",
                "table_id": "accounts",
                "selection_mode": "multi",
                "columns": ["account_id", "name", "note"],
                "data_source": {
                    "type": "managed_resource",
                    "resource_id": "accounts",
                },
                "crud": {
                    "primary_key": "account_id",
                    "form": {"update_columns": ["name", "note"]},
                    "toolbar": {"bulk_update": True},
                    "bulk_update_handler": "bulk_update_accounts",
                },
            }
        ],
    },
)
def load_accounts(context, page_id, params=None):
    return {}


@ui_action(name="bulk_update_accounts")
def bulk_update_accounts(
    context,
    primary_keys: list[str],
    payload: AccountUpdatePayload,
):
    # 业务校验与 ctx.db 写入由模块实现。
    return {"updated": len(primary_keys)}
```

规则：

| 字段 | 规则 |
|---|---|
| `selection_mode` | 顶层字段；`none/single/multi`；省略为 `single`；放进 `crud` 会作为未知字段拒绝 |
| `crud.primary_key` | 声明 `bulk_update_handler` 时必填，用于从选择行提取主键 |
| `crud.form.update_columns` | 声明 `bulk_update_handler` 时必须非空；批量表单不从首条选择行预填 |
| `crud.bulk_update_handler` | 必须引用同模块已登记的 `@ui_action` |
| `crud.toolbar.bulk_update` | `True` 时必须有 handler；handler 存在且该键省略时默认展示，显式 `False` 可隐藏入口 |

## 5. Handler 契约与 SDK Gate

批量 handler 的固定签名是：

```python
def handler(
    context,
    primary_keys: list[ConcretePrimaryKey],
    payload: ConcretePayload,
): ...
```

SDK scanner 必须拒绝：

- 首参不是精确名称 `context`；
- 参数缺失、错序、默认值、keyword-only、`*args` 或 `**kwargs`；
- 裸 `list`、`list[Any]`、`Any`、`Mapping`、模块 `TypeVar` 或多元素类型实参作为 `primary_keys`；
- 裸 `dict`、`Mapping` 或 `Any` 作为 payload；
- toolbar 开启但 handler 缺失，或 handler 引用不存在；
- 缺少 `primary_key` 或非空 `form.update_columns`。

具体 `list[str]`、`list[int]`、`List[str]`、`List[int]` 和模块自定义具体主键类型可以通过。SDK 只验证可静态观察的契约，不推断模块业务规则。

## 6. Core 交互与数据流

```text
当前页选择
  -> SkyDataTable.selected_rows()
  -> 按 crud.primary_key 提取并保序、类型敏感去重
  -> 复用 update_columns 打开空白表单
  -> ModuleUIRuntimeBridge.call_ui_action(
       bulk_update_handler,
       primary_keys=[...],
       payload={...},
     )
  -> 模块校验并通过 ctx.db 写入
  -> 成功：清选择并刷新一次
     失败：保留选择，不刷新，展示原始业务错误
```

Core 防御规则：

- 0 行选择时批量按钮禁用；一行或多行时启用。
- toolbar 单条编辑 / 删除只有恰好一行时启用。
- 行内编辑 / 删除使用用户点击的那一行，不依赖当前多选集合。
- 任一选择行缺少主键或主键为空时，表单和 handler 都不调用，并显示明确错误。
- 可空文本字段留空时沿用 CRUD 表单归一化为 `None`。
- 成功回调只触发一次 `request_refresh()`；表格在发出查询前清选择。
- 模块异常不转换为成功结果；同步和异步路径都保留选择并显示原始错误文本。

## 7. 同步与异步边界

- 没有运行中的 event loop 时，沿用同步 CRUD 对话框和同步 `@ui_action` 调用链。
- 已有 event loop 时转入 async flow，表单通过 `open_dialog_async()` 打开，不调用阻塞式 `QDialog.exec()`。
- 同步 / 异步路径共享相同的主键提取、参数形状、成功刷新和失败保留规则。

## 8. 选择生命周期

选择只属于当前加载结果。下列动作均清除选择：

- 手工刷新；
- 搜索文本变化；
- 快速筛选变化；
- 表头或可见排序控件变化；
- 上一页、下一页或直接分页；
- 每页条数变化。

这样可以避免旧行对象在查询条件变化后继续成为批量操作目标。V1 不在 Core 中维护跨页主键集合。

## 9. 分层与 owner

| 层 | 责任 | 禁止事项 |
|---|---|---|
| Contracts | schema 类型、允许值、规范化和配置前置条件 | 不认识业务表和业务字段规则 |
| SDK scanner | handler 引用、精确签名和具体类型诊断 | 不执行模块、不推断业务校验 |
| `SkyDataTable` | 选择模型、选择事件、查询前清选择 | 不调用模块 handler、不写数据库 |
| Core renderer | toolbar 状态、表单、主键提取、动作调用、成功 / 失败反馈 | 不直接访问 `managed_dataset` |
| 模块 `@ui_action` | 业务授权、状态约束、字段校验、`ctx.db` 批量写入 | 不依赖 Core 内部 UI 类型 |

## 10. 验证与当前状态

`TC-069` 覆盖：

- Contracts 选择模式、默认值和非法配置；
- SDK handler 引用、精确签名、主键列表与 payload 类型诊断；
- toolbar 按钮启用条件、行内点击行语义和主键缺失阻断；
- 保序、类型敏感去重、空白可空字段、同步 / 异步成功与失败；
- 刷新、搜索、筛选、排序和分页清选择；
- 未声明新字段的既有 CRUD 回归。

Task 1 Contracts / SDK 已通过独立 Spec + Quality Review，定向结果为 `82 passed`；Task 2 Core / UI 已通过独立 Spec + Quality Review，定向结果为 `38 passed`。Task 3 新鲜合并目标集为 `120 passed`，目标 Ruff、`git diff --check`、`.factory/project.json` JSON 校验与 docs-stratego 结构校验通过。全量 unit 为 `1132 passed, 2 failed`；两个失败均来自当前 HEAD 已存在的版本 / README 文档漂移（SDK `0.4.3` 与 README `0.4.2`、应用 `0.4.29` 与根 README 旧版本），不在 `CR-018` 允许修改范围。独立整体 review 已 `approved`（99/100），当前状态为带该 concern 的 `pending_human_confirmation`，不代表验证全绿、人工确认、发布或业务模块 E2E 完成。

## 版本历史

| 版本 | 修改内容 | 日期 | 修改人 | 审核 | 批准 |
|---|---|---|---|---|---|
| `0.1.0` | 建立本仓通用 DataTable 当前页批量编辑设计，记录 Contracts / SDK / Core owner 边界和实现事实 | 2026-07-10 | Codex | 待独立审核 | 待批准 |
