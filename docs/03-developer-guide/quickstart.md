# 快速开始

这一页给你一条从零到第一次交付的最短主线。

目标不是把所有概念一次看完，而是先得到一个标准模块项目，并把下面 4 件事跑通：

1. 用当前 CLI 命令树生成模块骨架
2. 用 Hosted UI V1 接出页面和数据表
3. 在宿主里用 DevLink 联调
4. 产出可安装、可升级的正式 ZIP

## 开始前先确认

至少需要：

- Python `3.12+`
- `uv`
- 一个可写目录

先确认工具链正常：

```bash
python3 --version
uv --version
uvx --from crawler4j-sdk crawler4j --help
```

如果这三条里有任何一条跑不通，不要继续。

## 第 1 步：初始化标准模块项目

下面以 `hotel_demo` 为例：

```bash
cd /absolute/path/to/your/workspace
uvx --from crawler4j-sdk crawler4j module init hotel_demo \
  --repo your-org/hotel_demo \
  --no-git \
  --no-install

cd /absolute/path/to/your/workspace/hotel_demo
uv sync
uv run crawler4j module show
```

从这里开始先记住一个环境边界：

- 你当前所在的是“模块工程环境”，适合执行 `module / task / workflow / page / data-table / config / check / package / release`
- 后面出现的 `host devlink`、`host debug`、`host install`、`host upgrade` 必须切到装有 `crawler4j` 宿主运行时的环境再执行

初始化完成后，先只看这几个文件：

- `module.yaml`
- `pyproject.toml`
- `module_runtime.py`
- `tasks/`
- `workflows/`

你真正长期维护的主入口，也基本只在这几处。

## 第 2 步：按当前命令树补业务骨架

先不要手写脚手架，直接走 CLI：

```bash
uv run crawler4j task create fetch_hotels
uv run crawler4j workflow create hotel_sync --display-name "酒店同步"
uv run crawler4j module set default-workflow hotel_sync
uv run crawler4j page create dashboard --display-name "运营看板"
uv run crawler4j data-table create hotels --label "酒店列表"
uv run crawler4j check structure
```

这一步会把项目补成当前正式形态：

- `task create` 生成原子任务文件
- `workflow create` 生成工作流并写回 `module.yaml.workflows`
- `page create` 生成 Hosted UI V1 的 `core:page:dashboard`
- `data-table create` 生成 Hosted UI V1 的 `core:data_table:hotels`
- `check structure` 做第一次骨架级 gate

从这里开始，项目已经具备“可继续开发”的最小形状。

## 第 3 步：把清单和源码改成真实业务

现在开始进入真正的模块开发。顺序建议固定如下。

### 先改 `module.yaml`

优先把下面这些字段改成真实业务值：

- `display_name`
- `description`
- `version`
- `upgrade_source.repo`
- `workflows[*]`
- `ui_extension.pages`
- `config_defaults`

最小示例：

```yaml
name: hotel_demo
version: 0.1.0
display_name: 酒店采集示例
description: 抓取并维护酒店快照数据
author: crawler4j
upgrade_source:
  type: github_release
  repo: your-org/hotel_demo
  allow_prerelease: false
workflows:
  - name: hotel_sync
    display_name: 酒店同步
    description: 抓取并刷新酒店列表
ui_extension:
  pages:
    - id: dashboard
      label: 运营看板
      icon: 📄
      entry: core:page:dashboard
    - id: hotels
      label: 酒店列表
      icon: 📋
      entry: core:data_table:hotels
config_defaults:
  module:
    city: shanghai
    page_size: 20
  workflows:
    hotel_sync:
      retry_enabled: false
```

这里要直接记死两条约束：

1. 正式 UI 入口只允许 `core:page:<page_id>` 和 `core:data_table:<view_id>`。
2. `upgrade_source.repo` 是后续正式发布和宿主升级的事实源，不是可选备注。

### 再写 `tasks/` 和 `workflows/`

- `tasks/*.py` 负责原子业务动作，例如登录、抓取一页、提交表单
- `workflows/*.py` 负责流程编排，例如顺序、分支、循环、停止判断

不要一上来就在模块里搭第二套 service / repository / manager 体系。这个项目不需要。

### 最后补 `module_runtime.py`

这里主要写 3 类东西：

- 生命周期 hook
- `@env_selector(...)`
- Hosted UI V1 的 `declare_ui()`、`build_*_page_schema()`、`load_*_page()`、数据表 handler

当前正式 UI 只走宿主托管：

```python
def declare_ui(context: TaskContext):
    _declare_dashboard_page(context)
    _declare_hotels_table(context)
    return None
```

不要再创建 `ui/` 目录，也不要导出 `PyQt6` 页面类。

如果你准备开始手改这些函数，先继续看三页细节：

- [UI 与数据表](ui-and-data-table.md)
- [SDK 与 CLI 参考](reference-sdk-and-cli.md)
- [Core 能力参考](reference-core-capabilities.md)

## 第 4 步：跑完整 gate

在第一次联调前，至少跑下面这些命令：

```bash
uv run crawler4j config lint
uv run crawler4j check full
```

这两条分别解决：

- `config lint`：默认配置结构是否合法
- `check full`：模块、task、workflow、Hosted UI V1 是否都能导入和声明

如果 `check full` 没过，不要先去怀疑宿主。先把模块本身修到可导入、可声明。

## 第 5 步：接到宿主里联调

### 先准备宿主环境

从这一步开始，你需要切到“宿主环境”，也就是已经安装 `crawler4j` 宿主 / Core 的那套 Python 环境。

最小确认方式：

```bash
uv run python -c "import src.core; print('ok: host runtime ready')"
uv run crawler4j host devlink list
```

如果这里导入失败或 `host` 子命令报“缺少 crawler4j 宿主运行时”，说明你还停留在只安装了 `crawler4j-sdk` 的模块工程环境。

下面开始默认你已经切到“宿主环境”，也就是能正常运行 `crawler4j` 宿主 / Core 的那套 Python 环境。

先把本地源码挂成 DevLink：

```bash
uv run crawler4j host devlink add /absolute/path/to/hotel_demo
uv run crawler4j host debug config
```

然后在宿主里按这条线联调：

1. 打开 `📦 模块管理`，确认模块来源是 `开发链接`
2. 打开 `📋 任务监控`，新建绑定 `hotel_demo` 的作业
3. 选择 `hotel_sync`
4. 点 `▶ 执行一次` 或 `🐞 调试`
5. 在模块详情页确认 `dashboard` 和 `hotels` 都已出现

这一步的目标是验证两件事：

- 宿主能真正加载你的模块
- Hosted UI V1 入口和业务执行链是通的

DevLink 只用于联调，不用于正式交付。

## 第 6 步：做第一次正式交付

当 DevLink 跑通后，先回到模块工程环境构建升级包：

```bash
uv run crawler4j package build
uv run crawler4j package verify dist/hotel_demo-0.1.0.zip
uv run crawler4j release status
uv run crawler4j release publish --dry-run
uv run crawler4j release publish
```

再回到宿主环境做安装验收：

```bash
uv run crawler4j host install preview dist/hotel_demo-0.1.0.zip --skip-remote-check
uv run crawler4j host install apply dist/hotel_demo-0.1.0.zip --skip-remote-check
```

这时 `upgrade_source.repo` 就开始真正生效了。

## 第 7 步：升级一个已安装模块

模块升级和 DevLink 没关系。正式安装后，升级链路只有这一条：

1. 你先改模块版本
2. 你重新打 ZIP 并发布到 GitHub Release
3. 宿主再检查并安装升级包

对应命令：

```bash
uv run crawler4j module set version 0.1.1
uv run crawler4j package build
uv run crawler4j release publish --rebuild
uv run crawler4j host upgrade check hotel_demo
uv run crawler4j host upgrade preview hotel_demo
uv run crawler4j host upgrade apply hotel_demo
```

这里最重要的事实是：

- `module set version` 改的是你的模块版本
- `release publish` 发布的是你的模块 ZIP
- `host upgrade` 升的是宿主里那个已安装模块

它们都不是在升级 `crawler4j-sdk`，也不是在升级宿主本体。

## 一页记住这条主线

```bash
uvx --from crawler4j-sdk crawler4j module init hotel_demo --repo your-org/hotel_demo
uv run crawler4j task create fetch_hotels
uv run crawler4j workflow create hotel_sync
uv run crawler4j page create dashboard
uv run crawler4j data-table create hotels
uv run crawler4j check full
```

切到宿主环境后：

```bash
uv run crawler4j host devlink add /absolute/path/to/hotel_demo
```

跑通联调后，回到模块工程环境：

```bash
uv run crawler4j package build
uv run crawler4j release publish
```

再回到宿主环境：

```bash
uv run crawler4j host upgrade apply hotel_demo
```

如果你已经走完这条线，下一步按这个顺序继续看：

1. [核心概念](core-concepts.md)
2. [模块结构](module-structure.md)
3. [构建模块](build-modules.md)
