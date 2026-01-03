# Crawler4j

Crawler4j 是一个基于 Python 的自动化监控与任务执行平台，采用**模块化任务脚本架构**，支持动态加载和执行自动化任务。

---

# 一、框架核心 (Framework Core)

## 功能描述

Crawler4j 主框架提供以下核心能力：

| 功能模块 | 说明 |
|----------|------|
| **环境管理** | 独立浏览器指纹环境，绑定账号和任务链 |
| **账号池** | 携程账号与劳保账号分离管理，支持导入/锁定/冷却 |
| **调度器** | 多环境并发执行，自动分配任务 |
| **模块加载** | 加载内置模块和用户安装的外部模块 |
| **Hooks 系统** | 在环境生命周期关键点执行自定义逻辑 |
| **GUI 界面** | 基于 PyQt6 的现代化图形界面 |

## 架构描述

### 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.12+ |
| 界面 | PyQt6 |
| 自动化 | Playwright |
| OCR | ddddocr |
| 包管理 | uv |
| 打包 | PyInstaller |

### 模块划分

```
crawler4j/
├── src/
│   ├── automation/      # 自动化核心（验证码、页面操作）
│   ├── core/            # 核心业务（账号、环境、调度）
│   ├── plugins/         # 插件系统（模块加载、脚本执行）
│   ├── ui/              # GUI 页面
│   └── main.py
├── modules/             # 内置任务模块（随应用打包）
├── crawler4j_sdk/       # SDK 开发工具包
└── pyproject.toml
```

### 模块加载机制

框架支持两类模块：

| 类型 | 位置 | 说明 |
|------|------|------|
| **内置模块** | `modules/` | 随应用打包分发 |
| **外部模块** | `~/.crawler4j/modules/` | 用户安装 |

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
uv run start
# 或
uv run python -m src.main
```

### 测试与代码检查

```bash
uv run pytest
uv run ruff check .
```

### 打包发布

```bash
# GUI 应用打包（包含内置模块）
uv run pyinstaller crawler4j.spec --clean
```

## 使用指南

### 安装

下载发布的 `Crawler4j.app` (macOS) 或 `Crawler4j.exe` (Windows)。

### 账号管理

| 账号类型 | 用途 | CSV格式 |
|----------|------|---------|
| 携程账号 | 爬虫入口身份 | `phone,password,country_code` |
| 劳保账号 | 执行具体任务 | `phone,password` |

### 操作流程

1. 导入账号（携程/劳保账号页面）
2. 配置设置（浏览器、接码平台）
3. 选择环境绑定的任务链
4. 点击"启动调度器"

---

# 二、SDK 开发工具包

## 功能描述

`crawler4j-sdk` 是面向脚本开发者的开发工具包，提供：

- **基类**：`TaskScript`（原子任务）、`TaskFlow`（复合任务链）
- **上下文**：`TaskContext`（页面、HTTP、日志、配置）
- **CLI 工具**：项目初始化、脚本创建、模块管理

## 架构描述

```
crawler4j_sdk/
├── __init__.py      # 基类导出
├── base.py          # TaskScript 定义
├── context.py       # TaskContext 定义
├── result.py        # TaskResult 定义
├── workflow.py      # TaskFlow 定义
├── db.py            # DataService 接口
└── cli/             # CLI 命令实现
```

### 核心类

| 类 | 说明 |
|-----|------|
| `TaskScript` | 原子任务基类，实现 `execute()` 方法 |
| `TaskFlow` | 复合任务链基类，实现 `run()` 方法 |
| `TaskContext` | 执行上下文，提供 `page`、`http`、`logger` 等 |
| `TaskResult` | 任务结果，包含 `success`、`tasks_completed` |

## 开发指南

### SDK 维护

```bash
cd crawler4j_sdk
uv build
uv publish
```

## 使用指南

### 1. 创建模块项目

```bash
# 全局命令（推荐）
uvx crawler4j-sdk init my_module

# 或项目内命令
uv run crawler4j module init my_module
```

### 2. 添加任务链和子任务

```bash
# 添加任务链
uv run crawler4j module add-workflow my_module main_workflow

# 添加子任务
uv run crawler4j module add-task my_module login_task
```

### 3. 脚本结构示例

**子任务（tasks/login_task.py）：**

```python
from crawler4j_sdk import TaskScript, TaskContext, TaskResult

class LoginTask(TaskScript):
    name = "login_task"
    display_name = "登录任务"
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        await ctx.page.goto("https://example.com/login")
        # ... 登录逻辑
        return TaskResult.ok(message="登录成功")
```

**任务链（workflows/main_workflow.py）：**

```python
from crawler4j_sdk import TaskFlow, TaskContext

class MainWorkflow(TaskFlow):
    name = "main_workflow"
    display_name = "主工作流"
    
    async def run(self, ctx: TaskContext) -> None:
        # 执行子任务
        await ctx.run_subtask("login_task")
        await ctx.run_subtask("search_task")
        await ctx.run_subtask("submit_task")
```

### 4. TaskContext API

| 属性/方法 | 类型 | 说明 |
|-----------|------|------|
| `page` | `Page` | Playwright Page 对象 |
| `http` | `HttpClient` | HTTP 客户端 |
| `logger` | `Logger` | 日志记录器 |
| `config` | `dict` | 任务配置 |
| `state` | `dict` | 共享状态 |
| `run_subtask(name)` | `async` | 执行子任务 |
| `should_stop()` | `bool` | 检查是否应停止 |
| `screenshot(name)` | `async` | 截图 |

### 5. 模块管理命令

| 命令 | 说明 |
|------|------|
| `module init <name>` | 创建模块骨架 |
| `module add-workflow <m> <n>` | 添加任务链 |
| `module add-task <m> <n>` | 添加子任务 |
| `module validate <name>` | 验证模块结构 |
| `module pack <name>` | 打包模块为 .zip |
| `module install <source>` | 安装外部模块 |
| `module list` | 列出已加载模块 |

### 6. 部署模块

**内置模块：** 放入 `modules/` 目录，随应用打包分发。

**外部模块：** 用户通过以下方式安装：
```bash
crawler4j module install ./my_module-1.0.0.zip
crawler4j module install https://github.com/user/my_module.git
```

---

# 三、内置任务脚本 (携程模块)

## 功能描述

携程模块 (`modules/ctrip/`) 实现完整的劳保做题自动化流程：

| 任务链 | 说明 |
|--------|------|
| **labor_workflow** | 劳保做题（完整流程） |
| **login_workflow** | 仅携程上号 |

## 架构描述

```
modules/ctrip/
├── module.yaml          # 模块配置
├── workflows/
│   └── labor_workflow.py   # 做题任务链
└── tasks/
    ├── ctrip_login_task.py   # 携程登录
    ├── labor_login_task.py   # 劳保登录
    ├── claim_task.py         # 领取任务
    ├── ctrip_search_task.py  # 携程搜索采集
    └── submit_task.py        # 提交结果
```

### 数据流

```
携程登录 → 劳保登录 → [领题 → 搜索采集 → 提交] × N
                         ↑_________循环_________↓
```

## 工作流程

### labor_workflow 完整流程

1. **携程登录** (`ctrip_login_task`)
   - 打开携程登录页
   - 输入手机号和密码
   - 处理验证码（滑块/点选）
   - 获取短信验证码（API/手动）
   - 验证登录成功

2. **劳保登录** (`labor_login_task`)
   - 跳转劳保平台
   - 输入账号密码
   - 验证登录成功

3. **任务循环**（重复 N 次）
   1. **领取任务** (`claim_task`)
      - 访问任务列表
      - 选择可用任务
      - 点击领取

   2. **携程搜索采集** (`ctrip_search_task`)
      - 解析任务要求
      - 在携程搜索酒店
      - 匹配目标信息
      - 截图保存证据

   3. **提交结果** (`submit_task`)
      - 填写表单
      - 上传截图
      - 提交审核

## 子任务说明

### ctrip_login_task

| 项目 | 说明 |
|------|------|
| **输入** | 携程账号（手机号、密码） |
| **输出** | 登录成功状态 |
| **依赖** | 验证码识别、短信接码 |

### labor_login_task

| 项目 | 说明 |
|------|------|
| **输入** | 劳保账号（手机号、密码） |
| **输出** | 登录成功状态 |

### claim_task

| 项目 | 说明 |
|------|------|
| **输入** | 已登录的劳保会话 |
| **输出** | 任务信息（酒店名、日期等） |

### ctrip_search_task

| 项目 | 说明 |
|------|------|
| **输入** | 任务信息、携程会话 |
| **输出** | 搜索结果、截图 |
| **异常** | 账号被封 → 终止流程 |

### submit_task

| 项目 | 说明 |
|------|------|
| **输入** | 搜索结果、截图 |
| **输出** | 提交成功状态 |

---

## 免责声明

> [!CAUTION]
> 本工具仅供学习和研究自动化技术使用。请遵守相关平台政策和法律法规。

- 数据存储在本地用户目录
- 尊重并遵守目标网站的 `robots.txt` 规则
