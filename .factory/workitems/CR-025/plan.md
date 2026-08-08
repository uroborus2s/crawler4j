# CR-025 实施计划

- Work item：`CR-025`
- 当前任务：`TASK-045`
- 输入：用户已确认的环境候选异步与候选上下文契约
- 风险：高（公共 Contracts 与跨层运行契约）
- 执行方式：当前会话 inline，TDD

## 授权执行包

- 目标：实现同步/异步候选、结构化 context、同次结果注入和兼容语义。
- 允许路径：
  - `packages/crawler4j-contracts/src/crawler4j_contracts/{candidate_query.py,context.py,__init__.py}`
  - `packages/crawler4j/src/core/{mms/service.py,mms/runtime_descriptor.py,atm/execution_runner.py,atm/controller.py,atm/runtime_capabilities.py}`
  - `packages/crawler4j-sdk/src/{v2_scanner.py,cli/templates.py,cli/commands.py}`
  - `packages/{crawler4j,crawler4j-contracts,crawler4j-sdk}/pyproject.toml`、`uv.lock`
  - `README.md`、`.factory/project.json`
  - `packages/{crawler4j,crawler4j-sdk,crawler4j-contracts}/README.md`
  - `docs/03-developer-guide/v0.4.0/{index.md,architecture-rules.md,module-structure.md,reference-core-capabilities.md,reference-sdk-and-cli.md}`
  - `docs/04-project-development/03-requirements/{prd.md,requirements-analysis.md,requirements-verification.md}`
  - `docs/04-project-development/04-design/{api-design.md,atm-resource-pool-queue-design.md,module-config-runtime-data-contract.md,system-architecture.md}`
  - `docs/04-project-development/07-release-delivery/version-governance.md`
  - `docs/04-project-development/07-release-delivery/{release-notes.md,acceptance-checklist.md,delivery-package.md}`
  - `docs/03-developer-guide/v0.4.0/shipping.md`
  - `packages/crawler4j-contracts/src/crawler4j_contracts/decorators.py`
  - `packages/crawler4j/tests/{unit,integration,acceptance}/**`
  - `.factory/workitems/CR-025/**`、必要的 `.factory/memory/**`
- 禁止：修改 `ctrip_crawler`；新增依赖；记录候选 context 内容。
- 当前 Gate：用户已授权客户端 `0.4.41` 版本收口、PR 合并 `main` 及 Contracts/SDK 发布；发布后核对索引和隔离安装。

## TASK-045：公共契约与运行闭环

1. RED：新增 Contracts 导出/类型、MMS 同步与异步调用、JSON 边界、ATM context 传递/固定环境/空候选/异常、SDK scanner/manifest 和验收打包测试。
2. GREEN：
   - 新增最小结构化候选结果和 `TaskContext.candidate_context`。
   - Core 单次调用 provider；同步 provider 在线程执行，awaitable 在事件循环 await；结构化 context 校验并归一化。
   - ATM 保存本次候选 context，环境选定后注入 workflow；租约后只复核宿主安全状态，不重跑 provider。
   - SDK 允许 async `env_candidates`、继续限制 cleanup；候选 surface 仅开放 `http.request`。
   - 同步 README、模板和 CLI 文案。
3. 定向验证：相关 unit + integration + acceptance 与目标 Ruff。
4. 版本收口：根应用 `0.4.41`、Contracts `0.4.5`、SDK `0.4.6`、SDK 依赖 Contracts `>=0.4.5,<0.5.0`；同步 lock、README、版本治理、发布文档、项目事实与打包测试，不发布。
5. 集中质量门：独立只读 review；同范围整改；重跑目标测试及项目规定完整 unit、相关 integration/acceptance、三包 build、`uv run ruff check .`、`uv lock --check`、`uvx --from docs-stratego docs-stratego source validate --repo-path .`、`.factory/project.json` / CR-025 ledger JSON 校验与 `git diff --check`。

## 计划自审

- 覆盖：`REQ-017..022`、`NFR-015` 均映射到 TASK-045 与测试。
- 构建性：只复用 stdlib `inspect/json/asyncio` 和现有 uv/pytest/ruff；仓库未配置 mypy，不虚构 type-check gate。
- 占位符：无。
- 回滚：撤回新类型、scanner 允许项和 Core 分支即可恢复旧同步候选行为。
- 版本：按用户补充要求 bump 根应用、Contracts、SDK patch 源码版本，不发布；正式包与桌面资产发布另行处理。
