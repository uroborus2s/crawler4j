# Crawler4j

Crawler4j 是一个基于 Python 的自动化监控与任务执行平台，支持**可扩展的任务脚本系统**。它集成了网页自动化控制、验证码识别及流程管理功能，主要用于携程（Ctrip）和劳务平台的自动化作业。

## 🚀 核心功能

- **任务脚本系统**：支持动态加载 Python 脚本，无需修改框架代码即可扩展新任务
- **多平台自动化**：支持携程（Ctrip）和劳务平台的自动登录、任务搜索、领取及提交
- **验证码识别**：内置 ddddocr 支持，能够自动处理复杂的图形验证码
- **环境管理**：灵活管理不同的执行环境（如浏览器配置、代理等）
- **Hooks 系统**：在环境生命周期关键点执行自定义逻辑
- **现代化 UI**：基于 PyQt6 开发的图形界面，提供直观的可视化操作

## 📖 文档

- [用户使用手册](MANUAL.md) - 操作指南、账号导入格式及防封号策略
- [SDK API 参考](#sdk-api-参考) - 任务脚本开发接口文档

## 🛠️ 技术栈

- **语言**: Python 3.12+
- **界面库**: [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- **自动化驱动**: [Playwright](https://playwright.dev/python/)
- **OCR 识别**: [ddddocr](https://github.com/sml2h3/ddddocr)
- **包管理**: [uv](https://github.com/astral-sh/uv)

## 📂 项目结构

```text
crawler4j/
├── src/
│   ├── automation/      # 自动化核心逻辑
│   │   └── workflows/   # 平台特定工作流（Ctrip, Labor）
│   ├── core/            # 核心业务逻辑与模型
│   ├── plugins/         # 插件系统（脚本执行、Hooks）
│   ├── ui/              # PyQt6 界面组件
│   ├── cli/             # 命令行工具
│   └── main.py          # 程序入口
├── crawler4j_sdk/       # 任务脚本SDK
├── scripts/tasks/       # 任务脚本目录
└── pyproject.toml
```

---

## ⚙️ 安装与运行

```bash
# 克隆项目
git clone https://github.com/your-repo/crawler4j.git
cd crawler4j

# 安装依赖
uv sync

# 安装 Playwright 浏览器
uv run playwright install chromium

# 启动应用
uv run start
```

---

## 🔌 任务脚本开发

### 快速开始

```bash
# 创建新脚本
uv run crawler4j new-script my_task

# 初始化独立脚本项目（用于团队协作）
uv run crawler4j init-project my_scripts
```

### 脚本示例

```python
from crawler4j_sdk import TaskScript, TaskContext, TaskResult

class MyTask(TaskScript):
    name = "my_task"
    display_name = "我的任务"
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        # 访问页面
        await ctx.page.goto("https://example.com")
        
        # 发送HTTP请求
        data = await ctx.http.get("https://api.example.com/data")
        
        # 截图
        await ctx.screenshot("result")
        
        return TaskResult.ok(tasks_completed=1, message="完成")
```

### 调试脚本

使用 VSCode 调试：

1. 修改 `scripts/debug_runner.py` 中的 `SCRIPT_NAME`
2. 按 F5 启动调试
3. 可设置断点、单步执行

### 部署脚本

1. 运行应用
2. 「任务配置」页面 → 「📁 添加脚本目录」
3. 选择脚本目录路径
4. 点击「🔄 重载脚本」

---

## SDK API 参考

### TaskScript

任务脚本基类，必须继承并实现 `execute` 方法。

```python
class TaskScript(ABC):
    name: str           # 唯一标识符
    display_name: str   # 显示名称
    description: str    # 描述
    default_config: dict  # 默认配置
    
    async def execute(self, ctx: TaskContext) -> TaskResult: ...
    async def on_error(self, ctx: TaskContext, error: Exception): ...
    async def on_init(self, ctx: TaskContext): ...
    async def on_cleanup(self, ctx: TaskContext): ...
```

### TaskContext

执行上下文，提供脚本可访问的所有能力。

| 属性 | 类型 | 说明 |
|------|------|------|
| `page` | `Page` | Playwright Page 对象 |
| `context` | `BrowserContext` | Playwright 浏览器上下文 |
| `http` | `HttpClient` | HTTP 客户端 |
| `logger` | `Logger` | 日志记录器 |
| `config` | `dict` | 任务配置 |
| `env_id` | `int` | 环境 ID |
| `ctrip_account` | `CtripAccountInfo` | 携程账号信息 |
| `labor_account` | `LaborAccountInfo` | 劳保账号信息 |

**方法：**
- `await ctx.wait(seconds)` - 等待
- `await ctx.screenshot(name)` - 截图
- `ctx.get_config(key, default)` - 获取配置项

### TaskResult

执行结果。

```python
# 成功
return TaskResult.ok(tasks_completed=1, message="完成")

# 失败
return TaskResult.fail(message="出错了", error="详细信息")
```

---

## 🖥️ CLI 命令

```bash
# 创建新脚本
uv run crawler4j new-script <name> [-o 输出目录]

# 初始化独立项目
uv run crawler4j init-project <name> [-o 输出目录]

# 重载脚本
uv run crawler4j reload-scripts

# 列出已加载脚本
uv run crawler4j list-scripts
```

---

## 📦 项目打包

```bash
uv add --dev pyinstaller
uv run pyinstaller crawler4j.spec --clean
```

---

## ⚖️ 免责声明

本工具仅供学习和研究自动化技术使用。请在使用过程中严格遵守相关平台的政策、法律法规。开发者不对任何因不当使用该工具而导致的违规或损失负责。
