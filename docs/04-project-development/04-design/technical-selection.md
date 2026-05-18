# 技术选型与工程规则

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** AI 软件工厂
**主要读者：** 架构 | 开发 | QA | 模块维护者
**上游输入：** `docs/04-project-development/01-governance/project-charter.md` | `docs/04-project-development/03-requirements/prd.md` | `crawler4j-model` 技术画像
**下游输出：** `system-architecture.md` | `module-boundaries.md` | `api-design.md` | `docs/04-project-development/06-testing-verification/test-plan.md` | `docs/04-project-development/08-operations-maintenance/deployment-guide.md`
**关联 ID：** `REQ-003`, `REQ-006`, `NFR-001`, `NFR-003`
**最后更新：** 2026-04-27

**当前阶段：** DESIGN
**技术画像：** Crawler4j Model 项目画像
**技术栈：** python + crawler4j-sdk CLI + crawler4j-contracts + core-native-v2 module project
**预设：** crawler4j-model
**备注：** 移除固定版本并清理旧预设命令

## 技术画像摘要

适用于使用 crawler4j SDK CLI 创建和维护标准 model/模块项目，强调 `module.yaml(runtime_api=core-native-v2)`、`crawler4j-contracts` 运行时契约、CLI 脚手架、DevLink/ATM 调试和 zip 安装验收。

## 必须落地的项目范围

- Crawler4j 标准模块项目
- Crawler4j Core 模块开发与验证

## 必装/必选模块

- Python 3.12+
- uv
- crawler4j-sdk CLI
- crawler4j-contracts runtime contracts
- module.yaml
- core-native-v2 decorators / object_param / object_inject / @page
- DevLink / ATM 调试链路

## 编码与工程规则

- 创建或补齐模块骨架时优先使用 `crawler4j module init`、`crawler4j interface create`、`crawler4j component create`、`crawler4j workflow create`、`crawler4j page-action create`、`crawler4j page create`，不要先手写脚手架。
- 模块运行契约以 `module.yaml` 和模块根 `__init__.py` 为准，不把 wheel 元数据当成 Core 加载依据。
- 新增运行时依赖时，同时确认宿主 `crawler4j` 环境可用；不要只改模块项目 `pyproject.toml`。
- 调试与验收优先走 DevLink / ATM 调试与 zip 安装 smoke，避免依赖旧版临时调试脚本。
- 改动 SDK CLI、模板、模块契约或 Core 集成行为时，同时更新模块开发文档与回归测试。

## 桌面宿主发布补充约束

- 桌面宿主统一以 `PyInstaller` 作为编译基线，不为不同平台引入第二套应用编译产物。
- macOS 小范围内部发布固定走 `PyInstaller.app + Sparkle`，由 `uv run package-macos-internal-release` 生成 DMG 与 `appcast.xml`。
- Windows 正式发布固定走 `PyInstaller onedir + Velopack`，由 `uv run package-windows-release` 生成 `Setup.exe`、`.nupkg` 与 `releases.<channel>.json`。
- Windows 宿主更新必须保持“应用可变数据不写入安装目录”的边界；当前 `%APPDATA%/Crawler4j/` 数据目录与 Velopack 的安装/替换模型兼容，不允许回退到把运行期数据写回安装目录的方案。
- Windows 正式安装默认使用 Velopack `Setup.exe` 的 per-user 安装路径，不把当前方案收口到 `Program Files` 或管理员权限安装。

## 管理后台要求

- 若当前项目不需要后台，请明确说明。

## 强制技能

- crawler4j-model-project
- python-uv-project
- tdd-workflow

## 初始化与安装动作

- 优先执行 `uvx --from crawler4j-sdk crawler4j module init` 创建模块项目，交互式输入模块名与升级源仓库；脚本化场景使用 `crawler4j module init <module_name> --repo <owner/repo> --runtime-api core-native-v2 --no-git --no-install`。
- 进入模块项目后优先执行 `uv run crawler4j task create <task_name>`、`uv run crawler4j workflow create <workflow_name>`、`uv run crawler4j page create <page_name>`。
- 在 crawler4j Core 源码仓验证本地 CLI 时，优先执行 `uv run python -m crawler4j_sdk.cli.commands --help`。
- 对象依赖和 component 对象参数可以写在装饰器参数里，也可以通过 `Annotated[..., object_inject(...)]` / `Annotated[..., object_param(...)]` 写在类属性或 `__init__` 参数上；SDK scanner 与 Core descriptor 必须把两者归一到同一份元数据。

## 设计/开发/Gate 同步要求

- 进入 IMPLEMENTATION 前，解决方案架构师、后端工程师和前端工程师必须先阅读本文件。
- 技术选型、模块清单或后台范围变化后，同步更新 `system-architecture.md`、`module-boundaries.md`、`api-design.md`、`test-plan.md`、`deployment-guide.md`、`docs/04-project-development/08-operations-maintenance/core-maintainer-guide.md`、`docs/03-developer-guide/index.md`、`docs/02-user-guide/user-guide.md` 和 `.factory/memory/tech-stack.summary.md`。
- 任何涉及该技术画像的 TASK/CR/BUG 在创建或变更时，都应在关联项或说明中引用相关设计条目。
- PR 评审时需检查代码实现、依赖安装、后台范围和文档同步是否与本文件一致。

## 参考资料

- skills/crawler4j-model-project/SKILL.md
- skills/crawler4j-model-project/references/cli-workflow.md
- skills/crawler4j-model-project/references/module-structure.md
- skills/crawler4j-model-project/references/core-integration.md

## 角色强制技能

- solution-architect：crawler4j-model-project、python-uv-project
- backend-engineer：crawler4j-model-project、python-uv-project、tdd-workflow
- frontend-engineer：crawler4j-model-project
- qa-engineer：crawler4j-model-project、python-uv-project、tdd-workflow

## 版本记录

- 2026-03-28 00:29:23: `Crawler4j Model 项目画像` | 负责人：AI 软件工厂 | 备注：启用 crawler4j model 专用 skill
- 2026-03-28 00:36:15: `Crawler4j Model 项目画像` | 负责人：AI 软件工厂 | 备注：修复预设合并后补写强制 skill
- 2026-03-28 00:42:01: `Crawler4j Model 项目画像` | 负责人：AI 软件工厂 | 备注：改为默认使用 PyPI 最新 crawler4j-sdk
- 2026-03-28 00:47:22: `Crawler4j Model 项目画像` | 负责人：AI 软件工厂 | 备注：移除固定版本并清理旧预设命令
- 2026-04-27: 刷新当前技术画像事实，移除 `TaskScript / TaskFlow` 作为当前必选模块的误导表述，并补记运行时代码只依赖 `crawler4j-contracts`
- 2026-04-30: 刷新 0.4.0 v2 对象装配注解入口，登记 `object_param` / `object_inject` 类属性与 `__init__` 参数注解归一规则
