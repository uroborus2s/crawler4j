# TASK-023 为固定环境池 Service Job 建立宿主等待队列与资源池资格分配

- 状态：DONE
- 负责人：Codex
- 优先级：P1
- 估算：2.0 人/天
- 关联 ID：`TASK-023`, `REQ-009`, `CR-009`, `API-007`, `NFR-004`

## 目标

- 把固定环境池场景从“环境选择失败即任务失败”推进到“等待环境”的正式业务语义。
- 让 Service Job 的目标并发收敛为“运行中 + 等待中 = 目标并发”。
- 让宿主只从当前模块资源池里资格有效的环境集合中分配工位。
- 让模块开发者只负责同步资格快照，不负责排队和轮询。

## 范围

- 在 ATM 建立固定环境池 Service Job 的等待队列与 FIFO 补位流程。
- 在 REM `env_metadata` 中落模块资源池资格卡片，并补容量变化触发调和。
- 为 SDK 增加资源池资格 helper，支持绑定、停发号、移除与全量重建。
- 更新运行模板/UI 文案、测试计划、需求追踪、开发者文档和 `.factory/memory/`。

## 非目标

- 不实现优先级队列、多租户抢占或跨模块插队策略。
- 不让模块自己通过 `sleep`/轮询实现等待。
- 不把资格卡片落成普通业务数据表或 `core:data_table` 可编辑页面。

## 验收标准

- 固定环境池 Service Job 在“目标并发 10、可用工位 2”时表现为“运行中 2、等待中 8”，而不是制造 8 个假失败。
- 容量从 2 增长到 5 时，宿主会一次性补位 3 个，结果表现为“运行中 5、等待中 5”。
- 宿主只从“当前模块 + 当前资源池 + `eligible=true`”的环境集合里分配工位。
- 黑号环境会先停发号，再按策略销毁或保留；销毁后对应资格卡片自动清理。
- 正式文档、测试计划、追踪矩阵和 `.factory/memory/` 已同步。

## 完成说明

- ATM 已为固定环境池 Service Job 引入“等待席位”语义：资源池模式下当前轮未命中会保持 `PENDING`，不再直接失败。
- 宿主已通过 `env_metadata` 资源池资格卡片过滤可分配环境，并在 `controller` 中按 FIFO 补位已有等待任务。
- SDK 已新增资源池 helper，模块开发者可通过统一封装登记/切换/移除/重建资格卡片。
- 运行模板表单与相关单测已同步支持 `resource_pool`，并保留“选择器细筛 + 资源池粗筛”的组合模式。
- 本地回归已通过：`uv run pytest packages/crawler4j/tests/unit/test_core/test_atm -q packages/crawler4j/tests/unit/test_sdk/test_data_capability.py`、目标文件 `uv run ruff check ...`。
