# 6.9 测试/运维/附录（SDK）

## 6.9.1 测试规格与验收

本节目标是让 SDK 的核心契约具备“可自动化验收”的标准，避免模块生态在 SDK 演进中被破坏。

### 6.9.1.1 单元测试（SDK 自身）

- SHOULD：覆盖 `TaskResult.ok/fail` 的字段与序列化行为。
- SHOULD：覆盖 `TaskContext` 的工具方法（如 `get_config/screenshot` 的异常路径）。
- SHOULD：覆盖 CLI 的核心路径（init/new/add/list）在典型参数下能成功运行。

### 6.9.1.2 契约测试（Runtime ↔ SDK）

> 契约测试的目标不是“测业务逻辑”，而是验证 Runtime 以正确方式驱动 SDK。

- MUST：Runtime 执行 TaskScript 时必须遵循生命周期顺序：`on_init -> execute -> on_error? -> on_cleanup`。
- MUST：当 execute 抛出异常时，Runtime 必须产出失败结果并记录诊断信息。
- SHOULD：`ctx.run_subtask` 的注入与返回语义保持稳定（共享 state、返回 result.data）。

### 6.9.1.3 验收口径

- 通过标准：
  - SDK 单元测试全部通过
  - 关键契约测试通过（生命周期、错误兜底、CLI 基础命令）
  - 文档（本章）与实现对齐（stable 部分不得与实现冲突）

## 6.9.2 发布与版本策略

### 6.9.2.1 发布物

- SDK 为独立 Python 包：`crawler4j-sdk`
- MUST：发布前更新版本号（SemVer），并维护变更说明（Release Notes）。

### 6.9.2.2 兼容性承诺

- stable API 在同一 MAJOR 内向后兼容（见 6.0.2/6.8）。
- 若出现破坏性变更：
  - MUST：提升 MAJOR
  - MUST：提供迁移指南（见附录 F：兼容性与迁移指南）

### 6.9.2.3 回归验证建议

- SHOULD：用仓库内至少 1 个真实模块（如 `modules/ctrip`）做回归 smoke test。

## 6.9.3 附录：API 索引/错误码/配置项/追溯

### 6.9.3.1 API 索引（稳定面）

- TaskScript：`execute/on_init/on_error/on_cleanup`（见 6.1）
- TaskFlow：`run/on_error/on_complete`（见 6.2）
- TaskContext：`page/context/logger/http/config/state/run_subtask/screenshot/...`（见 6.3）
- TaskResult：`success/tasks_completed/message/data/error`（见 6.4）

### 6.9.3.2 错误码索引

- 统一错误码规则见 6.7；全局错误码索引见：`docs/archive/reference-srs/appendix/B-error-codes.md`

### 6.9.3.3 配置项索引

- 全局配置项索引见：`docs/archive/reference-srs/appendix/C-config-index.md`

### 6.9.3.4 追溯

- 需求追溯矩阵见：`docs/archive/reference-srs/appendix/D-traceability-matrix.md`
