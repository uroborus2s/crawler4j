# 项目压缩运行卡

- 生成时间：2026-04-23 23:59:00
- 负责人：AI 软件工厂
- 项目：crawler4j
- 当前阶段：IMPLEMENTATION
- 当前模式：Default
- 技术画像：Crawler4j Model 项目画像
- 技术栈：python + crawler4j core + crawler4j-contracts + crawler4j-sdk CLI
- 活跃工作项：21
- 阻塞项：0
- 开放风险：1
- 当前源码版本基线：`crawler4j 0.4.0`、`crawler4j-sdk 0.4.0`、`crawler4j-contracts 0.4.0`；最近正式 Git tag：`v0.2.0`
- 当前 0.4.x 边界：本分支只支持 Core 0.4.0 / `core-native-v2`，SDK 与 Contracts 已破坏性升级；0.3.x SDK / Contracts / 旧开发方式在 0.3.x 分支维护，不在当前分支兼容。
- 当前 0.4.x SDK 初始化入口：新手优先使用 `uvx --from crawler4j-sdk crawler4j module init` 交互式输入模块名与 `owner/repo`，非必填项走默认值；脚本化/资深开发者仍可完整传参执行。
- 当前 0.4.x 对象装配入口：`@component/@workflow` 的 `inject` 与 component 对象参数可继续写在装饰器参数里，也可通过类属性或 `__init__` 参数上的 `Annotated[..., object_inject(...)]` / `Annotated[..., object_param(...)]` 声明；Contracts、SDK scanner、Core descriptor 已统一归一到 `InjectSpec` / `ParameterSpec`。`object_param` 参数类型覆盖 `string/text/integer/number/boolean/enum/array/object/json/date/datetime/time/url/path/secret`，结构化参数通过 `schema` / `item_schema` 描述。
- 最近交接包：无
- 最近快照：无
- 备注：当前 0.4.0 正式方案为 `core-native-v2` 装饰器对象装配。运行能力事实源是代码装饰器；workflow 不声明 parameters，只接收宿主装配对象；component 参数只用于对象创建；task 退化为 `@page_action` 纯函数；Hosted UI 页面统一由 `pages/*.py` 或 `pages/<group>/*.py` 中的 `@page(...)` 声明，`@page(menu=True)` 控制左侧菜单，`module.yaml.ui_extension` 与 `PageSpec` 已退出正式契约；旧生命周期 hooks 已退出当前运行链，Core 不再提供 `RunProfile.execution.hooks_module`、`ModuleService.call_hook()` 或 `prepare_env/init_env/before_run/on_*` 兼容入口，模块流程控制通过 workflow 主体返回 `TaskResult` 或发出 `TaskSignal`；环境选择统一由 `candidates/*.py` 中的 `@env_candidates` 同步纯函数声明，函数返回 env id 列表或 `EnvCandidates` 链式查询，Core 每次调度实时求值，不维护资源池同步快照；批量环境清理由 `cleanups/*.py` 中的 `@env_cleanup_candidates` 同步纯函数声明，复用 `EnvCandidates` DSL 但隔离删除语义，由宿主客户端预览确认并在 REM 二次安全校验后执行 `destroy_env()`。Core 为每个 task/env 创建独立对象图，SDK/Contracts 负责装饰器、扫描、校验、迁移和 manifest lock。`crawler4j-contracts` 承载共享运行时契约、`ctx.db` fluent API、`EnvCandidates` DSL 与 Hosted UI schema 归一化 helper；`crawler4j-sdk` 仅保留 CLI、脚手架、校验与开发辅助，不再导出 `ModuleAssembler`、`TaskScript`、`TaskFlow`、`env_selector`、资源池运行时 helper 或任何运行时 owner 身份。模块运行时代码只允许依赖 `crawler4j-contracts`；数据库唯一开发者入口为 `ctx.db`，旧 `ctx.tools.call("db.*")` 会被 SDK AST 扫描拒绝且运行时不注册；非数据库宿主能力仍走 `ctx.tools.call(...)`。同日补充 docs-stratego 指南版本分流方案：只对 `02-user-guide` 与 `03-developer-guide` 建立版本目录，网站主文档指向当前已发布版本，历史版本保留，未发布版本只做预览。当前环境候选与 hook 清理最终回归：`uv run pytest packages/crawler4j/tests -q` => `881 passed`，`ruff check` 与 `git diff --check` 通过；本轮批量清理聚焦回归：`123 passed`。

## AI 最小读取顺序

1. 先读本文件 `/.factory/memory/runtime-brief.md`
2. 再读 `/.factory/memory/role-charter.project.md`
3. 再读 `/.factory/project.json`
4. 再读 `/.factory/memory/motivation-state.md`、`/.factory/memory/autonomy-rules.md`、`/.factory/memory/evolution-baseline.md`
5. 再读当前阶段核心文档
6. 只有需要背景解释时，才读人类长文档

## 当前阶段核心文档

- `docs/01-getting-started/index.md`
- `docs/03-developer-guide/index.md`
- `docs/04-project-development/05-development-process/implementation-plan.md`
- `docs/04-project-development/04-design/technical-selection.md`
- `docs/04-project-development/04-design/system-architecture.md`
- `docs/04-project-development/04-design/api-design.md`
- `docs/04-project-development/04-design/module-config-runtime-data-contract.md`

## 必守规则

- 不跳阶段。
- 代码类工作必须走 PR 闭环后再关单。
- 任何已接受变更都要同步代码、文档、测试、`.factory/memory/`。
- 遇到阻塞、空转或质量漂移时，优先执行 `factory-dispatch recovery`。
- 发现问题时优先做模式级修复，再把有效做法沉淀到 `evolution-baseline.md`。
- 实现前优先读取 `docs/04-project-development/04-design/technical-selection.md`。

## 当前推荐动作

- `python3 ../../AiProject/shanforge/scripts/factory-dispatch session --project "." --owner "AI 软件工厂"`
- `python3 ../../AiProject/shanforge/scripts/factory-dispatch board --project "." --owner "AI 软件工厂" --focus "当前协作焦点"`
- `python3 ../../AiProject/shanforge/scripts/factory-dispatch doctor --project "." --owner "AI 软件工厂" --scope full`

## 当前前 5 个活跃工作项

- `TASK-028-implement-module-entity-table-view-query-capability` TASK-028 实现模块实体表视图与分析查询能力 | 状态：DONE | 负责人：Codex
- `TASK-027-implement-hosted-ui-master-detail-row-navigation` TASK-027 Hosted UI 主从表导航 | 状态：DONE | 负责人：Codex
- `TASK-026-implement-module-data-resource-storage-modes` TASK-026 模块数据资源统一登记与存储模式 | 状态：DONE | 负责人：Codex
- `TASK-025-implement-hosted-module-ui-framework` TASK-025 实现模块宿主管理页框架 V1 | 状态：DONE | 负责人：Codex
- `TASK-013-stabilize-module-root-entry-shim-and-sdk-assembler` TASK-013 旧模块入口托管方案历史任务；现已被 `core-native-v1` 宿主扫描协议取代 | 状态：DONE | 负责人：Gemini
