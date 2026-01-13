# Crawler4j

**Crawler4j** 是一个基于 Python 的自动化监控与任务执行平台，采用**微内核 + SDK + 插件**架构，支持动态加载和并发执行自动化任务。

[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://uroborus2s.github.io/crawler4j/)
[![Python](https://img.shields.io/badge/python-3.12+-green)](https://www.python.org/)

---

## 📚 文档

详细文档请访问：**[https://clawler.uroborus.cn](https://clawler.uroborus.cn)**

| 文档 | 说明 |
|------|------|
| [快速开始](https://clawler.uroborus.cn/getting-started/) | 下载安装与首次运行 |
| [用户指南](https://clawler.uroborus.cn/user-guide/configuration/) | 配置策略与部署 |
| [插件开发](https://clawler.uroborus.cn/plugin-dev/tutorial-crawler/) | 编写自定义爬虫 |
| [SDK 参考](https://clawler.uroborus.cn/user-guide/sdk/api/) | API 与 CLI 手册 |

---

## 🏗️ 架构概览

Crawler4j 采用 **Core + Modules** 架构，将基础设施与业务逻辑分离。

```mermaid
graph TD
    User[用户] --> UI[桌面客户端 (Core)]
    UI --> TSM[策略管理 TSM]
    TSM --> ATM[任务管理 ATM]
    ATM --> REM[环境管理 REM]
    
    subgraph Plugins [业务插件]
        P1[携程机票]
        P2[数据监控]
    end
    
    REM -.->|SDK 契约| Plugins
```

---

## 🚀 快速开始

### 方式一：下载安装包 (推荐)

对于最终用户，无需安装 Python 环境，直接下载编译好的二进制文件：

*   **Windows**: 下载 `.exe` 绿色包
*   **macOS**: 下载 `.dmg` 镜像
*   **Linux**: 下载二进制文件

👉 [前往发布页下载](https://github.com/uroborus2s/crawler4j/releases)

### 方式二：从源码运行 (开发者)

```bash
# 1. 克隆代码
git clone https://github.com/uroborus2s/crawler4j.git
cd crawler4j

# 2. 安装依赖 (使用 uv)
uv sync

# 3. 启动应用
uv run python -m src.ui.app
```

---

## 📁 项目结构

```
crawler4j/
├── src/                      # Core 内核源码
├── crawler4j_sdk/            # SDK 源码 (独立包)
├── modules/                  # 内置业务模块
├── docs/                     # 文档源文件 (MkDocs)
├── dist/                     # 构建产物 (.exe/.whl)
└── pyproject.toml            # 项目配置
```

---

## 🔧 开发者指南

### 构建发行版

```bash
# 构建 .exe/.app
uv run pyinstaller crawler4j.spec

# 构建 Python Wheel
uv build
```

### 调试 SDK

```bash
# 本地运行 CLI
uv run python -m crawler4j_sdk.cli.commands --help
```

详细内容请查阅 [开发者文档](https://clawler.uroborus.cn/user-guide/build-release/)。

---

## ⚠️ 免责声明

> [!CAUTION]
> 本项目及所含工具仅供技术研究与学习使用。使用者应严格遵守目标网站的 Robots 协议及相关法律法规。
> 作者不对使用本工具产生的任何后果负责。