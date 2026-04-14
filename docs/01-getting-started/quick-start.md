# 快速开始

本页给出三条最短路径：快速认路、把宿主跑起来、以及判断下一步该读哪部分文档。

## 1. 先选你的目标

| 你的目标 | 先读哪里 |
|---|---|
| 只想快速理解项目结构 | [项目概览](./project-overview.md) -> [文档地图](./document-map.md) |
| 想把宿主应用跑起来 | [安装说明](../02-user-guide/installation.md) -> [配置说明](../02-user-guide/configuration.md) -> [使用说明](../02-user-guide/usage.md) |
| 想开发模块 | [开发者指南总览](../03-developer-guide/index.md) |
| 想接手 Core | [接手入口](../02-user-guide/user-guide.md) -> [Core 接手与日常维护](../04-project-development/08-operations-maintenance/core-maintainer-guide.md) |

## 2. 本地启动宿主的最短路径

如果你已经拿到源码仓库，当前最短启动路径是：

```bash
uv sync --all-packages
uv run python -m src.ui.app
```

如果你需要显式从 Python 模块入口启动，也可以执行：

```bash
uv run python -m src.ui.app
```

启动成功后，应用会自动初始化数据库、日志、REM、ATM，并打开桌面 Shell。

## 3. 建议顺手做的 3 个最小检查

```bash
uv run python -m crawler4j_sdk.cli.commands --help
uv run python scripts/smoke_test_ui.py
uv run pytest -q
```

这三个检查分别覆盖：

- SDK CLI 是否可用
- 桌面入口和 `Shell` 初始化是否正常
- 默认自动化测试是否仍然通过

如果你只是临时认路，不一定要一次性全跑；但如果你准备接手维护，这三项值得至少执行一遍。

## 4. 启动后先看哪些页面

第一次打开应用，建议按下面顺序确认：

1. `🔧 系统设置`：确认语言、代理、浏览器和日志设置是否符合当前环境。
2. `📦 模块管理`：确认当前有哪些模块、来源是正式安装还是 DevLink。
3. `📋 任务监控`：确认作业里的运行配置 `execution.module` / `execution.workflow` 指向什么。
4. `📋 任务监控`：确认作业是否已配置运行模板、是否能运行或进入调试。

## 5. 当前最常用命令

```bash
uv sync --all-packages
uv run python -m src.ui.app
uv run pytest -q
uv run ruff check .
uv run python scripts/smoke_test_ui.py
uv build --package crawler4j --out-dir /tmp/crawler4j-build-check
uv run python -m crawler4j_sdk.cli.commands --help
```

## 6. 继续往下读什么

- 如果你要作为宿主使用者或协作者继续操作应用，转到 [用户指南概览](../02-user-guide/index.md)。
- 如果你要开始做模块开发，转到 [开发者指南总览](../03-developer-guide/index.md)。
- 如果你要接手仓库维护与发布，转到 [Core 接手与日常维护](../04-project-development/08-operations-maintenance/core-maintainer-guide.md)。
