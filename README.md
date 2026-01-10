# Crawler4j

**Crawler4j** 是一个基于 Python 的自动化监控与任务执行平台，采用**微内核 + SDK + 插件**架构，支持动态加载和并发执行自动化任务。

[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://uroborus2s.github.io/crawler4j/)
[![Python](https://img.shields.io/badge/python-3.12+-green)](https://www.python.org/)

---

## 📚 文档

完整文档请访问：**[Crawler4j Documentation](https://uroborus2s.github.io/crawler4j/)**

| 文档 | 说明 |
|------|------|
| [快速开始](https://uroborus2s.github.io/crawler4j/getting-started/) | 5 分钟上手指南 |
| [用户指南](https://uroborus2s.github.io/crawler4j/user-guide/deployment/) | 部署、配置、使用 |
| [插件开发](https://uroborus2s.github.io/crawler4j/plugin-dev/plugin-system/) | 编写自定义模块 |
| [SDK 参考](https://uroborus2s.github.io/crawler4j/sdk/core/) | API 文档 |
| [SRS 规格](https://uroborus2s.github.io/crawler4j/srs/) | 系统需求与功能规格 |

---

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                      Modules (业务插件)                       │
│   携程模块 / 劳务模块 / 自定义模块...                           │
├─────────────────────────────────────────────────────────────┤
│                         SDK 契约层                            │
│   TaskScript / TaskFlow / TaskContext / TaskResult           │
├─────────────────────────────────────────────────────────────┤
│                     Framework Core (微内核)                   │
│   MMS(模块管理) | REM(环境管理) | TSM(策略管理) | ATM(任务管理)  │
└─────────────────────────────────────────────────────────────┘
```

### 核心技术栈

| 组件 | 技术 |
|------|------|
| **语言** | Python 3.12+ |
| **界面** | PyQt6 |
| **自动化** | Playwright (Async) |
| **指纹浏览器** | BitBrowser / VirtualBrowser |
| **包管理** | uv |

---

## 🚀 快速开始

### 环境要求

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) 包管理器

### 安装

```bash
# 克隆仓库
git clone https://github.com/uroborus2s/crawler4j.git
cd crawler4j

# 安装依赖
uv sync --group dev

# 安装浏览器
uv run playwright install chromium
```

### 启动应用

```bash
uv run python -m src.ui.app
```

### 运行测试

```bash
uv run pytest
```

---

## 📁 项目结构

```
crawler4j/
├── src/
│   ├── core/                 # Framework Core (微内核)
│   │   ├── persistence/      # 数据持久化
│   │   ├── rem/              # 运行环境管理 (含 UI)
│   │   ├── tsm/              # 任务策略管理 (含 UI)
│   │   ├── mms/              # 模块管理系统 (含 UI)
│   │   ├── atm/              # 自动化任务管理 (含 UI)
│   │   └── settings/         # 系统设置 (含 UI)
│   ├── ui/                   # UI Host (容器层)
│   │   ├── shell.py          # 全局布局
│   │   ├── app.py            # 应用入口
│   │   ├── core/             # Core-UI 集成
│   │   └── components/       # 公共组件
│   └── utils/                # 工具函数
├── crawler4j_sdk/            # SDK 开发工具包
├── modules/                  # 业务模块
├── docs/                     # 文档源文件
│   ├── srs/                  # 需求规格说明书
│   ├── design/               # 技术方案设计
│   └── test/                 # 测试设计
└── tests/                    # 测试用例
```

---

## 🔧 开发

### 代码检查

```bash
uv run ruff check .
uv run ruff format .
```

### 构建文档

```bash
uv run mkdocs serve    # 本地预览
uv run mkdocs build    # 构建静态文件
```

---

## 📖 SDK 快速示例

```python
from crawler4j_sdk import TaskScript, TaskContext, TaskResult

class LoginTask(TaskScript):
    name = "login_task"
    display_name = "登录任务"
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        await ctx.page.goto("https://example.com/login")
        await ctx.page.fill("#username", ctx.config.get("username"))
        return TaskResult.ok(data={"status": "logged_in"})
```

详细 SDK 文档请参阅 [SDK 参考](https://uroborus2s.github.io/crawler4j/sdk/core/)。

---

## ⚠️ 免责声明

> [!CAUTION]
> 本项目及所含工具仅供技术研究与学习使用。使用者应严格遵守目标网站的 Robots 协议及相关法律法规。
> 作者不对使用本工具产生的任何后果负责。
