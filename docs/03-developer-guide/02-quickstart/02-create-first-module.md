# 2.2 创建第一个模块

这一节给出一条可以最快跑通的最小路径。第一次上手时，不要先追求业务完整度，先把链路跑通。

本页默认你已经完成上一页的环境准备。

本页以下示例以 `crawler4j-sdk 2.x` 为准；如果你在维护 1.x 时期的旧模块，先完成数据接口升级，再继续走新脚手架流程。

## 第 1 步：创建模块项目

```bash
uvx --from crawler4j-sdk crawler4j init-model hotel_demo
cd hotel_demo
```

如果你是第一次跑这个命令，推荐直接使用交互向导，不要急着加一堆参数。交互向导的意义不是“更高级”，而是让你先看到标准流程里会问哪些信息。

默认情况下，`init-model` 会进入交互向导，并在创建后自动：

1. 生成 `.gitignore`
2. 生成 `.python-version`
3. 执行 `git init`
4. 执行 `uv sync`

如果你是在脚本或 CI 中使用它，可以改成非交互方式：

```bash
uvx --from crawler4j-sdk crawler4j init-model hotel_demo --defaults --no-git --no-install
```

如果你是在把旧模块升到当前口径，再继续下面步骤前先确认：

1. 已删除 `DataService` 导入
2. 已把旧 `ctx.db.storage / accounts / tasks` 写法改成 `ctx.db` 最小接口
3. 已把 `module.yaml.sdk_version_range` 改到 `>=2.0.0`

### 这一步做完后你应该看到什么

至少应该看到：

- 当前目录下出现 `hotel_demo/`
- 进入目录后能看到 `module.yaml`
- 如果没有加 `--no-install`，通常还能直接使用 `uv run crawler4j ...`

如果你连 `module.yaml` 都没有看到，不要继续下一步，说明模块骨架没有正确生成。

## 第 2 步：继续补任务、工作流和 UI

```bash
uv run crawler4j new fetch_hotels
uv run crawler4j add-workflow sync_hotels
```

## 第 2.5 步：编写你的第一个业务逻辑

打开 `tasks/fetch_hotels.py`，你会看到脚手架生成的模板。将其修改为以下符合 **SDK 2.0.0** 规范的简化示例：

```python
from crawler4j_sdk import TaskScript, TaskResult

class FetchHotelsTask(TaskScript):
    """抓取酒店列表任务示例"""
    
    async def execute(self, ctx):
        ctx.logger.info("开始模拟抓取酒店数据...")
        
        # 1. 从配置获取参数 (来自 module.yaml 或 UI 输入)
        city = ctx.get_config("city", "shanghai")
        
        # 2. 模拟采集数据
        hotels = [
            {"id": "h1", "name": f"{city} 示例酒店 A", "price": 500},
            {"id": "h2", "name": f"{city} 示例酒店 B", "price": 800},
        ]
        
        # 3. 保存到模块数据集 (SDK 2.0.0 标准用法)
        # 注意：不再使用 ctx.db.storage，直接使用 ctx.db
        ctx.db.replace_records("hotels", hotels)
        
        # 4. 记录当前抓取状态（如下次翻页游标）
        ctx.db.set_state("last_sync_time", "2026-03-31")
        
        ctx.logger.info(f"成功抓取并保存 {len(hotels)} 条记录")
        return TaskResult(success=True, message=f"已同步 {city} 的酒店")
```

### 这一步的关键认知
- **导入**：只从 `crawler4j_sdk` 导入必要类，不再有 `DataService`。
- **数据操作**：直接使用 `ctx.db.replace_records` 和 `ctx.db.set_state`。
- **配置**：使用 `ctx.get_config` 安全获取外部输入。

## 第 3 步：确认模块目录结构

这时你的项目至少应长成下面这样：

```text
hotel_demo/
├── __init__.py
├── .gitignore
├── .python-version
├── pyproject.toml
├── README.md
├── module.yaml
├── config_schema.json
├── tasks/
│   ├── __init__.py
│   ├── example_task.py
│   └── fetch_hotels.py
└── workflows/
    ├── __init__.py
    ├── main_workflow.py
    └── sync_hotels.py
```

如果你现在还没有 `module.yaml`，说明你不是在标准模块项目里，后面的所有步骤都不应继续。

### 新手在这里最容易漏看的文件

第一次做模块时，最容易忽略下面三样：

1. 根 `__init__.py`
2. `module.yaml`
3. `workflows/`

但对宿主运行来说，这三样比 `README.md` 重要得多。

## 第 4 步：接进 Core 做 DevLink

在宿主应用里按下面顺序操作：

1. 打开 `crawler4j` 桌面应用
2. 进入“模块管理”
3. 点击 `🔗 添加开发模块`
4. 选择当前模块目录，也就是包含 `module.yaml` 的目录
5. 确认模块来源显示为“开发链接”

这里最关键的不是“把目录选进去”，而是“宿主已经把它当成一个 `DevLink` 模块”。

### 这一步做完后你应该确认什么

至少确认两件事：

1. 模块能在模块列表里看到
2. 来源不是“正式安装模块”，而是“开发链接”

因为后面调试能力依赖的就是这个来源类型。

## 第 5 步：把策略和作业指向你的模块

在策略中，至少要保证下面两个值正确：

- `execution.module = module.yaml.name`
- `execution.workflow = 你要运行的工作流名`

如果 `module.yaml.name` 是 `hotel_demo`，而你在策略里写了目录名、显示名或别名，调试和运行都会找不到正确目标。

### 第一次填写策略时的理解方法

可以这样理解：

- `execution.module`：告诉宿主“这次到底调用哪个模块”
- `execution.workflow`：告诉宿主“在这个模块里执行哪个工作流”

如果前者写错，宿主找不到模块；如果后者写错，宿主找不到工作流。

## 第 6 步：在 ATM 中发起调试

创建或选择一个绑定了该策略的作业后：

1. 打开 ATM
2. 找到这个作业
3. 点击 `🐞 调试`
4. 让 IDE 附加到 `debugpy`

如果 `🐞 调试` 没出现，不要先怀疑 IDE，先回去检查：

1. 模块是否真的是 `DevLink`
2. 作业是否绑定了策略
3. 策略里的 `execution.module` 是否等于 `module.yaml.name`

### 新手不要在这里先怀疑什么

第一次看不到 `🐞 调试` 时，先不要急着：

- 改 Python 代码
- 改 IDE 配置
- 重装依赖

优先检查上面 3 个条件，通常更快。

## 第 7 步：打包并做正式安装验收

在模块目录的父目录执行：

```bash
uv run python -m zipfile -c hotel_demo-1.0.0.zip hotel_demo
```

然后回到宿主应用里：

1. 打开“模块管理”
2. 点击 `📥 安装模块`
3. 选择刚刚生成的 zip
4. 确认来源切换为正式安装模块
5. 再跑一次 smoke

做到这一步，才算完成了“从创建到正式安装验收”的第一轮闭环。

## 这页做完后，你应该获得什么

如果你顺利完成了这 7 步，你已经完成了第一轮完整体验：

1. 你创建了一个标准模块项目
2. 你手动新增了任务和工作流
3. 你让宿主识别到了这个模块
4. 你在宿主里跑通了开发调试链路
5. 你又跑通了正式安装链路

这时你再去看后面的“结构”“契约”“排错”章节，会比一开始直接看更容易理解。
