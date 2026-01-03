# Crawler4j

Crawler4j 是一个基于 Python 的自动化监控与任务执行平台，支持**可扩展的任务脚本系统**。它集成了网页自动化控制、验证码识别及流程管理功能。

## 核心功能

- **任务脚本系统**：支持动态加载 Python 脚本，无需修改框架代码即可扩展新任务
- **多平台自动化**：支持携程（Ctrip）和劳务平台的自动登录、任务搜索、领取及提交
- **验证码识别**：内置 ddddocr 支持，自动处理图形验证码
- **环境管理**：独立的浏览器指纹环境，支持代理IP
- **Hooks 系统**：在环境生命周期关键点执行自定义逻辑
- **现代化 UI**：基于 PyQt6 的图形界面

## 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.12+ |
| 界面 | PyQt6 |
| 自动化 | Playwright |
| OCR | ddddocr |
| 包管理 | uv |

---

## 快速开始

### 安装

```bash
git clone https://github.com/uroborus2s/crawler4j.git
cd crawler4j
uv sync
uv run playwright install chromium
```

### 启动

```bash
uv run start
# 或
uv run python -m src.main
```

---

## 用户指南

### 账号管理

系统采用**携程账号**与**劳保账号**分离的双账号池设计：

| 账号类型 | 用途 |
|----------|------|
| 携程账号 | 登录携程旅行网，作为爬虫入口身份 |
| 劳保账号 | 登录劳保平台，执行具体任务 |

**CSV导入格式：**
- 携程账号：`phone`, `password`, `country_code`(可选)
- 劳保账号：`phone`, `password`

### 防封号策略

- **指纹浏览器**：每个环境独立设备指纹
- **并发控制**：默认最大10并发
- **任务间隔**：默认5秒间隔
- **API账号冷却**：首次登录后2天冷却期

### 操作流程

1. 导入账号（携程/劳保账号页面）
2. 配置设置（浏览器、接码平台）
3. 点击"启动调度器"

---

## 任务脚本开发指南

### 1. 创建脚本

```bash
# 一键创建脚本
uv run crawler4j new-script my_task

# 初始化独立项目（团队协作）
uv run crawler4j init-project my_scripts
```

### 2. 脚本结构

```python
from crawler4j_sdk import TaskScript, TaskContext, TaskResult

class MyTask(TaskScript):
    name = "my_task"
    display_name = "我的任务"
    description = "任务描述"
    
    default_config = {
        "max_items": 10,
    }
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        # 访问页面
        await ctx.page.goto("https://example.com")
        
        # 发送HTTP请求
        data = await ctx.http.get("https://api.example.com")
        
        # 截图
        await ctx.screenshot("result")
        
        # 日志
        ctx.logger.info("任务完成")
        
        return TaskResult.ok(tasks_completed=1)
    
    async def on_error(self, ctx: TaskContext, error: Exception):
        ctx.logger.error(f"出错: {error}")
        await ctx.screenshot("error")
```

### 3. SDK API

#### TaskContext 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `page` | `Page` | Playwright Page |
| `http` | `HttpClient` | HTTP客户端 |
| `logger` | `Logger` | 日志记录器 |
| `config` | `dict` | 任务配置 |
| `env_id` | `int` | 环境ID |
| `ctrip_account` | `CtripAccountInfo` | 携程账号 |
| `labor_account` | `LaborAccountInfo` | 劳保账号 |

#### TaskContext 方法

```python
await ctx.wait(seconds)           # 等待
await ctx.screenshot(name)        # 截图
ctx.get_config(key, default)      # 获取配置
```

#### TaskResult

```python
TaskResult.ok(tasks_completed=1, message="成功")
TaskResult.fail(message="失败", error="详情")
```

### 4. 调试脚本

1. 修改 `scripts/debug_runner.py` 中的 `SCRIPT_NAME`
2. VSCode 按 F5 启动调试
3. 可设置断点、单步执行

### 5. 部署脚本

1. 运行应用
2. 「任务配置」→「📁 添加脚本目录」
3. 选择脚本目录
4. 点击「🔄 重载脚本」

---

## CLI 命令

```bash
# 创建新脚本
uv run crawler4j new-script <name> [-o 输出目录]

# 初始化独立项目
uv run crawler4j init-project <name>

# 重载脚本
uv run crawler4j reload-scripts

# 列出已加载脚本
uv run crawler4j list-scripts
```

---

## 开发者指南

### 项目结构

```
crawler4j/
├── src/
│   ├── automation/workflows/   # 平台工作流
│   ├── core/                   # 核心业务
│   ├── plugins/                # 插件系统
│   ├── ui/                     # GUI组件
│   ├── cli/                    # CLI工具
│   └── main.py
├── crawler4j_sdk/              # SDK包
├── scripts/tasks/              # 任务脚本
└── pyproject.toml
```

### 开发环境

```bash
# 安装开发依赖
uv sync --group dev

# 运行测试
uv run pytest

# 代码检查
uv run ruff check src/
```

### 打包发布

#### 打包应用

```bash
uv run pyinstaller crawler4j.spec --clean
```

- macOS: `dist/Crawler4j.app`
- Windows: `dist/Crawler4j/Crawler4j.exe`

#### 发布SDK到PyPI

```bash
cd crawler4j_sdk
uv build
uv publish
```

### 提交代码

```bash
git add -A
git commit -m "feat: 功能描述"
git push origin feature/xxx
```

---

## 免责声明

> [!CAUTION]
> 本工具仅供学习和研究自动化技术使用。请遵守相关平台政策和法律法规。

- 数据存储在本地SQLite数据库 `crawler.db`
- 定期清理日志和浏览器配置
- 遵守目标网站 `robots.txt` 规则
