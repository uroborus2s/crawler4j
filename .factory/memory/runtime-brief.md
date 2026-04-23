# 项目压缩运行卡

- 生成时间：2026-04-21 01:01:40
- 负责人：AI 软件工厂
- 项目：crawler4j
- 当前阶段：IMPLEMENTATION
- 当前模式：未知
- 技术画像：Crawler4j Model 项目画像
- 技术栈：python + crawler4j sdk cli + model/module project
- 活跃工作项：20
- 阻塞项：0
- 开放风险：0
- 当前源码版本基线：`crawler4j 0.2.0`、`crawler4j-sdk 0.4.0`、`crawler4j-contracts 0.2.0`；最近正式 Git tag：`v0.2.0`
- 最近交接包：无
- 最近快照：无
- 备注：已完成 `TASK-013`、`TASK-025`；模块根入口薄壳 (Shim) 与 SDK 组装器 (ModuleAssembler) 已落地；CLI 已收敛为 `module / task / workflow / page / hook / env-selector / config / package / release / host / check` 分组体系并与集成测试对齐；`module_runtime.py` 已正式收口为宿主接缝薄壳，模块实现按 `pages/`、`hooks/`、`env_selectors/` 拆分；ATM 已彻底删除规则匹配选环境模式，运行模板“选择环境”现统一走模块回调，界面会对 `return_none` 占位选择器给出提示；模块 UI 现已进一步收口为纯 Hosted UI 页面契约：模块清单只保留 `ui_extension.pages[]` 的导航元信息，运行时只保留 `ui.declare_page` / `ui.get_page`，页面通过最小 `ManagedPageRenderer` 渲染 `Page / Section / Text / Button / DataTable`，所有页面组装和数据都由 `load_handler` / `query_handler` 与 `db.*` 能力提供，CLI 与 Core 现在只围绕当前页面协议做正向校验，不再保留面向废弃模块 UI 结构的专门分支；ATM 已收敛为“任务直接持有 RunProfile”模型，`TSM` 与 `strategy_id` 兼容层已删除；ATM/debug/sdk 相关定向回归已通过；当前版本线已收敛为根应用 `0.2.0`、SDK `0.4.0`、Contracts `0.2.0`，README、包描述、release 文档与 `.factory` 摘要已同步，不再混用旧版本口径；ATM Job 创建页现已支持“批次任务 + 执行一次 / Cron”双模式；声明式 `ui/config_schema.json` 与模块目录内 `strategy.yaml` 链路已从脚手架、客户端主链路和相关文档中移除；模块持久配置现统一持久化到 `config.db.module_config_entries`，`ctx.get_config()` 与 `ctx.runtime` 已按“配置 / 运行态”彻底分离，旧 KV 配置兼容迁移与旧 workflow 配置兜底已删除；`module.yaml` 已不再允许声明 `sdk_version_range`，模块必须跟随当前宿主一起升级；模块详情页真实默认配置入口已恢复为模块/工作流 YAML 编辑器，并显式拒绝 JSON/花括号对象字面量，`module.yaml.config_defaults` 现作为首次初始化与“恢复默认”的静态模板，首次加载后升级不会自动覆盖数据库配置；2026-04-17 起 `module.yaml.upgrade_source` 已成为标准必填契约，模块管理页支持 `本地 ZIP` / `GitHub 源` 双安装方式、DevLink 与正式安装的 GitHub 仓库预检，以及基于 GitHub Release 的行级在线升级按钮；2026-04-18 起模块快照数据与审计事件已拆成两条正式能力面：`module_datasets` 继续承载 snapshot dataset，`module_audit_events` 与 `db.append_event` / `db.query_events` 承载 append-only 历史事件；2026-04-21 起 `module_datasets` 已进一步改为按 `(module_name, dataset_name, record_index)` 一条 record 一行持久化，dataset 级元数据由 `module_dataset_manifests` 保留，`init_database()` 对 legacy `records_json` 迁移已改为 fail-fast，避免 silent data loss

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
- `docs/04-project-development/02-discovery/brainstorm-record.md`
- `docs/04-project-development/08-operations-maintenance/core-maintainer-guide.md`
- `docs/04-project-development/05-development-process/implementation-plan.md`
- `docs/04-project-development/04-design/technical-selection.md`
- `docs/04-project-development/04-design/system-architecture.md`
- `docs/04-project-development/04-design/api-design.md`
- `docs/04-project-development/04-design/module-hosted-ui-framework.md`
- `docs/04-project-development/04-design/module-config-runtime-data-contract.md`

## 必守规则

- 不跳阶段。
- 代码类工作必须走 PR 闭环后再关单。
- 任何已接受变更都要同步代码、文档、测试、`.factory/memory/`。
- 遇到阻塞、空转或质量漂移时，优先执行 `factory-dispatch recovery`。
- 发现问题时优先做模式级修复，再把有效做法沉淀到 `evolution-baseline.md`。
- 实现前优先读取 `docs/04-project-development/04-design/technical-selection.md`。
- 任务单位是人天，最小精度 0.5，但不是默认拆分步长。

## 当前推荐动作

- `python3 ../../AiProject/shanforge/scripts/factory-dispatch session --project "." --owner "AI 软件工厂"`
- `python3 ../../AiProject/shanforge/scripts/factory-dispatch board --project "." --owner "AI 软件工厂" --focus "当前协作焦点"`
- `python3 ../../AiProject/shanforge/scripts/factory-dispatch doctor --project "." --owner "AI 软件工厂" --scope full`

## 当前前 5 个活跃工作项

- `TASK-025-implement-hosted-module-ui-framework` TASK-025 实现模块宿主管理页框架 V1 | 状态：DONE | 负责人：Codex
- `TASK-010-optimize-module-developer-guide-for-external-authors` TASK-010 重做模块开发者指南 | 状态：DONE | 负责人：未知
- `TASK-011-mms-settings-store-and-module-state-persistence` TASK-011 建立 MMS settings store 与模块状态持久化 | 状态：DONE | 负责人：未知
- `TASK-012-mms-trust-gate-and-custom-ui-loading` TASK-012 补齐 MMS trust gate 与自定义页面加载 | 状态：DONE | 负责人：未知
- `TASK-013-stabilize-module-root-entry-shim-and-sdk-assembler` TASK-013 统一模块根入口为最新托管方案并要求模块重新初始化 | 状态：DONE | 负责人：Gemini
