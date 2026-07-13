# 环境代理交互与 VirtualBrowser 管理能力优化简报

- 项目：crawler4j
- Work item：`CR-021`
- 状态：`approved_pending_commit`
- 场景：`change_requirement` + `fix_bug`
- 日期：2026-07-13
- 来源：用户对环境编辑弹窗和环境列表的截图反馈

## 用户目标

- 环境编辑弹窗的按钮、下拉框统一使用公共组件和协调尺寸。
- 可用 IP 下拉框能查看并选择 IP 表中的其他可用 IP。
- 删除与明确选择流程重复的“随机更换 IP”入口。
- VirtualBrowser 环境增加“清理缓存”操作，调用 `POST /api/clearCache`。
- 环境列表新增“指纹浏览器 ID”列，展示环境的 `external_id`。

## 当前门禁

用户已确认停用 IP 不出现在候选框符合预期，并批准按方案实现。已绑定池时仅展示当前池内可用且未过期 IP；未绑定池时保留从全部池首次绑定的既有能力。实现通过完整验证与独立复评，待按仓库要求本地提交。调查报告见 `reports/root-cause.md`。
