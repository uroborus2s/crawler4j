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
- 当前源码版本基线：`crawler4j 0.3.2`、`crawler4j-sdk 0.6.1`、`crawler4j-contracts 0.4.0`；最近正式 Git tag：`v0.2.0`
- 最近交接包：无
- 最近快照：无
- 备注：2026-04-23 已按方案 A 完成模块运行时硬切换。Core 现为唯一运行时 owner，正式模块契约收口为 `module.yaml(runtime_api=core-native-v1)` + 宿主侧 runtime descriptor 扫描；Core 固定扫描 `tasks/`、`workflows/`、`hooks/`、`env_selectors/`、`pages/` 并直接调度 `TASK/execute`、`WORKFLOW/run`、`handle`、`SELECTOR/select`、`PAGE/handler`。2026-04-24 又补齐了宿主页源码物理分组协议与菜单解耦协议：页面路由仍保持扁平 `page_id`，运行时与 CLI 已允许 `pages/*.py` 和 `pages/<group>/*.py` 两种源码布局，`pages/` 是可路由页面注册表；`module.yaml.ui_extension.pages[]` 只控制左侧菜单，未配置为菜单的详情页/二级页仍可通过 `open_page.page_id` 打开。`crawler4j page create --group <group>` 会把页面骨架落到分组目录，`--no-menu` 会只创建页面文件不写入菜单配置。`crawler4j-contracts` 承载共享运行时契约、`ctx.db` fluent API 与 Hosted UI schema 归一化 helper；`crawler4j-sdk` 仅保留 CLI、脚手架、校验与开发辅助，不再导出 `ModuleAssembler`、`TaskScript`、`TaskFlow`、`env_selector`、资源池运行时 helper 或任何运行时 owner 身份。模块运行时代码只允许依赖 `crawler4j-contracts`；数据库唯一开发者入口为 `ctx.db`，旧 `ctx.tools.call("db.*")` 会被 SDK AST 扫描拒绝且运行时不注册；非数据库宿主能力仍走 `ctx.tools.call(...)`，资源池资格卡片通过宿主 `env.*` tools 维护，模块如需便捷函数只能在本模块内自封装薄 helper。缺少 `runtime_api: core-native-v1` 或仍保留旧运行薄壳的模块会被明确拒绝加载，不再提供兼容桥。历史主回归证据：2026-04-24 全量 `694 passed`、`ruff check .` 与 `uv lock --check` 通过；本轮文档/记忆同步未重新执行全量测试、打包或发布。

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
