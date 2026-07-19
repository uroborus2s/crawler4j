# CR-023 根因复现证据

- 日期：2026-07-19
- 环境：`/Users/uroborus/PythonProject/crawler4j/.venv/bin/python`
- 宿主依赖：`packages/crawler4j/pyproject.toml` 仅有 `httpx>=0.28.1`

## 宿主解释器复现

执行导入探测并构造 HTTP/2 Client：

```text
{'httpx': True, 'h2': False, 'hpack': False, 'hyperframe': False, 'brotli': False}
ImportError: Using http2=True, but the 'h2' package is not installed.
```

异常发生在 `httpx.Client(http2=True)` 初始化阶段，请求尚未发出。

## 依赖边界

- 宿主 `uv.lock` 有 `httpx 0.28.1`，但没有 `h2/hpack/hyperframe/brotli` package entries。
- `ctrip_crawler/pyproject.toml` 声明 `httpx[http2,brotli]>=0.28.1,<0.29.0`。
- `ctrip_crawler/uv.lock` 包含 `brotli`、`h2`、`hpack`、`hyperframe`，但这些只属于模块自己的开发虚拟环境。

## 安装预检边界

使用宿主 `.venv` 直接执行 `ModuleRegistry._probe_module_import("ctrip_crawler", module_path)`，结果为：

```text
preflight import passed
```

模块根 `__init__.py` 只描述扫描边界，不构造 HTTP client；真实构造发生在 `objects/_adapters/http/mini_hotel_room_list_transport.py` 的请求路径。因此导入预检可通过，而延迟运行时能力仍然缺失。

## 单一假设验证

假设：宿主未安装 `httpx` 的 `http2` 与 `brotli` extras 是唯一直接原因。证据链同时满足：

1. 宿主解释器缺少 extras 对应包。
2. `httpx.Client(http2=True)` 在同一解释器稳定抛出用户报告的异常。
3. 模块自己的锁文件含完整 extras，但 ZIP 安装链没有依赖安装步骤。
4. 模块导入预检不触发 client 构造。

结论：根因成立；修复必须同时进入宿主统一工具、内部依赖与发布物收集层，模块不得继续直连第三方库，也不能降级 HTTP 版本。
