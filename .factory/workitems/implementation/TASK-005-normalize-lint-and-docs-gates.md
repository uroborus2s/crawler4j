# TASK-005 收敛 lint 与 docs gate

- 状态：DONE
- 类型：TASK
- 优先级：P1
- 估算：1.0 人/天
- 关联 ID：`TASK-005`, `CR-002`, `REQ-005`, `NFR-003`

## 目标

- 确定哪些脚本应纳入 lint gate
- 逐步清理当前 ruff 失败项，或为 legacy/manual 脚本划清边界
- 让文档导航与当前工厂基线保持可解释状态

## 验收标准

- `ruff` 范围有明确规则
- 文档导航策略有记录
- 质量门结论可复用

## 完成说明

- 当前默认 `ruff` 质量门已收敛到维护范围内代码与常规自动化测试
- 历史 `manual/debug/verify/analyze` 脚本已明确标记为默认 lint gate 之外的人工辅助资产
- 当前质量门规则与文档导航策略已固化到 `docs/05-quality/quality-gates.md` 与 `.factory/process/quality-check-report.md`
