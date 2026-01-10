# Crawler4j SDK

任务脚本开发工具包（Software Development Kit）。

## 安装

```bash
pip install crawler4j-sdk
```

## 快速开始

```python
from crawler4j_sdk import TaskScript, TaskContext, TaskResult


class MyTask(TaskScript):
    """示例任务"""
    
    name = "my_task"
    display_name = "我的任务"
    description = "这是一个示例任务"
    default_config = {"timeout": 30}

    async def execute(self, ctx: TaskContext) -> TaskResult:
        # 使用浏览器
        await ctx.page.goto("https://example.com")
        
        # 使用配置
        timeout = ctx.get_config("timeout", 30)
        
        # 使用日志
        ctx.logger.info("任务执行中...")
        
        return TaskResult.ok(message="完成")

    async def on_error(self, ctx: TaskContext, error: Exception) -> None:
        await ctx.screenshot("error")
        ctx.logger.error(f"任务失败: {error}")
```

## 核心 API

### 稳定契约（同 MAJOR 版本内冻结）

| 类型 | 说明 |
|:---|:---|
| `TaskScript` | 原子任务基类 |
| `TaskFlow` | 工作流编排基类 |
| `TaskContext` | 任务执行上下文 |
| `TaskResult` | 任务结果模型 |
| `DataService` | 数据服务聚合 |

### TaskScript 生命周期

```
on_init(ctx) → execute(ctx) → on_cleanup(ctx)
                   ↓
              on_error(ctx, error)  [仅异常时]
```

### TaskContext 能力

| 属性/方法 | 说明 |
|:---|:---|
| `ctx.page` | Playwright Page 对象 |
| `ctx.logger` | 日志记录器 |
| `ctx.http` | HTTP 客户端 |
| `ctx.config` | 任务配置 |
| `ctx.state` | 共享状态 |
| `ctx.run_subtask()` | 调用子任务 |
| `ctx.should_stop()` | 检查停止标志 |
| `ctx.screenshot()` | 截图 |

## CLI 命令

```bash
# 初始化项目
crawler4j init my_project

# 创建脚本（交互式）
crawler4j add

# 创建脚本（快速）
crawler4j new my_task

# 列出脚本
crawler4j list
```

## 工作流示例

```python
from crawler4j_sdk import TaskFlow, TaskContext


class MyWorkflow(TaskFlow):
    name = "my_workflow"
    
    async def run(self, ctx: TaskContext) -> None:
        # 登录
        await ctx.run_subtask("login")
        
        # 循环处理
        while not ctx.should_stop():
            ctx.state["phase"] = "claim"
            task = await ctx.run_subtask("claim_task")
            if not task:
                break
            
            ctx.state["phase"] = "process"
            await ctx.run_subtask("process", task=task)
```

## 版本兼容

- Python: `>= 3.12`
- 遵循语义化版本（SemVer）
