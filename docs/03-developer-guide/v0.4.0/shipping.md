# 交付模块

> 版本绑定：本文只适用于 0.4.x SDK / Contracts 与 Core 0.4.0。0.4.x ZIP 包不需要兼容 0.3.x 宿主安装链或旧模块结构。

0.4.0 模块交付物仍是 ZIP。差异在发布前质量门：

- 必须通过装饰器扫描
- 必须生成 manifest lock
- 必须阻断 workflow 普通参数
- 必须阻断宿主保留数据字段

DevLink 只服务开发联调，不是正式交付。

## 发布前检查

```bash
uv run crawler4j check structure
uv run crawler4j manifest lock
uv run crawler4j check full
uv run crawler4j check release
```

这里至少确认：

- `module.yaml.runtime_api == core-native-v2`
- 装饰器名称唯一
- 对象图无环
- workflow 不声明 parameters
- component 参数合法
- page action 纯函数约束通过
- 数据表、索引、查询输出不使用宿主保留字段
- manifest lock 与源码一致
- 运行时代码没有依赖 `crawler4j-sdk`

`package build` 会先执行 full gate 再刷新 lock；因为 full gate 要求已有 lock 且未过期，发布前必须先运行 `manifest lock`。

源码目录里的 `.venv/`、`dist/`、`build/`、`.git/`、缓存目录和 `*.egg-info/` 不进入 manifest lock 或 ZIP 文件集合。这些忽略目录内的 symlink 不会阻断打包；模块源码、数据、页面、工作流等实际交付文件里的 symlink 仍会被拒绝。`package verify` 对正式 ZIP 包的安全策略不变：ZIP 内 symlink 和路径穿越仍然失败。

## 构建 ZIP

```bash
uv run crawler4j package build
uv run crawler4j package verify dist/<module>-<version>.zip
```

默认产物：

```text
dist/<module>-<version>.zip
```

## ZIP 结构

最小结构：

```text
hotel_demo/
  module.yaml
  __init__.py
  pyproject.toml
  .crawler4j/
    manifest.lock.json
  interfaces/
  objects/
  workflows/
  tasks/
  data/
  pages/
  candidates/
  cleanups/
```

关键约束：

- ZIP 只有一个根目录
- 根目录下有 `module.yaml`
- `runtime_api` 是 `core-native-v2`
- `.crawler4j/manifest.lock.json` 存在且未过期
- `candidates/` 存在；它是结构校验要求目录
- `cleanups/` 存在；它是标准扫描目录，建议随模块骨架保留
- `module.yaml.upgrade_source.repo` 是合法 `owner/repo`
- 运行时代码只依赖 `crawler4j-contracts`；网络等第三方能力通过宿主公开的 `ctx.tools` 方法使用

## 宿主安装与升级

本地验收：

```bash
# Shell B: crawler4j 宿主源码仓或已安装宿主环境
cd /absolute/path/to/crawler4j-host
uv run crawler4j host install preview /absolute/path/to/module/dist/<module>-<version>.zip --skip-remote-check
uv run crawler4j host install apply /absolute/path/to/module/dist/<module>-<version>.zip --skip-remote-check
```

这里安装的是 ZIP，不是 DevLink 源码目录。先在模块根完成 `package build` 和 `package verify`，再把 ZIP 的绝对路径交给宿主安装命令。

正式发布：

```bash
uv run crawler4j release status
uv run crawler4j release publish --dry-run
uv run crawler4j release publish
uv run crawler4j host upgrade check <module_name>
uv run crawler4j host upgrade preview <module_name>
uv run crawler4j host upgrade apply <module_name>
```

## Release 边界

GitHub Release 只负责分发 ZIP，不负责安装。

约束：

- 每个可安装 Release 只提供一个 ZIP 资产
- ZIP 内 `module.yaml.version` 与 Release 版本一致
- ZIP 内 `upgrade_source.repo` 与目标仓库一致

## 运行时依赖

模块与宿主运行在同一 Python 进程，但第三方库仍由宿主统一拥有和封装。模块 ZIP 不安装第三方依赖，也不能把宿主 `site-packages` 当成公共 API 直接 import。

需要原始 HTTP/2 请求时，使用 full runtime surface 提供的宿主方法：

```python
response = await ctx.tools.call(
    "http.request",
    method="POST",
    url=url,
    headers=header_items,
    content=body_bytes,
    proxy_url=proxy_url,
    http2=True,
    require_http2=True,
    follow_redirects=False,
    timeout=30.0,
)
```

返回值是宿主中立的 mapping，包含 `status_code`、保留重复项的 `headers`、已解码的 `content` bytes 和 `http_version`。模块负责检查业务状态码和解析业务 payload；`require_http2=True` 时宿主拒绝 HTTP/1.1 协议降级。该工具不在 Hosted UI 声明/只读面或环境候选面开放。

`httpx[http2,brotli]`、`h2/hpack/hyperframe/brotli` 都是宿主内部实现依赖，不是模块公共依赖。`crawler4j-contracts` 是模块与 Core 的唯一公共契约包：

允许：

```python
from crawler4j_contracts import component, workflow, page_action
```

禁止：

```python
from crawler4j_sdk import ...
```

`crawler4j-sdk` 可以出现在开发依赖中，不能成为模块运行条件。

模块自己的 `pyproject.toml` 用于 DevLink、单测和开发环境复现。ZIP 安装器不会执行它，也不会现场安装 `h2` 或其他第三方包。生产模块只能通过已定义的 Core/Contracts 公共能力访问第三方能力；`ctrip_crawler` 的生产依赖应移除 `httpx`，开发测试可以使用 mock/fake 验证宿主调用参数。

安装或升级新的宿主后，可执行：

```bash
# 1. crawler4j 开发 workspace / 源码环境
uv sync --all-packages
uv run python -m src.ui.app --crawler4j-verify-http-runtime

# 2. wheel 安装环境：先安装/升级新构建的宿主 wheel，再从该解释器运行
uv pip install --upgrade /absolute/path/to/crawler4j-0.4.40-py3-none-any.whl
python -m src.ui.app --crawler4j-verify-http-runtime

# 3. PyInstaller 桌面发布物（macOS 示例）：必须安装新构建的整包
Crawler4j.app/Contents/MacOS/Crawler4j --crawler4j-verify-http-runtime

# Windows onedir/Velopack 发布物在 Windows 构建机复验
Crawler4j.exe --crawler4j-verify-http-runtime
```

检查成功会输出 `httpx/h2/hpack/hyperframe/brotli` 版本和 `"http2_client": "ok"`。开发 workspace 要更新 lock/venv；wheel 用户要升级宿主 wheel；桌面用户要升级整个目标平台发布包，不能只修改源码虚拟环境。模块 ZIP 在三种情况下都不安装 `h2`。失败不得改成 HTTP/1.1 重试。

## 验收口径

完成交付至少看到这些事实：

1. `check full` 通过
2. `manifest lock` 已生成且未过期
3. `check release` 通过
4. `package verify` 通过
5. 宿主能安装 ZIP
6. 模块详情页来源不是 `开发链接`
7. 运行模板能展示对象装配树
8. 任务执行时每个 task/env 都创建独立对象实例
9. 数据表和只读视图通过 `ctx.db` 可访问
10. 模块使用 `http.request` 时不直接 import `httpx/h2/brotli`，且目标宿主 release 已通过 HTTP 运行时检查
