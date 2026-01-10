# Crawler4j

Crawler4j 是一个基于 Python 的自动化监控与任务执行平台，采用**模块化任务脚本架构**，支持 **BitBrowser**与**VirtualBrowser** 双指纹浏览器内核，具备动态加载和并发执行自动化任务的能力。

---

# 一、框架核心 (Framework Core)

## 功能描述

Crawler4j 主框架提供以下核心能力：

| 功能模块 | 说明 |
|----------|------|
| **环境管理** | 支持 **BitBrowser** 和 **VirtualBrowser** 双内核，自动管理指纹/代理/账号绑定 |
| **账号池** | 携程账号与劳保账号分离管理，支持**接码平台自动取号建号**、导入/锁定/冷却/黑名单管理 |
| **调度器** | 基于 APScheduler 的异步调度，支持多环境并发、任务链自动分配 |
| **模块加载** | 支持加载内置模块 (`modules/`) 和用户外部模块，提供沙箱化执行环境 |
| **Hooks 系统** | 在环境生命周期(创建前/后、销毁前/后)执行自定义逻辑 |
| **GUI 界面** | 基于 PyQt6 的现代化图形界面，采用异步信号机制保证流畅度 |

## 架构描述

### 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| **语言** | Python 3.12+ | 强类型注解，异步原生 |
| **界面** | PyQt6 + qasync | 异步 UI 事件循环 |
| **自动化** | Playwright (Async) | 高性能浏览器控制 |
| **指纹浏览器** | BitBrowser / VirtualBrowser | 支持两种主流指纹浏览器 API |
| **网络** | aiohttp / httpx | 异步 HTTP 请求 |
| **OCR** | ddddocr | 本地验证码识别 |
| **包管理** | uv | 极速依赖与环境管理 |

### 模块划分

```text
crawler4j/
├── src/
│   ├── automation/      # 自动化核心（浏览器驱动、页面操作封装）
│   ├── core/            # 核心业务
│   │   ├── browser_api.py   # 双内核浏览器接口适配
│   │   ├── environment_manager.py # 环境生命周期管理
│   │   └── ...
│   ├── plugins/         # 插件系统（模块加载器、Hook机制）
│   ├── ui/              # PyQt6 图形界面
│   └── main.py          # 程序入口
├── modules/             # 内置任务模块
│   └── ctrip/           # 示例：携程/劳保业务模块
├── crawler4j_sdk/       # SDK 开发工具包（独立发版）
│   ├── cli/             # 命令行工具实现
│   └── ...
└── pyproject.toml       # 项目配置与依赖
```

### 浏览器 API 支持

框架通过 `BrowserAPI` 类统一封装了底层差异，通过 `config.browser_type` 切换：

- **BitBrowser**: 使用 `/browser/*` 接口，支持 WS 连接。
- **VirtualBrowser**: 使用 `/api/*` 接口，支持 DebuggingPort 连接。

## 开发指南

### 环境配置

```bash
git clone https://github.com/uroborus2s/crawler4j.git
cd crawler4j
uv sync --group dev
uv run playwright install chromium
```

### 运行开发环境

```bash
# 启动 GUI 主程序
uv run start
# 或直接运行模块
uv run python -m src.main
```

### 代码检查

```bash
uv run ruff check .
uv run pytest
```

---

# 二、SDK 开发工具包 (crawler4j-sdk)

## 功能描述

`crawler4j-sdk` 是面向脚本开发者的工具包，旨在降低自动化脚本的开发门槛。

- **核心基类**：`TaskScript`（原子任务）、`TaskFlow`（复合任务链）
- **执行上下文**：`TaskContext`（封装 Page、HTTP、Log、DB、配置）
- **CLI 工具**：提供 `init`, `add`, `list` 等脚手架命令

## CLI 使用指南

SDK 提供了 `crawler4j` 命令行工具（由 `pyproject.toml` 注册），用于快速生成代码。

### 1. 初始化新模块

创建一个包含标准结构的脚本项目：

```bash
# 在当前目录下创建 my_module 项目
uv run crawler4j init my_module
```

生成的结构：
```text
my_module/
├── pyproject.toml
├── README.md
├── debug_runner.py      # 调试运行器
└── tasks/
    └── example_task.py  # 示例脚本
```

### 2. 创建新脚本

在项目目录下交互式创建新任务脚本：

```bash
cd my_module
uv run crawler4j add
# 按提示输入脚本名称、显示名称等
```

或非交互式快速创建：

```bash
uv run crawler4j new login_task
```

### 3. 列出所有脚本

```bash
uv run crawler4j list
```

## 脚本开发示例

**1. 定义原子任务 (TaskScript)**

```python
from crawler4j_sdk import TaskScript, TaskContext, TaskResult

class LoginTask(TaskScript):
    name = "login_task"          # 唯一标识
    display_name = "登录任务"     # UI显示名称
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        ctx.logger.info("开始登录...")
        
        # 使用 playwright page 对象
        await ctx.page.goto("https://example.com/login")
        await ctx.page.fill("#username", ctx.config.get("username"))
        
        # 使用封装的 HTTP 客户端
        resp = await ctx.http.get("https://api.ipify.org?format=json")
        ctx.logger.info(f"当前IP: {resp.get('ip')}")
        
        return TaskResult.ok(data={"status": "logged_in"})
```

**2. 定义任务链 (TaskFlow)**

```python
from crawler4j_sdk import TaskFlow, TaskContext

class MainWorkflow(TaskFlow):
    name = "main_workflow"
    
    async def run(self, ctx: TaskContext) -> None:
        # 串行执行子任务
        await ctx.run_subtask("login_task")
        
        # 结果传递
        search_data = await ctx.run_subtask("search_task", keyword="hotel")
        
        # 循环执行
        for item in search_data:
            if ctx.should_stop(): # 响应停止信号
                break
            await ctx.run_subtask("process_item", item=item)
```

---

# 三、内置业务模块 (Ctrip Module)

## 模块介绍

位于 `modules/ctrip/`，展示了如何使用 SDK 构建复杂的业务流程。

### 核心任务链

| 任务链 | ID | 说明 |
|--------|----|------|
| **完整搬砖流程** | `labor_workflow` | 自动登录携程 -> 登录劳保 -> 领题 -> 搜题 -> 提交 -> 循环 |
| **仅携程上号** | `login_workflow` | 仅执行携程登录，用于环境预热或测试 |

### 自动化特性

- **自动接码**：集成接码平台 API，自动获取手机号和验证码注册/登录携程。
- **滑块验证**：集成 OpenCV/ddddocr 识别滑块缺口。
- **异常恢复**：遇到账号封禁自动标记并终止当前环境，调度器会自动启动新环境接力。

## 目录结构

```text
modules/ctrip/
├── module.py          # 模块入口 (定义模块元数据)
├── config.py          # Pydantic 配置模型
├── workflows/         # TaskFlow 定义 (labor_workflow.py)
└── tasks/             # TaskScript 定义 (login.py, search.py)
```

---

## 免责声明

> [!CAUTION]
> 本项目及所含工具仅供技术研究与学习使用。使用者应严格遵守目标网站的 Robots 协议及相关法律法规。
> 作者不对使用本工具产生的任何后果负责。
