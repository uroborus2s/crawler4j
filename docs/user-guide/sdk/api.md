# API 参考 (SDK Reference)

本章节列出了插件开发中常用的核心 API。

## TaskScript (任务基类)

所有原子任务必须继承此类。

```python
from crawler4j_sdk import TaskScript, TaskContext, TaskResult

class MyTask(TaskScript):
    # 必需属性
    name: str = "unique_task_name"
    
    # 执行入口
    async def execute(self, ctx: TaskContext) -> TaskResult:
        pass
        
    # 生命周期钩子 (可选)
    async def on_init(self, ctx: TaskContext): ...
    async def on_error(self, ctx: TaskContext, error: Exception): ...
    async def on_cleanup(self, ctx: TaskContext): ...
```

## TaskContext (任务上下文)

`ctx` 对象是脚本与系统交互的唯一桥梁。

### 核心属性

| 属性 | 类型 | 说明 |
| :--- | :--- | :--- |
| `ctx.page` | `playwright.async_api.Page` | 当前浏览器页面对象 (Playwright)。 |
| `ctx.logger` | `logging.Logger` | 任务专用日志记录器。 |
| `ctx.config` | `dict` | 当前任务的运行时配置。 |
| `ctx.state` | `dict` | 任务间共享的状态存储。 |

### 常用方法

#### `ctx.get_config(key, default=None)`
获取配置项。
```python
url = ctx.get_config("target_url", "https://example.com")
```

#### `ctx.screenshot(name: str) -> str`
截图并保存到系统指定的证据目录。
```python
path = await ctx.screenshot("login_success")
```

#### `ctx.wait(seconds: float)`
非阻塞等待。
```python
await ctx.wait(2.0)
```

#### `ctx.run_subtask(name: str, **kwargs)`
调用其他子任务（在工作流中使用）。
```python
# 调用名为 'login' 的任务
await ctx.run_subtask("login")
```

## TaskResult (任务结果)

用于标准化任务的返回结果。

#### `TaskResult.ok(data=None, message="")`
表示任务执行成功。
```python
return TaskResult.ok(data={"price": 100}, message="抓取成功")
```

#### `TaskResult.fail(error=None, message="")`
表示任务执行失败。
```python
return TaskResult.fail(message="页面加载超时")
```
