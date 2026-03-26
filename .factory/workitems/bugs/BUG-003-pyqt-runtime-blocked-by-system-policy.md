# BUG-003 PyQt6 运行时当前被系统策略阻断，导致 UI 与 `pytest-qt` 不可用

- 状态：DONE
- 类型：BUG
- 优先级：P0
- 估算：1.0 人/天
- 关联 ID：`BUG-003`, `REQ-002`, `REQ-005`, `TASK-008`
- 发现日期：2026-03-26

## 问题

当前机器上的 Qt 相关测试稳定性曾异常，导致桌面 UI 主链路和 `pytest-qt` 质量门一度不可靠。

## 证据

- `uv run pytest -q` 现已通过：`184 passed`
- `uv run python scripts/smoke_test_ui.py` 现已通过
- `tests/conftest.py` 已补充 Qt 运行时探测逻辑，避免环境不稳定时直接把全量回归打崩

## 影响

- 当前可把“应用可启动”和“测试门可执行”重新视为成立
- 后续如遇到机器级 Qt 波动，仍会优先通过探测与跳过策略保护测试门

## 验收标准

- PyQt6 在当前机器可直接导入
- `uv run python scripts/smoke_test_ui.py` 恢复通过
- `uv run pytest -q` 不再因 `pytest-qt` / PyQt6 初始化失败而退出
