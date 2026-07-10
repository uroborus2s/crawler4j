# 项目记忆索引

更新时间：2026-07-10

## 读取入口

默认只读以下三份：

1. `.factory/memory/runtime-brief.md`：当前阶段、版本、硬约束、风险和下一动作。
2. `.factory/memory/agent-session.md`：本次会话卡、已读范围和排除范围。
3. `.factory/memory/project-index.md`：项目导航。

然后只按任务读取一个相关摘要和对应 work item ledger。不要把整个 `.factory/memory/`、`docs/` 或 `.factory/workitems/` 一次性加载。

## 分层

| 层 | 文件 | 用途 |
| --- | --- | --- |
| L0 入口 | `runtime-brief.md`、`agent-session.md`、`project-index.md` | 会话恢复必读 |
| L1 当前摘要 | `current-state.md`、`tasks.summary.md`、`tests.summary.md`、`release.summary.md`、`cr-019.summary.md` | 当前任务按需读取 |
| L2 专题摘要 | `api.summary.md`、`architecture.summary.md`、`requirements.summary.md`、`tech-stack.summary.md`、`traceability.summary.md` | 只有专题任务读取 |
| L3 事实源 | `.factory/workitems/**`、`docs/**`、`reviews/`、`evidence/` | 需要核实具体事实时回源 |
| 历史 | `history/`、旧 task/CR 条目 | 默认排除，除非追溯历史 |

## 记忆写入规则

- memory 只保存 ID、状态、gate、`next_required_action`、关键约束、风险和路径索引。
- 测试命令只保留最近一次通过结果；完整输出放在 work item evidence。
- 历史变更不追加到当前摘要；稳定事实回写正式文档，执行事实回写 ledger/evidence。
- 新摘要目标：单文件不超过 8KB；L0 合计不超过 16KB；超过阈值先压缩再继续会话。
- `current-state.md`、`change-summary.md`、`tests.summary.md` 不再承载逐条历史日志。

## 本轮结果

- 压缩前可计量内容：484,973 bytes（含 history 快照）。
- 压缩后可计量内容：约 85KB（含本次 session ledger、验证报告和 history 快照），相对压缩前减少约 82%。
- 当前 L0 入口（本索引 + runtime + session + project index）四份文件合计约 7.6KB；满足 16KB 入口预算。
- 精确命令结果和本轮动作记录在 `.factory/memory/session-ledger.jsonl`。
