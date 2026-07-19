# TASK-043 实现报告

## 结论

crawler4j 0.4.40 已把 HTTP/2/Brotli 收口为 full runtime 的宿主统一方法 `ctx.tools.call("http.request")`。模块不安装、也不直接 import `httpx/h2/brotli`。源码解释器、隔离 wheel 与 macOS arm64 PyInstaller app 的宿主运行时检查均通过。

## 实现

- Core ATM 新增异步 `http.request`，输入输出只使用标准 Python 类型。
- Core 内部以 `httpx.Request + AsyncClient.send` 发送一次请求，保留调用方提供的有序/重复 headers 与 raw body。
- `require_http2=True` 强制 `http2=True`，实际协议不是 HTTP/2 时抛 `HOST_HTTP2_NOT_NEGOTIATED`，不回退。
- 工具只在 full runtime surface 注册；Hosted UI、环境候选和清理候选不开放。
- 宿主依赖改为 `httpx[http2,brotli]>=0.28.1`，lock 纳入 `h2/hpack/hyperframe/brotli`。
- PyInstaller 同时收集四个运行包的模块与 `httpx/h2/hpack/hyperframe/Brotli` distribution metadata。
- 源码与冻结入口新增 `--crawler4j-verify-http-runtime` 诊断，不启动 GUI/数据库。

## 验证

- 定向/邻近：`152 passed`。
- 全量 unit：`1265 passed`。
- 独立 review 的重复请求头、Brotli 解码、布尔参数严格校验与状态文档建议已修复。
- Ruff、lock、docs-stratego、JSON、diff：通过。
- wheel：0.4.40 build/METADATA/隔离安装/runtime/tool surface：通过。
- macOS arm64 PyInstaller：首轮 metadata RED 已修复，复建 runtime check：通过。

## 未闭环边界

- Windows 必须在 Windows 构建机重建并执行同一 runtime check。
- 当前 `ctrip_crawler 0.3.9` 仍直接 import `httpx`；其外部仓库必须改为 await 宿主 `http.request`，并补 DevLink + ZIP 真实房型 E2E。
- 通用 manifest 机器可读宿主能力/版本协商保持后续架构项；本轮不增加任意模块依赖安装器。
