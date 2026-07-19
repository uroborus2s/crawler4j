# CR-023 完成前验证报告

- Work item：`CR-023`
- Task：`TASK-043`
- 当前结论：宿主源码、隔离 wheel 和 macOS arm64 PyInstaller 运行时的 HTTP/2/Brotli 能力通过；外部 `ctrip_crawler` 改接与 Windows 目标平台仍为后续发布门。

## 已通过

- `http.request` 只在 full runtime surface 暴露，模块只传标准 Python 类型。
- 宿主依赖、uv lock、wheel METADATA、PyInstaller module/distribution metadata 收集一致。
- 定向/邻近 `152 passed`；全量 unit `1265 passed`。
- 源码、隔离 wheel 和 macOS 冻结入口均可导入 HTTP/2/Brotli 依赖并成功构造 `httpx.Client(http2=True)`。
- 重复 headers、raw body、Brotli 解码、代理、严格参数与 HTTP/2 拒绝降级回归通过。

## 不得扩大声明

- 当前 `ctrip_crawler 0.3.9` 仍有直接 `httpx` transport；在其迁移到 `await ctx.tools.call("http.request", ...)` 并完成真实 E2E 前，不宣称业务模块闭环。
- 本机 macOS 证据不代表 Windows 冻结发布物已验证。
- 模块 ZIP 不安装 `h2` 或其他第三方运行时依赖。
