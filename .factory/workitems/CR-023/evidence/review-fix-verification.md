# CR-023 评审修复验证

## TDD / 回归

- 严格布尔校验 RED：`3 failed, 8 passed`，失败均为非 `bool` 值未被拒绝。
- 严格布尔校验修复后：`11 passed`。
- 增加 Brotli 真实解码特征回归后：`12 passed in 0.16s`。
- 最终定向/邻近：`152 passed in 1.15s`。
- 最终全量 unit：`1265 passed in 30.82s`。

## 构建与运行时

- `uv run build crawler4j`：0.4.40 wheel/sdist 重建成功。
- `/private/tmp/crawler4j-cr023-wheel-final-20260719` 隔离安装：自动安装 `brotli/h2/hpack/hyperframe`；诊断输出 `http2_client=ok`，full surface 输出 `http.request=available`。
- macOS arm64 `uv run package-desktop`：最终代码重建成功。
- `Crawler4j.app/Contents/MacOS/Crawler4j --crawler4j-verify-http-runtime`：输出 `httpx=0.28.1`、`h2=4.3.0`、`hpack=4.2.0`、`hyperframe=6.1.0`、`brotli=1.2.0`、`http2_client=ok`。

## 静态与追踪

- 目标 Ruff：`All checks passed!`。
- 全仓 Ruff、lock、docs-stratego、JSON、diff 由完成前最终门禁复验。
- 正式 docs、work item 与 `.factory/memory` 已同步当前事实；外部 ctrip 接线与 Windows 冻结物仍明确为后续 gate。
