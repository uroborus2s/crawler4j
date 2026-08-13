# CR-026 HubStudio 独立评审输入

- 评审类型：批次 Spec + Quality Review
- 需求：`.factory/workitems/CR-026/brief.md`
- 计划：`.factory/workitems/CR-026/plan.md`
- 实现摘要：`.factory/workitems/CR-026/reports/batch-hubstudio.md`
- 验证证据：`.factory/workitems/CR-026/evidence/batch-hubstudio.md`
- 实现 diff：当前 `git diff` 与未跟踪的 `hubstudio_provider.py` / `test_hubstudio_provider.py`

## 必审边界

- `containerCode` 与 `browserID` 是否全路径严格分离。
- 生命周期、Cookie、缓存、更新、已有环境导入和 CDP 是否符合 HubStudio 官方契约。
- 是否保持旧 Provider 顺序/默认、环境列表列、数据库与公共契约不变。
- 指纹浏览器高层管理和用户操作是否可用；厂商限制是否被准确标记。
- 错误处理、敏感信息、循环导入、状态一致性与测试充分性。

## 评审输出

按 `Critical | Important | Minor` 列出可定位 Finding；存在 Critical/Important 时 `changes_requested`，否则 `approved`。明确真实 E2E 未运行是否在当前候选可接受。
