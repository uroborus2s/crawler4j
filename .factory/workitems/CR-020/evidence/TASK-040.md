# TASK-040 完成前验证证据

## 基本信息

- Work item：`CR-020`
- Task：`TASK-040`
- Actor：Codex `/root`
- 时间：2026-07-13 22:17 +08:00
- 验证声明：Core 已实现 full runtime `env.cookie.ensure` 的完整集合全量替换、持久化复核、严格重启、运行态完整集合校验和 TaskContext/tools 回绑。
- 结论：`passed`

## Red-Green

### Red

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_env_cookie_service.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py -q -p no:cacheprovider
```

- exit code：`2`
- 预期失败原因：`cookie_service` 和新 Core 工具尚未实现。
- 实际失败原因：collection 报 `ModuleNotFoundError: No module named 'src.core.rem.cookie_service'`。
- 是否匹配：是。

### Green 目标集

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_env_cookie_service.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py -q -p no:cacheprovider
```

- exit code：`0`
- 真实输出：`107 passed in 2.63s`
- failures/errors/skipped：`0/0/0`

## 完整验证

### Ruff format

```bash
uv run ruff format --check packages/crawler4j/src/core/rem/cookie_service.py packages/crawler4j/src/core/rem/provider.py packages/crawler4j/src/core/rem/manager.py packages/crawler4j/src/core/atm/runtime_capabilities.py packages/crawler4j/tests/unit/test_core/test_rem/test_env_cookie_service.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py
```

- exit code：`0`
- 真实输出：`8 files already formatted`

### Ruff check

```bash
uv run ruff check packages/crawler4j/src/core/rem/cookie_service.py packages/crawler4j/src/core/rem/provider.py packages/crawler4j/src/core/rem/manager.py packages/crawler4j/src/core/atm/runtime_capabilities.py packages/crawler4j/tests/unit/test_core/test_rem/test_env_cookie_service.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py
```

- exit code：`0`
- 真实输出：`All checks passed!`

### 完整 unit

```bash
uv run pytest packages/crawler4j/tests/unit -q -p no:cacheprovider
```

- exit code：`0`
- 真实输出：`1176 passed in 30.74s`
- failures/errors/skipped：`0/0/0`

### Diff

```bash
git diff --check
```

- exit code：`0`
- 输出：空，未发现 whitespace error。

## VirtualBrowser 实际接口

```bash
uv run python /tmp/virtualbrowser_cookie_probe.py
```

- exit code：`0`
- 使用生产 `VirtualBrowserClient.get_cookies/replace_cookies`，不是探针自带 HTTP 读写 helper。
- 第一次全量写 A、B：回读 2 个。
- 第二次只写 A：回读 1 个，B 已删除。
- 空列表：回读 0 个。
- `expires → expirationDate`、domain/path/secure/httpOnly/sameSite 回读匹配。
- 一次性环境删除成功。
- API Key 和 Cookie value 未输出。

## 需求逐项核对

| AC | 证据 | 结论 |
|---|---|---|
| AC-020-001 | runtime capabilities surface 测试 | full 注册，受限 surface 不注册 |
| AC-020-002 | ATM 工具测试和精确调用签名 | 四个 bool，成功 `runtime_matched=True` |
| AC-020-003 | service 幂等测试 | 完整集合一致时不写、不重启 |
| AC-020-004 | service 全量替换测试、生产 API 探针 | 未传 Cookie 删除，写后回读并严格重启 |
| AC-020-005 | 同 env 并发测试 | 最大并行读为 1 |
| AC-020-006 | ATM 回绑测试 | 新 page/context 回绑，browser tools 指向新 Page |
| AC-020-007 | 持久化失败测试和异常路径 | 失败抛异常，不返回部分成功 |
| AC-020-008 | Client 安全异常测试和探针输出 | API Key/Cookie value 不进入异常或输出 |

## 偏离与残余风险

- 未运行真实携程模块 E2E：需要真实 cticket 和模块侧接线，本任务只交付 Core。
- 未用一次性环境完成真实 stop/start/CDP 重连 E2E：本机一次性环境此前存在 VirtualBrowser `launchBrowser` DevTools 端口探测问题；本任务以 Provider 严格关闭单测、REM/ATM 回归和真实 Cookie API 探针覆盖。真实业务环境联调仍建议由模块侧执行。
