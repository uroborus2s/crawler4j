# 模块开发指南

**项目名称：** crawler4j  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 外部模块开发者 | Core 维护者 | QA  
**上游输入：** `crawler4j_sdk/cli/commands.py` | `src/core/mms/registry.py` | `src/core/debug/service.py` | 当前验证结果  
**下游输出：** 外部模块项目 | `docs/08-handover/user-guide.md` | `.factory/workitems/implementation/TASK-010-optimize-module-developer-guide-for-external-authors.md`  
**关联 ID：** `TASK-010`, `REQ-003`, `REQ-005`, `DOC-002`  
**最后更新：** 2026-03-26  

## 1. 先记住这 8 个真实事实

1. CLI 命令名仍然叫 `init-model`，但它生成的是当前正式支持的“模块项目”。
2. 当前已发布 SDK 版本是 `1.0.3`，Contracts 版本是 `1.0.1`。
3. Core 运行模块时看的是 `module.yaml` 和模块根 `__init__.py`，不是 wheel 元数据。
4. 当前应用内正式安装只支持 `zip` 包，不支持把 `.whl` 直接装进模块管理。
5. 不管是 `DevLink` 调试还是安装后的正式运行，模块代码最终都运行在 `crawler4j` 自己的 Python 环境里。
6. 这意味着模块项目 `pyproject.toml` 里的第三方依赖不会被应用自动安装；新增运行时依赖必须进入宿主应用，或者作为模块源码的一部分随包交付。
7. 只有解析到 `DevLink` 模块的作业，ATM 里才会显示 `🐞 调试`。
8. 当前真正可靠的 UI 扩展只有 `config_schema.json` 声明式配置和 `core:data_table:<view_id>` 通用数据表。

如果你只想最快跑通一条链路，请直接看第 2 节。

## 2. 15 分钟上手路径

### 2.1 准备 CLI

长期使用：

```bash
uv tool install crawler4j-sdk==1.0.3
crawler4j --help
```

一次性使用：

```bash
uvx --from crawler4j-sdk==1.0.3 crawler4j --help
```

### 2.2 创建模块项目

```bash
uvx --from crawler4j-sdk==1.0.3 crawler4j init-model hotel_demo
cd hotel_demo
uv run crawler4j list
```

当前 `init-model` 默认会：

1. 进入一轮初始化向导
2. 生成 `.gitignore` 与 `.python-version`
3. 自动执行 `git init`
4. 自动执行 `uv sync`

如果你在脚本或 CI 中使用它，可以改成：

```bash
uvx --from crawler4j-sdk==1.0.3 crawler4j init-model hotel_demo --defaults --no-git --no-install
```

### 2.3 继续补任务、工作流、配置 UI

```bash
uv run crawler4j new fetch_hotels
uv run crawler4j add-workflow sync_hotels
uv run crawler4j add-ui
uv run crawler4j list
```

### 2.4 接进 Core 调试

1. 打开 `crawler4j` 桌面应用
2. 进入“模块管理”
3. 点击 `🔗 添加开发模块`
4. 选择当前模块目录，也就是包含 `module.yaml` 的目录
5. 在策略里把 `execution.module` 设为 `module.yaml.name`
6. 把 `execution.workflow` 设为 `module.yaml.workflows[*].name`
7. 创建或选择一个绑定该策略的作业
8. 在 ATM 里点击 `🐞 调试`
9. 让 IDE 附加到 `debugpy`

### 2.5 打包并做正式安装验收

在模块目录的父目录执行：

```bash
uv run python -m zipfile -c hotel_demo-1.0.0.zip hotel_demo
```

然后在应用里：

1. 回到“模块管理”
2. 点击 `📥 安装模块`
3. 选择刚刚生成的 zip
4. 确认来源变成正式安装模块
5. 再跑一次作业 smoke

## 3. 当前推荐工作流

当前最稳的开发姿势只有一条主线：

```text
init-model
-> 在模块项目里写 tasks / workflows / module.yaml / config_schema.json
-> 用 DevLink 接进 Core
-> 在 ATM 中按真实 Job + Strategy 调试
-> 用 zip 做正式安装验收
```

不要再按旧习惯走下面这些路径：

- `crawler4j init`
- 轻量脚本项目
- CLI 生成 `debug_runner.py`
- 用 `.whl` 直接作为应用内模块安装包

## 4. 创建模块项目

### 4.1 `init-model` 会生成什么

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
│   └── example_task.py
└── workflows/
    ├── __init__.py
    └── main_workflow.py
```

各文件职责如下：

- `module.yaml`
  模块清单。模块名、版本、工作流声明、UI 扩展都从这里读取。
- `__init__.py`
  模块真正入口。Core 最终导入这个文件，并调用导出的 `run(context)` 和可选 hooks。
- `tasks/`
  原子任务脚本。
- `workflows/`
  任务编排。
- `config_schema.json`
  声明式配置 UI。
- `pyproject.toml`
  只负责模块项目自己的开发环境，不负责应用内安装。
- `.gitignore`
  Python / uv 项目的默认忽略规则，初始化时自动生成。
- `.python-version`
  当前模块项目默认使用的 Python 版本，初始化时自动生成。

### 4.2 命名建议

- `module.yaml.name` 是运行时模块 ID，也是策略里 `execution.module` 应该填写的值。
- 模块目录名理论上可以和 `module.yaml.name` 不同，但不建议这么做。
- 最稳的做法是目录名、Python 包名、`module.yaml.name` 全部保持一致。

例如：

```yaml
name: hotel_demo
version: 1.0.0
sdk_version_range: ">=1.0.3"
```

## 5. 你真正要实现的契约

### 5.1 必需入口

模块根 `__init__.py` 必须能让 Core 调用到：

- `run(context)`

这是唯一硬性必需入口。

### 5.2 可选 hooks

如果实现了这些函数，执行器会按真实运行链调用它们：

- `prepare_env(context)`
- `init_env(context)`
- `before_run(context)`
- `on_success(context, result)`
- `on_failure(context, error)`
- `on_timeout(context)`
- `on_cleanup(context)`

### 5.3 工作流和任务的关系

CLI 模板已经帮你生成了两个注册表：

- `TASK_SCRIPTS`
- `WORKFLOWS`

当前默认行为是：

1. `workflow` 命中 `WORKFLOWS` 时，走 `TaskFlow`
2. `workflow` 命中 `TASK_SCRIPTS` 时，直接执行单个 `TaskScript`
3. 否则回退到默认工作流

### 5.4 `TaskContext.run_subtask()` 的返回值要记住

这是当前很容易踩坑的一点：

- 子任务返回 `TaskResult.ok(data=...)` 时，`await ctx.run_subtask(...)` 会直接拿到 `data`
- 子任务返回成功但没有 `data` 时，`await ctx.run_subtask(...)` 会拿到 `True`
- 子任务失败时会拿到 `False`

所以你在工作流里写：

```python
task = await ctx.run_subtask("claim_task")
if not task:
    return
```

是当前被验证过、可以正常工作的写法。

## 6. 先写最小可运行任务

```python
from crawler4j_sdk import TaskContext, TaskResult, TaskScript


class FetchHotelsTask(TaskScript):
    name = "fetch_hotels"
    display_name = "抓取酒店"
    description = "打开页面并采集标题"

    default_config = {
        "start_url": "https://example.com",
    }

    async def execute(self, ctx: TaskContext) -> TaskResult:
        if not ctx.page:
            return TaskResult.fail(message="当前运行环境没有可用的浏览器 Page")

        start_url = ctx.get_config("start_url", "https://example.com")
        await ctx.page.goto(start_url, wait_until="domcontentloaded")
        title = await ctx.page.title()

        return TaskResult.ok(
            message="采集完成",
            data={"url": ctx.page.url, "title": title},
        )
```

当前最常用的上下文能力：

- `ctx.page`
- `ctx.logger`
- `ctx.config` / `ctx.get_config()`
- `ctx.state`
- `ctx.run_subtask()`
- `ctx.screenshot()`
- `ctx.should_stop()`

## 7. 再写最小工作流

```python
from crawler4j_sdk import TaskContext, TaskFlow


class SyncHotelsWorkflow(TaskFlow):
    name = "sync_hotels"
    display_name = "同步酒店"
    description = "按顺序执行抓取任务"

    async def run(self, ctx: TaskContext) -> None:
        ctx.state["phase"] = "sync"
        result = await ctx.run_subtask("fetch_hotels")
        if not result:
            raise RuntimeError("fetch_hotels 执行失败")
```

补齐文件后，别忘了把工作流写进 `module.yaml`：

```yaml
workflows:
  - name: sync_hotels
    display_name: 同步酒店
    description: 酒店同步主工作流
```

## 8. CLI 命令怎么用

下面这些命令都要求当前目录处于模块项目里，也就是当前目录或父目录能找到 `module.yaml`。

```bash
uv run crawler4j add
uv run crawler4j new fetch_hotels
uv run crawler4j list
uv run crawler4j add-workflow sync_hotels
uv run crawler4j add-ui
```

各命令真实作用：

- `new <task_name>`
  新建一个任务脚本。
- `add`
  交互式创建任务脚本。
- `add-workflow <workflow_name>`
  新建工作流文件，并同步更新 `module.yaml.workflows`。
- `add-ui`
  生成或补齐 `config_schema.json`，并把 `module.yaml.ui_extension` 指向它。
- `list`
  列出当前模块中的任务脚本。

如果命令提示“当前目录不在 model 项目中，找不到 module.yaml”，先确认你已经 `cd` 到模块目录。

## 9. `module.yaml` 怎么写才稳

### 9.1 推荐最小写法

```yaml
name: hotel_demo
version: 1.0.0
display_name: Hotel Demo
description: 示例模块
author: crawler4j
sdk_version_range: ">=1.0.3"

ui_extension:
  type: declarative
  entry: config_schema.json
  nav_item:
    icon: "🧩"
    label: "Hotel Demo 配置"

workflows:
  - name: main_workflow
    display_name: 主工作流
    description: 默认工作流
```

### 9.2 当前实现里的校验点

- `name` 必填
- 模块名建议小写字母、数字、下划线
- 工作流名不能重复
- `sdk_version_range` 当前最稳妥写法是 `>=x.y.z`

注意：

- 扫描器当前的兼容性判断实现是简化版，主要可靠支持 `>=1.0.3` 这类格式
- 复杂表达式即使能写，也不建议作为当前交付口径

## 10. 配置 UI 现在支持到什么程度

### 10.1 当前正式支持

```yaml
ui_extension:
  type: declarative
  entry: config_schema.json
  nav_item:
    icon: "🧩"
    label: "模块配置"
  detail_menu:
    - id: accounts
      icon: "👤"
      label: "账号管理"
      entry: "core:data_table:accounts"
```

当前支持情况：

- `type: declarative`
  已实现。Core 会把 `config_schema.json` 渲染成配置表单。
- `detail_menu.entry: core:data_table:<view_id>`
  已实现。Core 会创建通用数据表页面。
- `detail_menu.entry: ui:SomePage`
  已实现，但必须同时满足：
  1. `ui_extension.type: micro_app`
  2. 模块来源是 `DevLink` / 内置来源，或模块名命中系统 allowlist `mms.ui.allowlist`
  3. 模块内存在 `ui.py`，且导出了对应的 `QWidget` 类

### 10.2 当前不要作为交付主路径

- 未通过 trust gate 的外部 `micro_app`
  现在会被明确拒绝并降级为说明页，不会被宿主直接执行。
- 复杂页面框架或任意前端应用嵌入
  当前仍没有浏览器容器级 micro-frontend 运行时，适合当前交付的是 `ui.py` 中的受控 `QWidget` 页面。

## 11. 开发调试的真实链路

### 11.1 什么时候用 DevLink

DevLink 是本地源码目录到模块名的持久化映射：

```text
module_name -> /abs/path/to/your/module
```

它的用途非常明确：

- 开发时不打包，直接让 Core 指向你的本地源码目录
- 允许 ATM 给对应作业显示 `🐞 调试`
- 重启应用后仍然保留

### 11.2 怎么把模块注册成 DevLink

推荐在桌面应用里操作：

1. 打开“模块管理”
2. 点击 `🔗 添加开发模块`
3. 选择包含 `module.yaml` 的目录
4. 确认列表里该模块来源显示为“开发链接”

如果你在调试 Core 本身，也可以直接调用后端：

```python
from src.core.mms import get_module_registry

get_module_registry().register_dev_link("/abs/path/to/hotel_demo")
```

### 11.3 为什么我看不到 `🐞 调试`

只有同时满足下面两条时，ATM 才会显示调试入口：

1. 作业已经绑定策略
2. 该策略解析出来的 `execution.module` 指向的是 `DevLink` 模块

最常见原因有 4 个：

- 策略没绑到作业
- `execution.module` 不是 `module.yaml.name`
- 模块已经切回正式安装版
- 你只是 `uv sync` 了模块项目，但没有把它注册到应用里

### 11.4 当前调试会话到底在调什么

当前链路已经不是离线模拟器，而是真实执行链：

```text
ATM 作业 / 策略
-> DebugService
-> DebugWorker
-> debugpy
-> ExecutionRunner
-> 模块 run / hooks / TaskFlow / TaskScript
```

这意味着：

- 断点打在 `tasks/*.py`、`workflows/*.py`、模块 hooks 里都有效
- 调试时拿到的是接近正式运行的 `TaskContext`
- 浏览器、资源获取、环境生命周期都按真实执行链推进

## 12. 正式交付为什么必须做 zip 安装验收

### 12.1 当前正式安装只认 zip

模块管理里的正式安装按钮当前走的是：

- 选择 zip
- 校验 zip 结构
- 解压到应用受控目录
- 重新加载模块注册表

所以当前正式交付物不是 wheel，而是 zip。

### 12.2 zip 的结构要求

最稳的结构是：

```text
hotel_demo-1.0.0.zip
└── hotel_demo/
    ├── __init__.py
    ├── module.yaml
    ├── config_schema.json
    ├── tasks/
    └── workflows/
```

要求只有两条：

1. zip 里只能有一个根目录
2. 根目录里必须能找到 `module.yaml`

### 12.3 打包命令

在模块目录的父目录执行：

```bash
uv run python -m zipfile -c hotel_demo-1.0.0.zip hotel_demo
```

### 12.4 安装时会发生什么

如果应用里已经存在同名 `DevLink`，安装正式 zip 时会自动移除那条开发链接，避免运行时仍然优先回落到源码目录。

所以你看到的现象会是：

1. 安装成功
2. 模块来源从开发链接切到正式安装模块
3. 同名作业的 `🐞 调试` 入口消失

这不是 bug，而是当前设计。

## 13. 模块作者的最小验收清单

在你把模块交给别人之前，至少完成下面 8 项：

1. `uvx --from crawler4j-sdk==1.0.3 crawler4j init-model ...` 能重新回放
2. 模块目录里有 `module.yaml`、`__init__.py`、`tasks/`、`workflows/`
3. `uv run crawler4j list` 能列出任务
4. 模块能被应用注册成 `DevLink`
5. 绑定到策略和作业后，ATM 能显示 `🐞 调试`
6. IDE 能成功附加并命中断点
7. zip 安装能通过
8. 安装后模块能从应用受控目录被加载并完成一次 smoke

## 14. 最常见的 7 个坑

### 14.1 `uv run crawler4j ...` 找不到命令

原因通常是你在模块目录里还没执行：

```bash
uv sync
```

### 14.2 CLI 提示不在 model 项目里

说明当前目录或父目录没有 `module.yaml`。

### 14.3 模块能在自己项目里 import，但放进应用就报依赖缺失

这是当前真实限制：应用不会自动安装模块项目自己的第三方依赖。

### 14.4 调试按钮不显示

先查 3 个点：

1. 模块是不是 `DevLink`
2. 策略的 `execution.module` 是不是 `module.yaml.name`
3. 作业是不是绑定了这个策略

### 14.5 zip 安装失败

通常是这两类问题：

- zip 里有多个根目录
- 根目录缺少 `module.yaml`

### 14.6 我已经安装了 zip，为什么还是在跑本地源码

当前同名正式安装会自动清掉 `DevLink`。如果你还看到源码行为，先刷新模块列表并确认来源是否仍为“开发链接”。

### 14.7 我写了自定义 Python UI 页面，但应用里只看到占位

因为当前真正可交付的 UI 扩展仍以声明式配置和通用数据表为主，自定义 Widget 动态加载还没有闭环。

## 15. 相关文档怎么搭配看

- 想看 Core 当前运行与发布方式：
  [部署与运行说明](../07-operations/deployment-guide.md)
- 想看当前方案边界和 API 摘要：
  [接口与契约设计](../03-solution/api-design.md)
- 想看当前文档总入口：
  [文档索引](../traceability/document-index.md)

## 16. 一句话总结

当前版本最正确、最省坑的模块开发路径是：

```text
init-model
-> 写任务 / 工作流 / module.yaml / config_schema.json
-> 注册 DevLink
-> 用 Job + Strategy 在 ATM 调试
-> 打 zip
-> 在模块管理里安装 zip 做正式验收
```
