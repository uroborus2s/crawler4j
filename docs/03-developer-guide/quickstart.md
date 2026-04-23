# 快速开始

这一页给你一条从零到第一次交付的最短主线。

目标不是把所有概念一次看完，而是先得到一个标准模块项目，并把下面 4 件事跑通：

1. 用当前 CLI 命令树生成模块骨架
2. 用 Hosted UI 接出页面
3. 在宿主里用 DevLink 联调
4. 产出可安装、可升级的正式 ZIP

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

## 第 2 步：按当前命令树补业务骨架

先不要手写脚手架，直接走 CLI：

```bash
uv run crawler4j task create fetch_hotels
uv run crawler4j workflow create hotel_sync --display-name "酒店同步"
uv run crawler4j module set default-workflow hotel_sync
uv run crawler4j page create dashboard --display-name "运营看板"
uv run crawler4j page create accounts --display-name "账号列表"
uv run crawler4j check structure
```

这一步会把项目补成当前正式形态：

- `task create` 生成原子任务文件
- `workflow create` 生成工作流并写回 `module.yaml.workflows`
- `page create` 生成 Hosted UI 页面骨架，并维护 `ui_extension.pages[]`
- `check structure` 做第一次骨架级 gate

## 第 3 步：把清单和源码改成真实业务

优先把 `module.yaml` 改成真实业务值：

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
    - id: accounts
      label: 账号列表
      icon: 📄
config_defaults:
  module:
    city: shanghai
    page_size: 20
```

然后开始补 `module_runtime.py`：

```python
from crawler4j_sdk import TaskContext


def declare_ui(context: TaskContext):
    _declare_dashboard_page(context)
    _declare_accounts_page(context)
    return None
```

页面 schema 里可以直接放 `DataTable` 组件；宿主负责渲染，模块只负责返回数据。

## 第 4 步：跑完整 gate

在第一次联调前，至少跑下面这些命令：

```bash
uv run crawler4j config lint
uv run crawler4j check full
```

## 第 5 步：接到宿主里联调

先切到已经安装 `crawler4j` 宿主 / Core 的环境：

```bash
uv run python -c "import src.core; print('ok: host runtime ready')"
uv run crawler4j host devlink add /absolute/path/to/hotel_demo
uv run crawler4j host debug config
```

然后在宿主里按这条线联调：

1. 打开 `📦 模块管理`，确认模块来源是 `开发链接`
2. 打开 `📋 任务监控`，新建绑定 `hotel_demo` 的作业
3. 选择 `hotel_sync`
4. 点 `▶ 执行一次` 或 `🐞 调试`
5. 在模块详情页确认 `dashboard` 和 `accounts` 都已出现

## 第 6 步：做第一次正式交付

回到模块工程环境构建升级包：

```bash
uv run crawler4j package build
uv run crawler4j package verify dist/hotel_demo-0.1.0.zip
uv run crawler4j release publish --dry-run
uv run crawler4j release publish
```

再回到宿主环境做安装验收：

```bash
uv run crawler4j host install preview dist/hotel_demo-0.1.0.zip --skip-remote-check
uv run crawler4j host install apply dist/hotel_demo-0.1.0.zip --skip-remote-check
```

## 一页记住这条主线

```bash
uvx --from crawler4j-sdk crawler4j module init hotel_demo --repo your-org/hotel_demo
uv run crawler4j task create fetch_hotels
uv run crawler4j workflow create hotel_sync
uv run crawler4j page create dashboard
uv run crawler4j page create accounts
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
