# CR-017 VirtualBrowser 创建环境指纹自洽与稳定性优化

- 状态：READY_FOR_REVIEW
- 类型：CR
- 优先级：P1
- 估算：2.0 人/天
- 关联 ID：`CR-017`, `REQ-011`, `NFR-011`, `TC-068`, `TASK-035`
- 提出日期：2026-07-08
- 来源：携游数据管家现场对比 `Virtual-Browser_20260708T065502.860Z.json` 与 `Virtual-Browser__0708模板.json` 后转入宿主 crawler4j 项目

## 变更动机

- 宿主创建的 VirtualBrowser 环境出现 `WOW64` UA、定位 `0,0`、字体 / 语音 / Canvas / WebGL / Audio / ClientRects 仅有 `mode=1` 但缺少可审计实际参数的问题。
- 人工模板环境参数更完整，但存在不可直接照抄的风险：代理 `host` 与 `proxy.url` IP 不一致、`2 CPU / 64GB` 组合不自然、代理地区 / 定位 / 时区 / 语言混搭。
- 需要由 crawler4j 宿主侧分析并优化创建环境逻辑，保证每个新环境在创建期形成一套自洽且后续启动稳定的参数，而不是把业务模块侧做成补丁。

## 当前代码事实

- `packages/crawler4j/src/core/rem/virtualbrowser_fingerprint.py` 的 UA 模板池仍包含 `Windows NT 10.0; WOW64`。
- 随机指纹默认硬件池已有常见组合：`4/8`、`6/16`、`8/16`、`8/32`、`12/32`，不包含现场模板里的 `2/64`。
- 随机指纹托管模式当前只给 `fonts`、`canvas`、`webgl-img`、`audio-context`、`client-rects`、`speech_voices` 下发 `mode=1`，实际细节交给 VirtualBrowser。
- 2026-07-03 已把 `location` 改回 VirtualBrowser 默认配置：随机创建期不再下发经纬度，代理 geo 只用于语言和时区。
- 创建后轻验收目前主要校验 `time-zone`、`ua-language`、`webrtc`，还没有覆盖 UA 架构、定位占位、字体 / 语音 / 扰动完整度、代理字段一致性和硬件组合自然度。

## 需求

- `REQ-011-001` 默认随机 UA 不应再生成 `WOW64`，除非后续明确增加 32 位浏览器画像并同步 CPU / OS / Chrome 版本等配套字段。
- `REQ-011-002` 每个新环境的指纹参数只在创建期生成一次并持久化到外部 VirtualBrowser 环境；后续启动、连接、任务运行不得重新随机同一环境的 UA、硬件、字体、语音或扰动参数。
- `REQ-011-003` 定位策略必须避免 `0,0`。若无法拿到可信经纬度，继续不下发 `location`；若重新引入定位，必须来自可信 geo 数据并与代理出口国家 / 城市 / 时区保持一致。
- `REQ-011-004` 评估是否由 crawler4j 显式生成中文 Windows 字体、语音列表和 Canvas / WebGL / Audio / ClientRects 稳定扰动值；若 VirtualBrowser 自身已能稳定生成，则不要重复造完整指纹引擎，只补验收和风险标记。
- `REQ-011-005` CPU / 内存只能使用常见组合，避免 `2/64` 这类不自然组合；手工模板导入或高级配置也应在风险验收中提示异常组合。
- `REQ-011-006` 创建后 `getBrowserFullParameters` 轻验收需要扩展：UA 架构、`proxy.host` 与 `proxy.url` 一致性、定位 `0,0`、语言 / 时区 / 代理 geo 一致性、硬件组合、字体 / 语音 / 扰动字段完整度都应进入 warning。
- `REQ-011-007` 轻验收 warning 应继续落入环境风险 metadata，并被现有调度跳过逻辑消费，避免风险环境进入自动任务池。

## 非目标

- 不在 `ctrip_crawler` 业务模块内修补环境创建参数。
- 不复制人工模板的具体代理、定位、字体、语音或扰动值。
- 不新增大而全的设备指纹库；优先复用 VirtualBrowser 原生能力，只补 crawler4j 必须兜住的自洽规则和验收。
- 不把代理 IP 地理库结果强行伪造成精确 GPS 坐标。

## 验收标准

- `TC-068-001` 默认随机 VirtualBrowser UA 不包含 `WOW64`，Windows 默认为 `Win64; x64`。
- `TC-068-002` 创建期随机参数只在 `addBrowser` 前展开一次；启动 / 连接不触发重新随机。
- `TC-068-003` 随机创建 payload 不会下发 `location: 0,0`；若实现可信定位，则测试覆盖定位、时区、语言和代理 geo 一致。
- `TC-068-004` 硬件池和验收逻辑拒绝或标记 `2 CPU / 64GB` 等异常组合。
- `TC-068-005` 创建后验收能识别 `proxy.host` 与 `proxy.url` IP 不一致。
- `TC-068-006` 创建后验收能识别缺少字体 / 语音 / 指纹扰动实际值的风险，或明确证明 VirtualBrowser 自身已稳定生成且无需宿主下发具体值。
- `TC-068-007` 风险 warning 会在环境列表可见，并沿用现有风险环境调度跳过机制。

## 后续任务

- `TASK-035`：先做代码路径与 VirtualBrowser 实际返回参数分析，形成最小实现方案，再按测试先行修改创建逻辑和验收逻辑。

## 实现记录

- 2026-07-08 已完成最小实现：随机 VirtualBrowser 创建期默认 UA 收敛为 Windows `Win64; x64`；`fonts`、`canvas`、`webgl-img`、`audio-context`、`client-rects`、`speech_voices`、设备名和 MAC 在 `addBrowser` 前一次性生成完整值；UI 传入的 `mode=1` 占位不会覆盖这些完整值；`location` 继续不下发，避免 `0,0`；创建后验收新增 `WOW64`、`location=0,0`、异常 CPU/内存组合、`proxy.host` 与 `proxy.url` 非本地转发不一致、裸 `mode=1` 字段缺实际值的 warning。
- 验证：版本服务回归 `3 passed`，目标 VirtualBrowser REM 回归 `44 passed`，运行模板 UI 回归 `36 passed`，目标 `ruff check`、`.factory/project.json` JSON 校验和 `git diff --check` 通过。
