# BUG-005 `hybrid` 资源获取模式已暴露给用户，但运行时明确拒绝

- 状态：DONE
- 类型：BUG
- 优先级：P1
- 估算：0.5 人/天
- 关联 ID：`BUG-005`, `REQ-002`, `TASK-008`
- 发现日期：2026-03-26

## 问题

策略模型和策略编辑器曾支持 `hybrid` 获取模式，但执行内核只支持 `match` 和 `create`，会把 `hybrid` 直接判为失败。

## 证据

- `src/core/tsm/models.py` 已移除 `AcquisitionMode.HYBRID`
- 策略编辑器已移除 `hybrid` 选项
- 新增运行时测试，确保 `mode: hybrid` 现在会在解析阶段被拒绝

## 影响

- 已收敛为“模型、编辑器、运行时仅支持 match/create”这一致语义

## 验收标准

- 二选一：
  - 实现 `hybrid` 的真实运行语义
  - 或从模型、UI、文档中彻底移除 `hybrid`
- 增加对应的回归验证，确保编辑器和运行时语义一致
