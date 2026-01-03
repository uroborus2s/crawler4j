# Crawler4j SDK

用于开发任务脚本的开发工具包。

## 安装

```bash
uv add crawler4j-sdk
# 或
pip install crawler4j-sdk
```

## 使用

```python
from crawler4j_sdk import TaskScript, TaskContext, TaskResult

class MyTask(TaskScript):
    name = "my_task"
    display_name = "我的任务"
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        await ctx.page.goto("https://example.com")
        return TaskResult.ok(tasks_completed=1)
```

## API

### TaskScript

任务脚本基类，必须继承并实现`execute`方法。

### TaskContext

执行上下文，提供：
- `page` - Playwright Page对象
- `http` - HTTP客户端
- `logger` - 日志记录器
- `config` - 任务配置

### TaskResult

执行结果，包含`success`、`tasks_completed`、`message`等字段。
