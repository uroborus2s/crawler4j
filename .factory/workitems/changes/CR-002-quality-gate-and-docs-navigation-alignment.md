# CR-002 收敛质量门与文档导航策略

- 状态：DONE
- 类型：CR
- 优先级：P1
- 估算：1.0 人/天
- 关联 ID：`CR-002`, `REQ-005`, `NFR-003`, `TASK-005`
- 提出日期：2026-03-26

## 变更动机

- `uv run ruff check .` 当前失败 58 项
- 仓库内存在 manual/debug/verify 类型脚本，不一定适合直接纳入同一 lint gate
- `docs/` 已统一为单一 Markdown 文档树，但导航入口、参考层约束和质量门说明还需要进一步固化

## 变更范围

- 确定 lint 范围与 legacy 脚本策略
- 记录 Markdown 文档树的导航与参考层管理规则
- 将质量门结果变成可复用的基线

## 完成判定

- 质量门规则有文档
- lint 与文档基线的结论可解释、可复验

## 完成说明

- 已为默认 `ruff` gate 明确维护范围与 legacy 脚本边界
- 已建立 `docs/05-quality/quality-gates.md` 作为质量门与文档导航策略的正式入口
- 当前质量门结论已同步回 `.factory/project.json` 与 `.factory/process/quality-check-report.md`
