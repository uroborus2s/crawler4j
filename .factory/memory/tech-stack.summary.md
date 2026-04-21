# 技术画像摘要

- 当前画像：Crawler4j Model 项目画像
- 预设：crawler4j-model
- 技术栈：python + crawler4j sdk cli + model/module project
- 最近更新时间：2026-03-28 00:47:22

## 摘要

适用于使用 crawler4j SDK CLI 创建和维护标准 model/模块项目，强调 `module.yaml` 契约（含只读 `config_defaults` 初始化模板）、CLI 脚手架、DevLink/ATM 调试和 zip 安装验收。

## 桌面宿主发布补充栈

- 桌面宿主编译基线固定为 `PyInstaller`。
- macOS 内部发布固定为 `PyInstaller.app + Sparkle`。
- Windows 正式发布固定为 `PyInstaller onedir + Velopack`。
- 宿主可变运行数据继续落在应用数据目录，不回写安装目录。

## 项目范围

- Crawler4j 标准模块项目
- Crawler4j Core 模块开发与验证

## 必装/必选模块

- Python 3.12+
- uv
- crawler4j-sdk CLI
- module.yaml
- TaskScript / TaskFlow
- DevLink / ATM 调试链路

## 关键工程规则

- 创建或补齐模块骨架时优先使用 `crawler4j module init`、`crawler4j task create`、`crawler4j workflow create`、`crawler4j page create`、`crawler4j data-table create`，不要先手写脚手架。
- 模块运行契约以 `module.yaml` 和模块根 `__init__.py` 为准，不把 wheel 元数据当成 Core 加载依据。
- 新增运行时依赖时，同时确认宿主 `crawler4j` 环境可用；不要只改模块项目 `pyproject.toml`。
- 调试与验收优先走 DevLink / ATM 调试与 zip 安装 smoke，避免依赖旧版临时调试脚本。
- 改动 SDK CLI、模板、模块契约或 Core 集成行为时，同时更新模块开发文档与回归测试。

## 管理后台要求

- 暂无。

## 强制技能

- crawler4j-model-project
- python-uv-project
- tdd-workflow

## 推荐初始化动作

- 优先执行 `uvx --from crawler4j-sdk crawler4j module init <module_name> --repo <owner/repo>` 创建模块项目，默认使用 PyPI 最新发布版本；脚本化场景可再加 `--defaults --no-git --no-install`。
- 进入模块项目后优先执行 `uv run crawler4j task create <task_name>`、`uv run crawler4j workflow create <workflow_name>`、`uv run crawler4j page create <page_name>`；需要托管数据表时再执行 `uv run crawler4j data-table create <view_id>`。
- 在 crawler4j Core 源码仓验证本地 CLI 时，优先执行 `uv run python -m crawler4j_sdk.cli.commands --help`。

## 参考资料

- skills/crawler4j-model-project/SKILL.md
- skills/crawler4j-model-project/references/cli-workflow.md
- skills/crawler4j-model-project/references/module-structure.md
- skills/crawler4j-model-project/references/core-integration.md
