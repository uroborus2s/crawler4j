# CR-003 补齐 MMS settings store 与 UI 扩展合规实现

- 状态：OPEN
- 类型：CR
- 优先级：P1
- 估算：1.5 人/天
- 关联 ID：`CR-003`, `REQ-002`, `REQ-005`, `TASK-008`
- 提出日期：2026-03-26

## 变更动机

- SRS 与详细设计要求 MMS 提供模块级/工作流级 settings 的读写与导出能力
- SRS 要求代码型 UI 扩展具备 trust gate / allowlist 约束
- 当前实现只有部分 manifest 索引和通用降级页，自定义页面仍停留在占位实现

## 变更范围

- 为 MMS 建立正式的 settings store 接口与持久化模型
- 补齐模块启用/禁用状态的持久化与启动时覆盖逻辑
- 补齐工作流级 settings 的读写与导出能力
- 明确并实现 UI 扩展 trust gate / allowlist / 降级路径
- 让模块自定义页面从占位页进入真实可加载状态，或明确限制支持范围

## 当前进展

- 已完成：settings store、工作流级导出、模块启停持久化、卸载时的 settings 清理策略
- 剩余范围：trust gate / allowlist、受信代码型 UI 扩展装载、自定义页面真实加载与降级

## 完成判定

- `read_settings/write_settings` 与导出能力可用
- 模块启用/禁用状态具备持久化
- UI 扩展加载路径有明确的 trust gate 规则与测试
- 文档与实现保持一致
