# 部署与打包 (Deployment & Build)

本节介绍如何将 Crawler4j 构建为可分发的安装包（.whl, .exe, .app）。

## 📦 Python 包构建 (.whl)

适用于部署到已安装 Python 环境的服务器。

### 1. 构建 Core 和 SDK
在项目根目录下运行构建命令：

```bash
uv build
```

产物 `dist/crawler4j-0.1.1-py3-none-any.whl` 可通过 pip 安装。

## 🖥️ 可执行文件构建 (.exe / .app)

适用于分发给最终用户的独立应用程序（无需用户安装 Python）。项目使用 **PyInstaller** 进行打包。

### Windows 打包 (.exe)

1.  **准备环境**: 确保在 Windows 环境下运行。
2.  **执行打包**:

```bash
uv run pyinstaller crawler4j.spec
```

3.  **获取产物**: 
    生成的可执行文件位于 `dist/Crawler4j/Crawler4j.exe`。您可以将整个 `dist/Crawler4j` 文件夹压缩分发。

> [!TIP]
> 如果需要生成单文件 exe，请修改 `crawler4j.spec` 中的 `console=False` 和相关配置，或者使用 `--onefile` 参数（注意单文件启动速度较慢）。

### macOS 打包 (.app)

1.  **准备环境**: 确保在 macOS 环境下运行。
2.  **执行打包**:

```bash
uv run pyinstaller crawler4j.spec
```

3.  **获取产物**:
    生成的应用包位于 `dist/Crawler4j.app`。您可以直接双击运行，或将其压缩为 `.dmg` / `.zip` 分发。

> [!NOTE]
> **关于签名**: 默认构建的 .app 未经过 Apple 开发者签名。在其它机器上运行时，可能需要右键点击并选择"打开"以绕过安全检查，或自行配置代码签名证书。

### 注意事项

*   **Playwright 浏览器**: 打包后的程序通常不包含 Playwright 浏览器二进制文件。用户首次运行时会自动下载，或者您可以手动将 `~/mb/Library/Caches/ms-playwright` (macOS) 或 `%USERPROFILE%\AppData\Local\ms-playwright` (Windows) 下的浏览器文件夹复制到打包产物的相应位置，并通过环境变量 `PLAYWRIGHT_BROWSERS_PATH` 指定。
*   **平台限制**: PyInstaller 不支持跨平台交叉编译。要打 Windows 包必须在 Windows 上运行，打 macOS 包必须在 macOS 上运行。

## 📚 文档构建

如果您需要离线部署文档站点：

```bash
uv run mkdocs build
```

构建完成后，静态 HTML 文件将生成在 `site/` 目录下。
