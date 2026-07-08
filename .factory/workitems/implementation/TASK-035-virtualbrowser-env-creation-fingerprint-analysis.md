# TASK-035 分析并优化 VirtualBrowser 创建环境指纹逻辑

- 状态：READY_FOR_REVIEW
- 负责人：Codex
- 优先级：P1
- 估算：2.0 人/天
- 关联 ID：`TASK-035`, `CR-017`, `REQ-011`, `NFR-011`, `TC-068`

## 目标

把携游现场发现的环境参数问题收口到 crawler4j 宿主创建逻辑：分析 `VirtualBrowser` 创建期指纹展开、代理 geo、创建后验收和风险标记，给出并实现最小自洽优化。

## 现场输入

- 宿主创建环境出现 `WOW64` UA、`location` 为 `0,0`、字体 / 语音 / Canvas / WebGL / Audio / ClientRects 只有 `mode=1`。
- 人工模板更完整，但存在 `proxy.host` 与 `proxy.url` IP 不一致、`2/64` 硬件组合、代理地区 / 定位 / 时区 / 语言混搭等风险。
- 期望结论：新环境创建时参数自洽；同一个环境后续启动稳定，不重新随机。

## 代码入口

- `packages/crawler4j/src/core/rem/virtualbrowser_fingerprint.py`
- `packages/crawler4j/src/core/rem/provider.py`
- `packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_fingerprint.py`
- `packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py`
- `packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py`
- 必要时补充 `packages/crawler4j/tests/unit/test_core/test_rem/test_env_list_widget.py`

## 实施步骤

1. 复核 `materialize_virtualbrowser_fingerprint()` 当前输出与 `getBrowserFullParameters()` 实际返回，确认哪些字段由 VirtualBrowser 稳定生成，哪些需要 crawler4j 下发。
2. 删除或降权默认 `WOW64` UA，保持 UA、`chrome_version`、`sec-ch-ua` 与 OS 架构一致。
3. 保持定位策略最小化：不下发 `0,0`；只有可信经纬度来源时才考虑重新引入 `location`。
4. 评估字体、语音和扰动字段：优先增加创建后验收；只有 VirtualBrowser 不稳定或缺失时，再生成固定值。
5. 扩展硬件组合和代理字段验收：标记异常 CPU / 内存组合、`proxy.host` 与 `proxy.url` 不一致。
6. 确保验收 warning 继续落入环境风险 metadata，并沿用现有调度跳过机制。
7. 同步测试计划、变更摘要和必要用户说明。

## 非目标

- 不改业务模块 `ctrip_crawler`。
- 不实现完整设备画像系统。
- 不照抄人工模板参数。

## 验收标准

- `test_virtualbrowser_fingerprint.py` 覆盖 UA 架构、硬件池、定位策略和稳定生成规则。
- `test_virtualbrowser_client.py` 覆盖创建 payload 不携带旧身份字段、不携带 `location: 0,0`，并正确传入创建期一次性展开结果。
- `test_provider.py` 覆盖创建后验收 warning：UA 架构、代理字段不一致、异常硬件、缺少字体 / 语音 / 扰动实际值。
- 风险 metadata / 环境列表 / 调度跳过沿用既有机制，必要时补目标回归。
- 目标验证：`uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_fingerprint.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py -q`、目标 `ruff check`、`git diff --check` 通过。

## 实现记录

- 2026-07-08 已实现创建期一次性稳定参数：`materialize_virtualbrowser_fingerprint()` 在随机模式下按宿主系统生成 OS / UA / 字体 / 语音 / 设备名（Windows 使用 `Win64; x64`，macOS 使用 Macintosh，Linux 使用 `Linux x86_64`），并生成完整 Canvas/WebGL/Audio/ClientRects 扰动、MAC、常见硬件组合和屏幕参数；`mode=1` 占位字段不会覆盖已生成的完整值。
- 保持启动路径不变：本次未修改 `launchBrowser` / `connect`，后续启动只打开已创建环境，不重新随机。
- 创建后验收扩展：`getBrowserFullParameters` 结果会标记 `WOW64`、`location=0,0`、非常见硬件组合、非本地转发的代理 host/url 不一致、字体/语音/扰动缺实际值。

## 验证记录

- `uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_fingerprint.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py -q` -> `44 passed`
- `uv run pytest packages/crawler4j/tests/unit/test_core/test_atm/test_run_profile_dialog.py -q` -> `36 passed`
- `uv run ruff check packages/crawler4j/src/core/rem/virtualbrowser_fingerprint.py packages/crawler4j/src/core/rem/provider.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_fingerprint.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py` -> `All checks passed!`
- `git diff --check` -> 通过
