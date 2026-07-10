# 会话卡

- 时间：2026-07-10
- Actor：Codex
- 阶段：IMPLEMENTATION / MAINTENANCE
- Work item：none（本轮为项目记忆整理事件）
- 状态：ready_for_review

## 本轮目标

检查记忆体量，压缩冗长 current/change/test 摘要，并建立按需读取边界，避免后续会话批量加载历史内容。

## 已读取上下文

- .factory/memory/runtime-brief.md：恢复当前阶段、版本和约束。
- .factory/memory/current-state.md：确认当前任务与风险。
- .factory/memory/tasks.summary.md、.factory/memory/tests.summary.md：确认任务和验证索引。
- .factory/memory/project-index.md、.factory/memory/doc-map.md：确认入口与事实源映射。
- .factory/workitems/CR-019/ledger.jsonl、.factory/workitems/TASK-039/ledger.jsonl、.factory/workitems/TASK-037/ledger.jsonl：核对最近状态。

## 未读 / 已排除上下文

- .factory/memory/history/：历史快照，不影响当前恢复。
- 旧的逐条变更和测试正文：已压缩，不作为当前事实源。
- docs/ 全量正文：本轮只整理入口，没有具体开发事实缺口。

## 当前事实

- 压缩前 .factory/memory 约 556KB；主要膨胀来自三个历史型大摘要。
- 已将入口、当前状态、任务、测试和变更摘要改为索引式内容。
- 已新增 .factory/memory/memory-index.md 和 .factory/memory/session-ledger.jsonl。
- 精确压缩后体量以本轮命令证据为准。

## 禁止动作

- 不要默认读取整个 memory、docs 或 workitems。
- 不要把历史命令、临时推理或正式文档正文复制回 memory。
- 不要把 summary 当作高于 ledger、evidence 或正式文档的事实源。

## 待决事项

- 交回 using-shanforge 判断是否进入 gitcommitzh；本轮只应提交 memory 整理相关文件，不纳入工作区现有代码、文档和发布改动。

## 证据

- .factory/memory/session-ledger.jsonl
- .factory/memory/memory-index.md
- .factory/memory/memory-compaction-report.md
