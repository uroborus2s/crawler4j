# 技术画像摘要

- 当前画像：Crawler4j Model 项目画像
- 预设：crawler4j-model
- 技术栈：python + crawler4j core + crawler4j-contracts + crawler4j-sdk CLI
- 最近更新时间：2026-04-23 23:59:00

## 摘要

适用于使用 `crawler4j-sdk` CLI 创建和维护 Core 0.4.0 / `core-native-v2` 标准模块项目。模块运行时只依赖 `crawler4j-contracts`，由 Core 负责扫描装饰器、生成 descriptor、装配对象图与执行。

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
- crawler4j-contracts
- core-native-v2 decorators / `object_param` / `object_inject`
- `module.yaml`
- DevLink / ATM 调试链路

## 关键工程规则

- 创建或补齐模块骨架时优先使用 `crawler4j module init`、`crawler4j interface create`、`crawler4j component create`、`crawler4j workflow create`、`crawler4j page-action create`、`crawler4j page create`、`crawler4j data table/query create`，不要先手写脚手架。
- 正式模块协议是 `module.yaml(runtime_api=core-native-v2)` + v2 装饰器扫描 + `.crawler4j/manifest.lock.json`，不依赖根包运行入口或 0.3.x 顶层 spec 导出。
- 对象依赖和 component 对象参数可写在装饰器参数、类属性注解或 `__init__` 参数注解上；SDK scanner 与 Core descriptor 必须归一到同一份元数据。对象参数类型覆盖标量、enum、array、object、json、date/datetime/time、url、path、secret，结构化约束写入 `ParameterSpec.schema/item_schema`。
- 模块运行时代码只 import `crawler4j-contracts`；`crawler4j-sdk` 仅限开发期使用。
- 新增运行时依赖时，同时确认宿主 `crawler4j` 环境可用；不要只改模块项目 `pyproject.toml`。
- 调试与验收优先走 DevLink / ATM 调试与 ZIP 安装 smoke。
- 改动 SDK CLI、模板、模块契约或 Core 集成行为时，同时更新模块开发文档与回归测试。

## 强制技能

- crawler4j-model-project
- python-uv-project
- tdd-workflow

## 推荐初始化动作

- 优先执行 `uvx --from crawler4j-sdk crawler4j module init` 创建模块项目，交互式输入模块名和升级源仓库；脚本化场景再使用 `crawler4j module init <module_name> --repo <owner/repo> --runtime-api core-native-v2`。
- 进入模块项目后优先执行 `uv run crawler4j interface create <name>`、`uv run crawler4j component create <name> --implements <interface>`、`uv run crawler4j workflow create <workflow_name>`、`uv run crawler4j page-action create <action_name>`、`uv run crawler4j data table/query create ...`、`uv run crawler4j manifest lock`。
- 在 Core 源码仓验证本地 CLI 时，优先执行 `uv run python -m crawler4j_sdk.cli.commands <subcommand>`。
