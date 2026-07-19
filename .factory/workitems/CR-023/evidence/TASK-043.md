# TASK-043 验证证据

- Work item：`CR-023`
- Actor：Codex
- 时间：2026-07-19
- 状态：`verification_passed`

## RED

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_system/test_http_runtime.py packages/crawler4j/tests/unit/test_ui/test_app.py packages/crawler4j/tests/unit/test_sdk/test_packaging_config.py -q -p no:cacheprovider
```

真实结果：测试收集阶段 1 error；`ModuleNotFoundError: No module named 'src.core.system.http_runtime'`。

失败原因符合预期：宿主尚无可执行 HTTP/2/Brotli 能力检查，依赖 extras 与 PyInstaller 收集配置也尚未实现。

## 架构修订 RED

用户明确裁决“必须由宿主统一提供方法，模块不能自行安装/调用库”后，新增 `http.request` 契约测试：

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_atm/test_http_tools.py -q -p no:cacheprovider
```

真实结果：`3 failed, 2 passed`；失败原因分别为 `src.core.atm.http_tools` 不存在与 full surface 未注册 `http.request`，符合修订后的 RED 预期。

## GREEN

统一 HTTP 工具实现后的新鲜结果：

```text
uv run pytest .../test_http_tools.py .../test_runtime_capabilities.py -q -p no:cacheprovider
50 passed in 0.53s

uv run pytest .../test_http_tools.py -q -p no:cacheprovider
5 passed in 0.12s

uv run ruff check .../http_tools.py .../runtime_capabilities.py .../test_http_tools.py
All checks passed!
```

此前宿主依赖/诊断 GREEN：聚焦与相邻回归 `95 passed in 2.88s`；源码入口输出 `httpx=0.28.1, h2=4.3.0, hpack=4.2.0, hyperframe=6.1.0, brotli=1.2.0, http2_client=ok`；`uv lock --check` 通过。

## 回归

- 定向/邻近测试：HTTP tool、runtime capability、system runtime、UI app、packaging 和外部模块安装共 `152 passed in 1.15s`。
- 全量测试：`1265 passed in 30.82s`。
- 静态/结构：全仓 Ruff、`uv lock --check`、docs-stratego（`pages=87 contracts=0`）、`.factory/project.json` JSON 与 `git diff --check` 通过。

## Wheel

- 构建：`crawler4j-0.4.40-py3-none-any.whl` 与 sdist 成功。
- METADATA：`Requires-Dist: httpx[brotli,http2]>=0.28.1`。
- 全新 Python 3.12 venv 安装：自动安装 `brotli 1.2.0`、`h2 4.3.0`、`hpack 4.2.0`、`hyperframe 6.1.0`。
- 从 `/private/tmp/crawler4j-cr023-wheel-final-20260719` 启动隔离 wheel：诊断输出 `http2_client=ok`，full runtime `http.request=available`。

## PyInstaller

首轮 macOS arm64 冻结 smoke 真实失败：

```text
PackageNotFoundError: No package metadata was found for httpx
```

原因是诊断函数依赖 distribution metadata，而 spec 只收集了模块代码。新增 packaging RED 后，spec 对 `httpx/h2/hpack/hyperframe/Brotli` 执行 `copy_metadata`，重新构建 `Crawler4j.app`。最终冻结入口输出：

```json
{"brotli":"1.2.0","h2":"4.3.0","hpack":"4.2.0","http2_client":"ok","httpx":"0.28.1","hyperframe":"6.1.0"}
```

## 偏离

- 未运行：Windows PyInstaller/Velopack 目标平台 runtime smoke；`ctrip_crawler` 外部仓库改接与真实房型 E2E。
- 原因：Windows 构建必须在 Windows 目标平台执行；ctrip 仓库不属于当前可写宿主 workspace。
- 风险：不得据 macOS/宿主结果声明 Windows 发布物或外部 ctrip 业务 E2E 完成。
