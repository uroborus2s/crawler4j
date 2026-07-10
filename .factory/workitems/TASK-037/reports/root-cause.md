# TASK-037 发布一致性测试失败根因

- 日期：2026-07-10（Asia/Shanghai）
- 状态：root_cause_found
- 复现命令：`QT_QPA_PLATFORM=offscreen uv run pytest packages/crawler4j/tests/unit -q -p no:cacheprovider`
- 复现结果：`1132 passed, 2 failed`

## 直接原因

1. `README.md` 已同步三包版本表，但缺少测试约束的 `uv run publish crawler4j-contracts` 与 `uv run publish crawler4j-sdk` 命令，因此无法证明依赖顺序。
2. `packages/crawler4j/pyproject.toml` 仍声明 `crawler4j-contracts>=0.4.2,<0.5.0`，与新 Contracts `0.4.3` 不一致。

## 根源原因

版本提升最初只同步了待发布的 Contracts / SDK 包及文档版本表，没有同步两个既有发布契约：根 README 的明确发布顺序，以及根应用作为 Contracts 消费方的依赖下限。两个失败均由 `test_packaging_config.py` 的确定性断言稳定复现，不涉及 CR-018 功能逻辑。

## 修复边界

- 在根 README 补回 Contracts -> SDK 的构建/发布命令顺序。
- 将根应用 Contracts 依赖下限同步为 `>=0.4.3,<0.5.0`，但保持客户端版本 `0.4.29` 不变。
- 更新锁文件并复跑失败用例及全量 unit。
