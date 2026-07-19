# CR-023 独立评审反馈分流

## CR-023-RF-001：请求侧重复 header 未直接回归

- 来源：`/root/cr023_review_fast`，Minor
- 技术核实：正确。实现使用二元组序列支持重复项，但首轮测试的请求 header 名互不重复。
- 决定：`Fixed`。请求回归改为两个 `x-test` 值，并精确断言 Core 交给 `httpx.Request` 的顺序与重复性。

## CR-023-RF-002：布尔参数宽松强制转换

- 来源：`/root/cr023_review_fast`，Minor
- 技术核实：正确。`bool(...)` 会静默接受 `1` 或非空字符串，扩大公共工具的模糊输入面。
- 决定：`Fixed`。先增加 `http2=1`、`require_http2="yes"`、`follow_redirects=1` 的失败回归，再对三项参数执行严格 `bool` 类型校验。

## CR-023-RF-003：Brotli 路径缺少实际解码回归

- 来源：`/root/cr023_independent_review`，Minor 建议
- 技术核实：正确。已有诊断证明 `brotli` 可导入，但没有直接锁定 `httpx` 的 `Content-Encoding: br` 解码链。
- 决定：`Fixed`。使用 `httpx.MockTransport` 返回真实 Brotli 压缩内容，断言宿主 `http.request` 返回解码后的 raw bytes。

## CR-023-RF-004：发布与 memory 仍保留旧门禁事实

- 来源：`/root/cr023_independent_review`，Minor
- 技术核实：正确。首轮 TASK evidence 已写入新全量结果，但部分 release/memory 摘要仍以 2026-07-15 基线表达当前状态。
- 决定：`Fixed`。当前发布证据、验收清单、实施/执行/测试文档与 `.factory/memory` 均收敛到最终 `152 passed` / `1265 passed` 事实；2026-07-15 历史行保留不改。

## 验证

详见 `../evidence/review-fix-verification.md`。
