# 打包与发布 (Build & Release)

本指南面向**核心开发者**和**运维人员**，详细介绍 Core 应用、SDK 开发包以及文档站点的构建与发布流程。

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
# 产物: dist/crawler4j-0.1.1-py3-none-any.whl
```

## 📦 SDK 打包与发布 (SDK)

`crawler4j-sdk` 是需要单独分发给插件开发者的依赖包。它位于项目根目录的 `crawler4j_sdk/` 文件夹下。

### 1. 构建 SDK Wheel
SDK 拥有独立的 `pyproject.toml` 配置。

```bash
cd crawler4j_sdk
uv build
```

构建完成后，在 `crawler4j_sdk/dist/` 目录下会生成：
*   `crawler4j_sdk-1.0.0-py3-none-any.whl`
*   `crawler4j_sdk-1.0.0.tar.gz`

### 2. 发布到 PyPI
将构建好的 SDK 包发布到 PyPI 仓库，以便用户通过 `pip install crawler4j-sdk` 安装。

```bash
# 确保已通过 twine 配置好 credentials
uv run twine upload crawler4j_sdk/dist/*
```

## 📚 文档构建与部署 (Docs)

文档站点基于 MkDocs 构建。

### 1. 构建静态站点
生成的 HTML 文件适合部署到 Nginx、Apache 或对象存储（如 AWS S3, Aliyun OSS）。

```bash
uv run mkdocs build
```

*   **产物目录**: `site/`
*   **部署方式**: 将 `site/` 目录下的所有文件上传至 Web 服务器根目录。

### 2. 发布到 GitHub Pages
如果项目托管在 GitHub，可以使用内置命令一键部署：

```bash
uv run mkdocs gh-deploy
```

该命令会自动构建文档并将结果推送到仓库的 `gh-pages` 分支。

## 💻 开发环境调试 (Dev Mode)

### 1. 调试 Core 应用
在开发 Core 代码时，推荐以下启动方式：

*   **IDE 启动**: 将 `src/ui/app.py` 设为启动脚本，工作目录设为项目根目录。
*   **命令行启动**:
    ```bash
    uv run python -m src.ui.app
    ```
*   **调试日志**: 设置环境变量 `LOG_LEVEL=DEBUG` 开启详细日志。

### 2. 调试 SDK CLI
在开发 `crawler4j` 命令行工具时，无需每次打包安装。可以直接从源码运行 CLI：

```bash
# 格式: uv run python -m <cli_entry_point> <command> [args]

# 初始化项目示例
uv run python -m crawler4j_sdk.cli.commands init my_test_project

# 运行 help
uv run python -m crawler4j_sdk.cli.commands --help
```

### 3. 调试文档
在编写文档时，启动本地实时预览服务：

```bash
uv run mkdocs serve
```

*   访问地址: [http://127.0.0.1:8000](http://127.0.0.1:8000)
*   特性: 保存文件后浏览器会自动刷新 (Live Reload)。
