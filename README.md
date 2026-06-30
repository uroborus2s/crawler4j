# 蛛行演略（crawler4j）

`crawler4j` 是一个面向本地执行的自动化脚本宿主与模块开发工具集。

它把桌面管理、浏览器环境、任务调度、日志、数据表、Hosted UI、模块校验和打包这些通用能力放在宿主侧；业务逻辑以标准模块的形式开发、调试、安装和运行。

本仓库开源的是基础框架、SDK、共享契约和桌面宿主。它不包含任何面向特定第三方站点的规则、账号、数据、绕过逻辑或使用授权。

> 本项目是 Python 项目，不是 Java 生态中的同名爬虫库，也与其无隶属关系。

## 适合做什么

- 把重复性的浏览器操作整理成可运行、可调试、可记录的本地任务。
- 为业务自动化脚本提供统一的运行环境、配置、日志和结果入口。
- 用 `crawler4j-sdk` 创建标准模块，再交给宿主安装和执行。
- 在模块中声明数据表、页面、用户动作、环境候选和清理候选，让宿主统一托管。
- 构建面向内部团队或自用场景的桌面自动化工具。

## 不适合做什么

- 不适合作为托管爬虫平台、数据采集服务或反检测服务直接使用。
- 不提供绕过登录授权、验证码、风控、访问控制、频率限制或其他安全机制的能力承诺。
- 不内置任何第三方网站、App 或服务的采集规则。
- 不替代法律、合规、安全或目标系统授权审查。

请只在你有权操作的系统、账号、数据和页面上使用本项目，并遵守适用法律、服务条款、隐私要求、robots 规则和访问频率限制。

## 仓库结构

```text
crawler4j/
├── packages/
│   ├── crawler4j/            # 桌面宿主与 Core 运行时
│   ├── crawler4j-sdk/        # 模块开发 SDK 与 CLI
│   └── crawler4j-contracts/  # Core / SDK / 模块共享契约
├── scripts/                  # workspace 级开发、验证和打包脚本
├── docs/                     # 用户、开发者和项目维护文档
├── .factory/                 # 项目记忆与工作项
├── pyproject.toml            # uv workspace 配置
└── uv.lock                   # 全仓统一锁文件
```

## 快速开始

前置条件：

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/uroborus2s/crawler4j.git
cd crawler4j

uv sync --all-packages
uv run python -m src.ui.app
```

常用开发命令：

```bash
# 运行测试
uv run pytest -q

# 运行 lint
uv run ruff check .

# 启动桌面 UI smoke
uv run python scripts/smoke_test_ui.py

# 构建 workspace 包
uv run build
```

桌面应用依赖 PyQt、Playwright 等本地能力；首次运行时可能还需要按操作系统补齐浏览器、图形界面或打包工具链依赖。

## 开发自动化模块

模块开发优先使用 SDK CLI：

```bash
uvx --from crawler4j-sdk crawler4j module init
```

标准模块使用 `core-native-v2` 契约。模块运行时代码应依赖 `crawler4j-contracts`，SDK 只作为开发依赖提供脚手架、扫描、校验、manifest lock 和打包辅助。

典型模块目录：

```text
demo_module/
├── module.yaml
├── .crawler4j/manifest.lock.json
├── interfaces/
├── objects/
├── workflows/
├── tasks/
├── data/
├── pages/
├── candidates/
└── cleanups/
```

更多模块开发说明见 [开发者指南](docs/03-developer-guide/index.md)。

## 当前状态

当前源码主线处于 `0.x` 阶段，接口和模块契约仍可能在小版本中调整。请以仓库内文档、包版本和发布说明为准，不要只根据 Git tag 推断当前源码状态。

当前 workspace 包：

- `crawler4j`: 桌面宿主与 Core 运行时
- `crawler4j-sdk`: 模块开发 SDK 与 CLI
- `crawler4j-contracts`: Core、SDK 和模块共享契约

## 文档

- [入门说明](docs/01-getting-started/index.md)
- [用户指南](docs/02-user-guide/index.md)
- [开发者指南](docs/03-developer-guide/index.md)
- [项目维护文档](docs/04-project-development/index.md)

## 贡献

欢迎提交 Issue 和 Pull Request。提交前请尽量运行：

```bash
uv run pytest -q
uv run ruff check .
```

请不要提交真实账号、密钥、Cookie、Token、个人数据、未授权目标系统的专用规则，或用于规避访问控制和安全机制的实现。

## 许可证

本项目以 [MIT License](LICENSE) 开源。

第三方依赖、外部浏览器、系统组件和可选打包工具仍适用各自的许可证和使用条款。
