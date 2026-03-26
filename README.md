# Crawler4j

**Crawler4j** 是一个基于 Python 的自动化监控与任务执行平台，采用**微内核 + SDK + 插件**架构，支持动态加载和并发执行自动化任务。

[![Python](https://img.shields.io/badge/python-3.12+-green)](https://www.python.org/)

---

## 📚 文档

详细文档已统一收敛到仓库内的 `docs/` Markdown 体系。

| 文档 | 说明 |
|------|------|
| [快速开始](docs/08-handover/getting-started.md) | 下载安装与首次运行 |
| [接手与日常使用指南](docs/08-handover/user-guide.md) | 配置、运行与接手顺序 |
| [模块开发指南](docs/08-handover/module-developer-guide.md) | 从创建模块项目到 DevLink 调试和 zip 安装验收 |

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
├── modules/                  # 内置模块占位说明
├── docs/                     # 仓库内 Markdown 文档体系
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

### CLI 与模块开发

```bash
# 方式 1：安装 SDK CLI
uv tool install crawler4j-sdk

# 直接使用
crawler4j --help

# 方式 2：不安装，直接使用已发布 CLI
uvx --from crawler4j-sdk crawler4j --help
```

详细内容请查阅 [部署与运行说明](docs/07-operations/deployment-guide.md)。

---

## ⚠️ 免责声明

> [!CAUTION]
> 本项目及所含工具仅供技术研究与学习使用。使用者应严格遵守目标网站的 Robots 协议及相关法律法规。
> 作者不对使用本工具产生的任何后果负责。
