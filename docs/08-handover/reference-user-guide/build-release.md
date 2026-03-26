# 打包与发布 (Build & Release)

> 本文档当前保留为旧专题详细参考。
> 其中涉及 MkDocs 文档站的内容仅作为历史记录保留，当前仓库已移除静态文档站职责。
> 当前正式发布与运行入口请优先阅读：
> [发布说明](../06-release/release-notes.md)、
> [部署与运行说明](../07-operations/deployment-guide.md)、
> [文档索引](../traceability/document-index.md)。

本指南面向**核心开发者**和**运维人员**，详细介绍 Core 应用、SDK 开发包以及历史发布流程中的构建做法。

## 🛠️ Core 应用构建 (Application)

Core 是最终用户使用的桌面应用程序。

### 1. 独立可执行文件 (.exe / .app)
使用 `PyInstaller` 将应用打包为无需 Python 环境的独立程序。

**Windows (.exe)**:
```powershell
uv run pyinstaller crawler4j.spec
# 产物: dist/Crawler4j/Crawler4j.exe
```

**macOS (.app)**:
```bash
uv run pyinstaller crawler4j.spec
# 产物: dist/Crawler4j.app
```

> [!IMPORTANT]
> PyInstaller 不支持交叉编译。请在目标操作系统上执行打包命令。

### 2. Python Wheel 包
如果您希望通过 `pip install` 分发应用：

```bash
uv build
# 产物: dist/crawler4j-<root-version>-py3-none-any.whl
```

## 📦 SDK 与 Contracts 打包与发布 (SDK)

`crawler4j-sdk` 是开发者直接安装的 SDK 包；`crawler4j-contracts` 是 SDK 和 Core 共享的稳定契约包。两者都需要发布，model 项目安装链路才完整。

### 1. 构建 Wheel
两个包都拥有独立的 `pyproject.toml` 配置。

```bash
cd crawler4j_contracts
uv build

cd crawler4j_sdk
uv build
```

构建完成后，会生成：
*   `crawler4j_contracts/dist/crawler4j_contracts-1.0.1-py3-none-any.whl`
*   `crawler4j_contracts/dist/crawler4j_contracts-1.0.1.tar.gz`
*   `crawler4j_sdk/dist/crawler4j_sdk-1.0.2-py3-none-any.whl`
*   `crawler4j_sdk/dist/crawler4j_sdk-1.0.2.tar.gz`

### 2. 发布到 PyPI
将构建好的两个包都发布到 PyPI 仓库。

```bash
# 确保已通过 twine 配置好 credentials
uv run twine upload crawler4j_contracts/dist/*
uv run twine upload crawler4j_sdk/dist/*
```

发布顺序建议：

1. 先发布 `crawler4j-contracts`
2. 再发布 `crawler4j-sdk`

因为 `crawler4j-sdk` 依赖 `crawler4j-contracts>=1.0.0,<2.0.0`。

## 📚 文档说明 (Docs)

当前仓库只保留 `docs/` 下的 Markdown 文档树，不再构建或发布 MkDocs 静态站点。
如需查看和维护文档，请直接阅读或编辑仓库中的 Markdown 文件。

## 💻 开发环境调试 (Dev Mode)

### 1. 调试 Core 应用
在开发 Core 代码时，推荐以下启动方式：

*   **IDE 启动**: 将 `src/ui/app.py` 设为启动脚本，工作目录设为项目根目录。
*   **命令行启动**:
    ```bash
    uv run python -m src.ui.app
    ```
*   **调试日志**: 设置环境变量 `LOG_LEVEL=DEBUG` 开启详细日志。

### 2. 验证 SDK CLI
`crawler4j` 命令由已发布的 `crawler4j-sdk` 包提供。验证时不再使用源码入口，而是直接通过已发布包检查：

```bash
# 一次性运行已发布 CLI
uvx --from crawler4j-sdk crawler4j --help

# 或先安装为本地工具，再长期使用
uv tool install crawler4j-sdk
crawler4j init-model my_test_project --no-install

# 如果项目目录里已经执行过 uv sync，也可以在项目内使用
cd my_test_project
uv run crawler4j --help
```

### 3. 调试文档
当前不再提供仓库内置的文档站预览命令。
编写文档时，直接使用 IDE 或 Markdown 阅读器进行本地预览即可。
