# SDK 与 CLI 参考

这一页只写当前命令树。默认使用最新 `crawler4j-sdk`，不要在命令里固定版本号。

## CLI 命令总表

当前 `crawler4j --help` 暴露的命令如下。下面每一行都按“可直接复制的完整命令”来写，只保留占位参数。

| 命令 | 建议执行位置 | 会改哪些文件 | 用途 |
|---|---|---|---|
| `uvx --from crawler4j-sdk crawler4j module init <name> --repo owner/repo` | 目标模块的父目录 | 新建整个模块目录树 | 初始化标准模块项目 |
| `uv run crawler4j module show` | 模块根目录 | 无 | 查看版本、仓库、默认工作流和 UI 入口 |
| `uv run crawler4j task create <name>` | 模块根目录 | `tasks/<name>.py` | 新建 task |
| `uv run crawler4j workflow create <name>` | 模块根目录 | `workflows/<name>.py`、`module.yaml` | 新建 workflow 并注册到清单 |
| `uv run crawler4j page create <name>` | 模块根目录 | `ui/<name>.py`、`ui/__init__.py`、`module.yaml` | 新建代码型页面并注册 `ui_extension.entry` |
| `uv run crawler4j data-table create <name>` | 模块根目录 | `module.yaml`、`module_runtime.py` | 注册 `core:data_table:<view_id>` 入口并补 `declare_ui` 骨架 |
| `uv run crawler4j env-selector create <name>` | 模块根目录 | `module_runtime.py` | 新建环境选择策略函数 |
| `uv run crawler4j config show` | 模块根目录 | 无 | 查看当前 `config_defaults` |
| `uv run crawler4j config set module --file <yaml>` | 模块根目录 | `module.yaml` | 写入模块级默认配置 |
| `uv run crawler4j config set workflow <workflow> --file <yaml>` | 模块根目录 | `module.yaml` | 写入 workflow 级默认配置 |
| `uv run crawler4j package build` | 模块根目录 | `dist/*.zip` | 构建正式安装包 |
| `uv run crawler4j package verify <archive>` | 模块根目录 | 无 | 校验现有 ZIP 结构 |
| `uv run crawler4j release status` | 模块根目录 | 无 | 查看本地发布就绪度 |
| `uv run crawler4j release check-remote` | 模块根目录 | 无 | 对比远端 GitHub Release 版本 |
| `uv run crawler4j release publish` | 模块根目录 | 可能新建或复用 `dist/*.zip` | 发布 GitHub Release 资产 |
| `uv run crawler4j host devlink add <module_root>` | 宿主环境或模块根目录 | 宿主 DevLink 状态 | 注册宿主开发链接 |
| `uv run crawler4j host devlink remove <module_name>` | 宿主环境或模块根目录 | 宿主 DevLink 状态 | 移除宿主开发链接 |
| `uv run crawler4j host devlink list` | 宿主环境或模块根目录 | 无 | 查看宿主 DevLink 列表 |
| `uv run crawler4j host install preview <source>` | 宿主环境或模块根目录 | 无 | 预检 ZIP / GitHub 源安装 |
| `uv run crawler4j host install apply <source>` | 宿主环境或模块根目录 | 宿主安装状态 | 真正安装 ZIP / GitHub 源 |
| `uv run crawler4j host upgrade check <module>` | 宿主环境 | 无 | 查看是否有新版本 |
| `uv run crawler4j host upgrade preview <module>` | 宿主环境 | 无 | 预览升级包 |
| `uv run crawler4j host upgrade apply <module>` | 宿主环境 | 宿主安装状态 | 真正安装升级包 |
| `uv run crawler4j host debug config` | 模块根目录 | `.vscode/launch.json` | 生成 VS Code attach 配置 |
| `uv run crawler4j check structure` | 模块根目录 | 无 | 做骨架级校验 |
| `uv run crawler4j check release` | 模块根目录 | 无 | 做发布前提校验 |
| `uv run crawler4j check full` | 模块根目录 | 无 | 做完整导入校验 |

## 第一次交付时的最小安全顺序

如果你只是想按最稳妥顺序走，不要乱点命令菜单，直接按这个顺序:

1. `uv run crawler4j check release`
2. `uv run crawler4j package build`
3. `uv run crawler4j package verify dist/<module>-<version>.zip`
4. 二选一:
   - 本地宿主桥接安装: `uv run crawler4j host install preview <zip>`，确认无误后再执行 `uv run crawler4j host install apply <zip>`
   - GitHub Release 发布: 先执行 `uv run crawler4j release publish --dry-run`，确认无误后再执行 `uv run crawler4j release publish`

## `module init` 帮助信息

```text
crawler4j module init [-h] --repo OWNER/REPO [--output OUTPUT]
                      [--display-name DISPLAY_NAME]
                      [--description DESCRIPTION] [--version VERSION]
                      [--workflow-name WORKFLOW_NAME]
                      [--workflow-display-name WORKFLOW_DISPLAY_NAME]
                      [--workflow-description WORKFLOW_DESCRIPTION]
                      [--python-version PYTHON_VERSION] [--no-git]
                      [--no-install] [--force]
                      name
```

最常用写法:

```bash
uvx --from crawler4j-sdk crawler4j module init hotel_demo --repo owner/hotel_demo --no-git --no-install
```

## 命令分组与常用写法

### `module`

| 命令 | 作用 |
|---|---|
| `uv run crawler4j module show` | 查看模块摘要 |
| `uv run crawler4j module set repo owner/repo` | 更新 `upgrade_source.repo` |
| `uv run crawler4j module set version 0.1.1` | 更新 `module.yaml.version` |
| `uv run crawler4j module set default-workflow hotel_sync` | 更新 `module_runtime.py` 里的默认 workflow |

### `task` / `workflow`

| 命令 | 作用 |
|---|---|
| `uv run crawler4j task create fetch_hotels` | 创建 task 文件 |
| `uv run crawler4j task list` | 列出 `tasks/` 下的 task |
| `uv run crawler4j workflow create hotel_sync --display-name "酒店同步"` | 创建 workflow 并写回 `module.yaml` |
| `uv run crawler4j workflow list` | 列出 `module.yaml.workflows` |

### `page` / `data-table` / `env-selector`

| 命令 | 作用 |
|---|---|
| `uv run crawler4j page create dashboard --display-name "Dashboard"` | 创建代码型页面并设置 `ui_extension.entry` |
| `uv run crawler4j page list` | 列出 `ui/` 下页面文件 |
| `uv run crawler4j data-table create hotels --label "Hotels"` | 注册 `core:data_table:hotels` 并补 `module_runtime.py` helper |
| `uv run crawler4j data-table list` | 列出 `detail_menu` 中的数据表入口 |
| `uv run crawler4j env-selector create random_ready --display-name "随机环境"` | 追加环境选择器函数 |
| `uv run crawler4j env-selector list` | 列出模块声明的环境选择器 |

### `config`

| 命令 | 作用 |
|---|---|
| `uv run crawler4j config show` | 打印当前 `config_defaults` |
| `uv run crawler4j config set module --file module.defaults.yaml` | 从 YAML 文件写模块级默认配置 |
| `uv run crawler4j config set workflow hotel_sync --file workflow.defaults.yaml` | 从 YAML 文件写 workflow 级默认配置 |
| `uv run crawler4j config lint` | 校验 `config_defaults` 结构和 workflow 引用 |

### `check`

| 命令 | 作用 |
|---|---|
| `uv run crawler4j check structure` | 只看骨架、清单和 UI 入口格式 |
| `uv run crawler4j check release` | 在 `structure` 基础上再看版本、仓库、默认配置等发布前提 |
| `uv run crawler4j check full` | 在 `release` 基础上再尝试导入模块、task、workflow、page |

### `package` / `release`

| 命令 | 作用 |
|---|---|
| `uv run crawler4j package build` | 先做 `release` 级校验，再产出正式 ZIP |
| `uv run crawler4j package verify dist/hotel_demo-0.1.0.zip` | 校验已有 ZIP 的单根目录和清单结构 |
| `uv run crawler4j release status` | 查看本地是否具备发布条件 |
| `uv run crawler4j release check-remote` | 查看远端 GitHub Release 最新版本并对比本地版本 |
| `uv run crawler4j release publish --dry-run` | 先打印 `gh release` 将执行的命令 |
| `uv run crawler4j release publish --rebuild` | 发布前强制重新构建 ZIP，再调用 `gh release` |

发布前提直接记 4 条:

- `module.yaml.upgrade_source.repo` 必须是合法 `owner/repo`
- `module.yaml.version` 必须是合法语义化版本
- 默认会使用 `dist/<module>-<version>.zip`
- 本机必须已安装并登录 GitHub CLI `gh`

`release publish` 的真实语义:

- 如果 ZIP 不存在，会自动先构建
- 如果 ZIP 已存在，会先校验再发布
- 只有显式加 `--rebuild` 才会强制重新打包

### `host`

这是面向模块开发者的宿主桥接命令，适合做 DevLink、安装预检和 VS Code 调试配置。

| 命令 | 作用 |
|---|---|
| `uv run crawler4j host devlink add /abs/path/to/module` | 把本地模块目录注册为宿主 DevLink |
| `uv run crawler4j host devlink remove hotel_demo` | 移除宿主中的 DevLink |
| `uv run crawler4j host devlink list` | 查看宿主当前 DevLink 列表 |
| `uv run crawler4j host install preview dist/hotel_demo-0.1.0.zip` | 只做本地 ZIP 安装预检 |
| `uv run crawler4j host install apply dist/hotel_demo-0.1.0.zip` | 直接把 ZIP 安装到宿主 |
| `uv run crawler4j host install preview owner/repo` | 预览 GitHub 源安装 |
| `uv run crawler4j host upgrade check hotel_demo` | 看已安装模块是否有新版本 |
| `uv run crawler4j host upgrade preview hotel_demo` | 下载并预览升级包，但不安装 |
| `uv run crawler4j host upgrade apply hotel_demo` | 下载并安装升级包 |
| `uv run crawler4j host debug config --port 5678` | 生成或更新 VS Code attach 配置 |

`host install <source>` 的 `source` 只认两种:

- 本地 ZIP 路径，例如 `dist/hotel_demo-0.1.0.zip`
- GitHub 仓库，例如 `owner/hotel_demo`

它不接受源码目录；源码目录要走 `host devlink add <module_root>`。

补一条最容易误判的规则:

- `preview` 只预检，不安装
- `apply` 才会真正安装
- 本地 ZIP 默认也会校验 `upgrade_source.repo` 的远端可达性
- 如果你只是本地先验 ZIP 结构，可加 `--skip-remote-check`

## `crawler4j_sdk` 公开导出

| 名称 | 类型 | 模块开发者怎么用 |
|---|---|---|
| `TaskScript` | 基类 | 写 task |
| `TaskFlow` | 基类 | 写 workflow |
| `ModuleAssembler` | 装配器 | 根薄壳使用，业务代码一般不直接调用 |
| `env_selector` | 装饰器 | 声明环境选择器 |
| `EnvSelectorInfo` | 数据类 | 选择器元数据，通常只读不手写 |
| `TaskContext` | 数据类 | 运行上下文 |
| `TaskResult` | 数据类 | 标准结果对象 |
| `TaskSignal` | 数据类 | 控制信号 |
| `TaskSignalAction` | 枚举 | 信号动作 |
| `EnvAction` | 枚举 | 环境后续动作 |
| `ToolSpec` | 数据类 | 工具元数据 |
| `ToolsCapability` | 协议 | `ctx.tools` 的接口 |
| `EnvCandidate` | 数据类 | 环境选择器入参 |
| `ImageInput` / `BBox` / `Point` | 类型别名 | 图像和验证码参数 |
| `SliderCaptcha*` / `ClickCaptcha*` | 数据类 | 验证码返回结果 |

## `TaskContext`

### 主要字段

| 字段 | 说明 |
|---|---|
| `env_id` | 当前环境 ID |
| `task_name` | 当前任务名 |
| `config` | 宿主持久配置视图 |
| `page` | Playwright `Page`，可为空 |
| `context` | Playwright `BrowserContext`，可为空 |
| `logger` | 日志器 |
| `http` | HTTP 客户端 |
| `tools` | Core 注入工具能力，可为空 |
| `captured_data` | 采集结果快照 |
| `state` | 单次执行共享内存 |
| `runtime` | 当前执行期元数据 |

### 常用方法

#### `get_config(key, default=None)`

```python
timeout = ctx.get_config("timeout", 30)
```

#### `wait(seconds)`

```python
await ctx.wait(0.5)
```

#### `screenshot(name)`

```python
path = await ctx.screenshot("login_page")
```

#### `run_subtask(task_name, **kwargs)`

```python
payload = await ctx.run_subtask("fetch_hotels", page_no=1)
```

真实语义:

- 先把 `kwargs` 合并进 `ctx.state`
- 再调用目标 task
- 如果子任务返回 `TaskResult.data`，优先返回这个数据
- 如果没有 `data`，退化成布尔成功语义

#### `should_stop()` / `request_stop()`

workflow 的长循环必须周期性调用 `should_stop()`。

## `TaskResult`

### 主要字段

| 字段 | 说明 |
|---|---|
| `success` | 是否成功 |
| `tasks_completed` | 完成任务数 |
| `message` | 面向结果和日志的说明 |
| `data` | 结构化载荷 |
| `error` | 错误码或错误描述 |
| `signal` | 可选控制信号 |

### 常用构造

```python
return TaskResult.ok(
    tasks_completed=1,
    message="抓取完成",
    data={"records": records},
)
```

```python
return TaskResult.fail(
    message="登录失败",
    error="captcha_error",
    data={"retryable": False},
)
```

`TaskResult.ok(...)` / `fail(...)` 的真实语义:

- 标准结构化载荷字段是 `data`
- 你也可以直接传额外关键字参数；它们最终也会被合并进 `data`
- 为了让新手少误解，文档示例默认优先写显式 `data={...}`

## `TaskSignal`

### 常见动作

- `TaskSignal.succeed(...)`
- `TaskSignal.fail(...)`
- `TaskSignal.wait_for_confirmation(...)`
- `TaskSignal.cancel(...)`

### 当前约束

`wait_for_confirmation(...)` 里:

- `env_action` 只应使用 `EnvAction.KEEP_ALIVE` 或默认值
- 传 `DESTROY` / `RECYCLE` 会直接出错

## `env_selector(...)`

```python
from crawler4j_sdk import EnvCandidate, TaskContext, env_selector


@env_selector(
    name="random_ready",
    display_name="随机选择就绪环境",
    description="从 ready 候选中随机选一个",
)
def random_ready_selector(ctx: TaskContext, candidates: list[EnvCandidate]):
    ready = [item for item in candidates if item.status == "ready"]
    if not ready:
        return None
    return ready[0].env_id
```

参数:

- `name`
- `display_name`
- `description`
- `returns_none`

## `ModuleAssembler`

模块作者需要知道的只有三点:

1. 它会自动发现 `tasks/`、`workflows/` 和 `module_runtime.py`
2. 它优先使用 `ctx.runtime["workflow"]` 选择 workflow
3. 如果 workflow `run()` 返回 `None`，它会把 `ctx.state` 组装成成功结果

## `ToolsCapability` 与 `ToolSpec`

### `ToolsCapability`

公开方法:

- `has_tool(tool_name)`
- `list_tools()`
- `call(tool_name, **kwargs)`

### `ToolSpec`

字段:

- `name`
- `description`
- `is_async`

## 图像与验证码相关类型

### 类型别名

- `ImageInput = str | Path | bytes`
- `BBox = tuple[int, int, int, int]`
- `Point = tuple[int, int]`

### 滑块结果

`SliderCaptchaMatchResult`:

- `target_center`
- `target_bbox`
- `puzzle_piece_offset`
- `debug`

### 点选结果

`ClickCaptchaMatchResult`:

- `ordered_target_centers`
- `ordered_targets`
- `missing_query_orders`
- `ambiguous_query_orders`
- `debug`

如果你要查 `db.*`、`ui.*`、`env.*` 这类宿主注入能力，直接看 [Core 能力参考](reference-core-capabilities.md)。
