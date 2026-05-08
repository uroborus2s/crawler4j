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
- 当前 0.4.x 对象装配入口：`@component/@workflow` 的 `inject` 与 component 对象参数可继续写在装饰器参数里，也可通过类属性或 `__init__` 参数上的 `Annotated[..., object_inject(...)]` / `Annotated[..., object_param(...)]` 声明；Contracts、SDK scanner、Core descriptor 已统一归一到 `InjectSpec` / `ParameterSpec`。`object_param` 参数类型覆盖 `string/text/integer/number/boolean/enum/array/object/json/date/datetime/time/url/path/secret`，结构化参数通过 `schema` / `item_schema` 描述。ATM 运行模板 UI 使用公共 `ObjectGraphTree`，以 `workflow -> interface 绑定行 -> 子 interface/参数` 树形展示对象图；绑定行左侧显示 interface 中文 `label(name)`，右侧下拉框显示 component 中文 `label(name)`，interface 选择写入 `object_bindings`，component 创建参数写入 `object_params`。
- 当前 0.4.x 数据表入口：`module.yaml.data` 不是正式事实源，模块数据表只由 `@data_table` / `@data_query` 进入 manifest lock 后同步；`@data_table` 默认 `custom_table`，旧快照表语义必须显式写 `storage_mode="managed_dataset"` 并继续落到 `data.db.module_datasets`；`@data_query` 只允许引用 `custom_table`。
- 最近交接包：无
- 最近快照：无
- 备注：当前 0.4.0 正式方案为 `core-native-v2` 装饰器对象装配。运行能力事实源是代码装饰器；workflow 不声明 parameters，只接收宿主装配对象；component 参数只用于对象创建；task 退化为 `@page_action` 纯函数；Hosted UI 页面统一由 `pages/*.py` 或 `pages/<group>/*.py` 中的 `@page(...)` 声明，`@page(menu=True)` 控制左侧菜单，`module.yaml.ui_extension` 与 `PageSpec` 已退出正式契约；旧生命周期 hooks、`TaskSignal` 与 `EnvAction` 已退出当前运行链，Core 不再提供 `RunProfile.execution.hooks_module`、`ModuleService.call_hook()`、`prepare_env/init_env/before_run/on_*`、模块信号确认或模块环境处置入口。模块流程控制只通过 workflow 主体返回 `TaskResult`，workflow/component 可选实现 `setup(ctx, workflow)` 做运行前准备，可选实现 `cleanup(ctx, outcome)` 做终态日志、审计或资源释放；`workflow` 和 `outcome.workflow` 保存当前 workflow 元信息，`outcome.status` 覆盖 `succeeded/failed/timed_out/cancelled`。环境选择统一由 `candidates/*.py` 中的 `@env_candidates` 同步纯函数声明，函数返回 env id 列表或 `EnvCandidates` 链式查询，Core 每次调度实时求值，不维护资源池同步快照；任务终态后的环境统一由宿主回收，创建环境会先写入 `host.env_claim(pending)`，终态按 `@data_table(..., env_binding_field="env_id")` 扫描模块业务表并标记 `claimed/abandoned`。批量环境清理由环境管理页 `清理环境` 统一触发：宿主扫描孤岛、未认领、owner 模块缺失环境，并合并 `cleanups/*.py` 中 `@env_cleanup_candidates` 声明的同模块、已认领、已绑定且业务上可丢弃候选，预览确认后在 REM 二次安全校验下执行 `destroy_env()`。Core 为每个 task/env 创建独立对象图，SDK/Contracts 负责装饰器、扫描、校验、迁移和 manifest lock。`crawler4j-contracts` 承载共享运行时契约、`TaskOutcome` / `WorkflowLifecycleInfo`、`ctx.db` fluent API、`EnvCandidates` DSL 与 Hosted UI schema 归一化 helper；`crawler4j-sdk` 仅保留 CLI、脚手架、校验与开发辅助，不再导出 `ModuleAssembler`、`TaskScript`、`TaskFlow`、`env_selector`、资源池运行时 helper 或任何运行时 owner 身份。模块运行时代码只允许依赖 `crawler4j-contracts`；数据库唯一开发者入口为 `ctx.db`，旧 `ctx.tools.call("db.*")` 会被 SDK AST 扫描拒绝且运行时不注册；非数据库宿主能力仍走 `ctx.tools.call(...)`。docs-stratego 指南版本分流方案只对 `02-user-guide` 与 `03-developer-guide` 建立版本目录，网站主文档指向当前已发布版本，历史版本保留，未发布版本只做预览。

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
