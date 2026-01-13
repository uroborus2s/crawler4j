# 快速开始 (Quick Start)

本指南针对**最终用户**，介绍如何下载、安装并运行 Crawler4j 桌面应用。

## � 获取应用

请前往 Release 页面下载适用于您操作系统的安装包：

### Windows
*   下载 `.exe` 绿色版压缩包 (e.g., `Crawler4j-v0.1.0-win64.zip`)。
*   解压到任意目录（建议不要包含中文路径）。

### macOS
*   下载 `.dmg` 镜像文件 (e.g., `Crawler4j-v0.1.0-mac.dmg`)。
*   打开镜像，将 `Crawler4j.app` 拖入 `Applications` 文件夹。

> [!NOTE]
> macOS 用户首次打开可能会提示"无法验证开发者"。请并在"系统设置 -> 隐私与安全性"中点击"仍要打开"。

### Linux
*   下载二进制文件包 (e.g., `crawler4j-linux-x64.tar.gz`)。
*   解压并赋予执行权限。

## ▶️ 初次运行

1.  **启动应用**: 双击 `Crawler4j` 图标启动。
2.  **初始化**: 首次运行时，应用会自动初始化本地数据库 (`config.db`)。
3.  **检查状态**: 
    *   查看底部的状态栏，确认 "System: Ready"。
    *   如果显示 "Browser: Installing"，说明系统正在后台下载 Playwright 浏览器内核，请耐心等待完成。

## 🎮 运行您的第一个任务

1.  点击左侧导航栏的 **"模块 (Modules)"** 图标。
2.  在模块列表中找到 **"Example Task"** (示例任务)。
3.  点击右侧的 **"Run" (运行)** 按钮。
4.  观察弹出的日志窗口，您将看到任务执行的全过程。

恭喜！您已经成功运行了 Crawler4j。
