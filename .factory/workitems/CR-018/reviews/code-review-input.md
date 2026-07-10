# CR-018 / TASK-036 整体 Review Input

## 请求

请独立执行整体 Spec + Quality Review。当前作者状态仅为 `ready_for_review`，不得把子任务 approval 直接升级为 work item 完成或人工确认。

## 需求与设计

- Work item brief：`.factory/workitems/CR-018/brief.md`
- Task brief：`.factory/workitems/CR-018/task-briefs/TASK-036.md`
- 通用设计：`docs/04-project-development/04-design/hosted-ui-datatable-bulk-update-design.md`
- API：`docs/04-project-development/04-design/api-design.md` 的 `API-021`
- 需求 / 测试 / 追踪：`REQ-012`、`NFR-012`、`TC-069` 与两个 traceability matrix。

## 实现范围

- `packages/crawler4j-contracts/src/crawler4j_contracts/hosted_ui.py`
- `packages/crawler4j-sdk/src/v2_scanner.py`
- `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py`
- `packages/crawler4j/src/ui/components/data_table.py`
- 四个对应目标测试文件。
- Task 3 指定 docs、work item 与 `.factory/memory/` 文件。

## 已有独立评审

- Task 1 Spec / Quality：`.factory/workitems/CR-018/reviews/task-1-spec-review.md`、`task-1-review.md`；approved，`82 passed`，`100/100`。
- Task 2 Spec / Quality：`.factory/workitems/CR-018/reviews/task-2-spec-review.md`、`task-2-review.md`；approved，`38 passed`，`98/100`。
- 子任务评审只批准各自范围，不替代本次整体 review。

## 整体验证

- Evidence：`.factory/workitems/CR-018/evidence/verification.md`
- 合并目标集：`120 passed`。
- 目标 Ruff、diff、project JSON、docs-stratego：通过。
- 全量 unit：`1132 passed, 2 failed`。
- 两个失败：SDK `0.4.3` / README `0.4.2`；应用 `0.4.29` / 根 README 旧版本。相关文件不在 `CR-018` diff，Task 3 禁止修改版本。

## Spec Review 核对点

- `selection_mode` 是否只在 DataTable 顶层、允许值正确且省略兼容 `single`。
- bulk handler 是否固定 `context + primary_keys:list[具体类型] + 具体 payload`。
- Core 是否只传 `primary_keys + payload`，没有数据库 / 业务规则耦合。
- 单条 toolbar、多选 bulk、行内点击行、缺主键、空值、成功 / 失败、同步 / 异步和选择生命周期是否满足 brief。
- 正式文档、追踪和 memory 是否只记录通用能力，未声称具体业务模块 E2E。

## Quality Review 核对点

- Contracts / SDK / Core / UI 分层是否清晰，是否存在重复验证或额外抽象。
- 类型诊断和错误位置是否稳定。
- sync / async 镜像路径是否保持一致，是否有阻塞式 dialog 回归。
- 全量 unit 的两个范围外失败是否应阻塞当前整体 gate；若接受 concern，仍只可推进到后续人工确认 gate，不能写 DONE。
