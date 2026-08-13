# CR-026 HubStudio 批次验证证据

- 候选：2026-08-13 当前工作树
- 验证者：独立 Terra 子任务 `/root/cr026_quality_test`；整改后由主控重新验证
- 结论：`passed`

## 新鲜命令

1. HubStudio + REM/ATM/System/UI 定向契约与回归：`156 passed in 8.68s`，exit `0`。
2. 变更源码和 HubStudio 测试 Ruff：`All checks passed!`，exit `0`。
3. `git diff --check`：无输出，exit `0`。
4. 独立导入 `src.core.rem.provider`：`['playwright_local', 'bitbrowser', 'virtualbrowser', 'hubstudio']`，exit `0`。
5. 独立导入 `src.core.rem.hubstudio_provider`：`get_provider('hubstudio')` 返回 `HubStudioProvider`，exit `0`。

## 整改后最终验证

1. HubStudio、Handle、REM/ATM/System/UI 合并回归：`167 passed in 8.67s`，exit `0`。
2. 全部变更源码和测试 Ruff：`All checks passed!`，exit `0`。
3. `git diff --check`：无输出，exit `0`。
4. Provider registry 探针：`['playwright_local', 'bitbrowser', 'virtualbrowser', 'hubstudio']`，exit `0`。
5. HubStudio 直接导入探针：`HubStudioProvider`，exit `0`。

## 覆盖结果

- 稳定 `containerCode` 与运行时 `browserID` 分离，缓存清理只使用后者。
- 临时和已缓存 `browserID` 路径均在清缓存前停止浏览器。
- HTTP 非成功、非 JSON、`code`、官方 `data.statusCode` 和 cache `failIds` 失败均被显式拒绝。
- 浏览器状态查询定向发送 `containerCodes`，并覆盖官方 `0/1/2/3` 状态，仅 `0` 判断为已开启。
- CDP loopback 探测显式禁用环境代理继承。
- Cookie JSON 字符串与 Core Cookie 字段双向转换。
- 创建代理用 `proxyServer`，更新代理用 `proxyHost`。
- 已有环境导入保留 `containerCode`，运行配置路由为 `provider=hubstudio` + `EnvType.VIRTUAL_BROWSER`。
- 旧 Provider 顺序、默认选择和环境列表列 schema 回归通过。
- HubStudio 不显示 location 修复，刷新指纹对话标明完整回读/location 修复厂商限制。

## 未运行

- 真实 HubStudio E2E：当前未提供本地 HubStudio 客户端、API Key 和可销毁测试环境；本批次用 mock HTTP 契约测试代替。
