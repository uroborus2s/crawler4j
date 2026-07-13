# VirtualBrowser Cookie API 文档偏差根因报告

## 结论

CR-020 原计划引用的 Cookie API 请求/响应结构与当前本机 VirtualBrowser 实际接口不一致。若按原计划实现，会在写入时收到 HTTP 400，且即使改到可调用形态，若只发送目标 Cookie，也会删除环境中的全部未传 Cookie。

## 根因

1. 当前 VirtualBrowser 版本与公开文档描述存在协议偏差：
   - 写接口实际要求顶层 `cookies` 数组，而不是 `cookie.mode/jsonStr`。
   - 读接口实际直接返回 `data` 数组，而不是 `data.cookie.jsonStr`。
2. `updateCookie` 的 `cookies` 数组是目标环境 Cookie 的**全量替换集合**，不是增量 patch。
3. Core 公开契约使用 Playwright 风格 `expires`，Provider 实际持久化字段使用 `expirationDate`；不转换会得到错误有效期。
4. `sameSite` 回读会转为小写，需要规范化比较。

## 影响

- `.factory/workitems/CR-020/plan.md` 中 Provider API 事实、Provider 单测断言和实现步骤需要修订。
- `env.cookie.ensure` 可把规范化和字段映射后的完整目标集合发送给 VirtualBrowser，调用方必须理解未传 Cookie 会被删除。
- Provider adapter 必须执行 `expires ↔ expirationDate` 和 `sameSite` 规范化，并解析本机实际 `data` 数组响应。
- 新环境 Cookie 文件不存在时的错误需要明确抛出，不能伪装为“当前 Cookie 为空”。

## 建议修复方向

1. 保持模块公开调用形态不变，但明确 `cookies` 是替换后的完整目标集合。
2. Core 不合并当前集合；只要不一致，就用传入集合全量替换。
3. 持久化回读和运行态验证要求完整集合匹配，未传入的既有 Cookie 必须不存在。
4. 单元测试必须精确断言：
   - GET 解析 `data` 数组；
   - POST 使用顶层 `cookies`；
   - 传入集合会全量替换且删除未传 Cookie；
   - `expires` 映射为 `expirationDate`；
   - 日志和异常不包含 API Key 或 Cookie value。
5. 保留读响应兼容解析的空间，但当前版本的写请求以实测顶层 `cookies` 为准，不再把公开文档形态作为本任务的正确断言。

## 证据

- `.factory/workitems/CR-020/evidence/virtualbrowser-cookie-api-probe.md`
- 临时探针：`/tmp/virtualbrowser_cookie_probe.py`（不纳入仓库）

## 用户决策

用户于 2026-07-13 确认：模块传入什么就全部替换为什么，必须删除其他所有 Cookie。原“目标子集 merge”建议作废。
