# 编写你的第一个爬虫 (Tutorial)

本教程将手把手教你开发一个完整的 Crawler4j 插件。

## 1. 初始化项目

首先，使用 CLI 工具创建一个新的插件项目。

```bash
# 1. 创建项目
uv run crawler4j init my_first_plugin

# 2. 进入目录
cd my_first_plugin

# 3. 检查结构
ls -R
```

生成的目录结构如下：
```text
my_first_plugin/
├── pyproject.toml      # 项目依赖配置
├── README.md
├── debug_runner.py     # 本地调试运行器
└── tasks/              # 任务脚本存放目录
    └── example_task.py # 示例代码
```

## 2. 编写任务逻辑

我们只需编辑 `tasks/` 目录下的 Python 文件。假设我们要编写一个 "访问百度并截图" 的爬虫。

运行添加命令：
```bash
uv run crawler4j add baidu_search
```

这将生成 `tasks/baidu_search.py`。打开它并修改 `execute` 方法：

```python
from crawler4j_sdk import TaskScript, TaskContext, TaskResult

class BaiduSearchTask(TaskScript):
    name = "baidu_search"
    display_name = "百度搜索示例"
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        # 1. 访问页面
        ctx.logger.info("正在打开百度...")
        await ctx.page.goto("https://www.baidu.com")
        
        # 2. 输入搜索词
        keyword = ctx.get_config("keyword", "Crawler4j")
        await ctx.page.fill("#kw", keyword)
        await ctx.page.click("#su")
        
        # 3. 等待结果
        await ctx.page.wait_for_selector("#content_left")
        
        # 4. 截图保存
        path = await ctx.screenshot("search_result")
        
        return TaskResult.ok(message=f"搜索 '{keyword}' static, 截图已保存至 {path}")
```

## 3. 本地调试

无需打包，直接使用 `debug_runner.py` 在本地运行调试。

```bash
python debug_runner.py
```

> [!TIP]
> `debug_runner.py` 会模拟一个真实的 `TaskContext`，并启动一个带界面的浏览器窗口，方便你观察脚本执行效果。

## 4. 打包发布

开发完成后，构建为 Python 包供 Crawler4j 平台加载。

```bash
uv build
```

生成的 `.whl` 文件即可在 Crawler4j 的"模块管理"界面中进行安装。
