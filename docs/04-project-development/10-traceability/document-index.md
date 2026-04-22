# 文档索引

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 新维护者 | 模块开发者 | Tech Lead | QA | 发布负责人 | 运维
**上游输入：** `docs/index.md` | 当前正式文档树 | 文档治理整改结果
**下游输出：** `docs/01-getting-started/index.md` | `.factory/memory/doc-map.md` | 角色阅读路径
**关联 ID：** `DOC-106`, `TASK-014`, `TASK-019`, `TASK-020`
**最后更新：** 2026-04-22

## 1. 当前正式文档结构

当前正式的人类文档收敛为四大模块：

| 模块 | 作用 | 主要读者 |
|---|---|---|
| `docs/01-getting-started/` | 面向所有人的单页产品介绍和阅读入口 | 第一次接触产品的人 / 协作者 |
| `docs/02-user-guide/` | 开始使用、安装、设置、日常使用、作业详情讲义、异常案例和管理员指南 | 宿主使用者 / 管理员 / 协作者 |
| `docs/03-developer-guide/` | 开发者指南；在本项目中即 module 开发指南 | 模块开发者 / 做模块集成的 Core 成员 |
| `docs/04-project-development/` | 治理、需求、设计、计划、测试、发布、运维和追踪等正式内部文档 | Tech Lead / Dev / QA / 发布 |

## 2. 按角色快速阅读

### 新维护者

1. [根入口](../../index.md)
2. [了解 crawler4j](../../01-getting-started/index.md)
3. [开始使用](../../02-user-guide/user-guide.md)
4. [Core 接手与日常维护](../08-operations-maintenance/core-maintainer-guide.md)
5. [当前真实状态分析](../02-discovery/current-state-analysis.md)
6. [实施方案](../05-development-process/implementation-plan.md)

### 模块开发者

1. [开发者指南总览](../../03-developer-guide/index.md)
2. [快速开始](../../03-developer-guide/quickstart.md)
3. [核心概念](../../03-developer-guide/core-concepts.md)
4. [模块结构](../../03-developer-guide/module-structure.md)
5. [构建模块](../../03-developer-guide/build-modules.md)
6. [Core 能力参考](../../03-developer-guide/reference-core-capabilities.md)
7. [调试模块](../../03-developer-guide/debugging.md)
8. [常见问题](../../03-developer-guide/troubleshooting.md)
9. [交付模块](../../03-developer-guide/shipping.md)

### 发布 / 运维

1. [发布与交付概览](../07-release-delivery/index.md)
2. [验收检查清单](../07-release-delivery/acceptance-checklist.md)
3. [ctrip 真实站点 E2E 收口方案](../06-testing-verification/ctrip-real-site-e2e-closeout.md)
4. [交付包清单](../07-release-delivery/delivery-package.md)
5. [部署与运行说明](../08-operations-maintenance/deployment-guide.md)
6. [运行手册](../08-operations-maintenance/operations-runbook.md)

## 3. 阶段文档入口

| 阶段 | 关键入口 | 作用 |
|---|---|---|
| 治理与调研 | `01-governance/`、`02-discovery/` | 说明背景、范围、风险和现状证据 |
| 需求与设计 | `03-requirements/`、`04-design/` | 说明为什么做、怎么设计、接口和边界是什么 |
| 实施与验证 | `05-development-process/`、`06-testing-verification/` | 说明如何推进、怎么验证、最近执行了什么 |
| 发布与运维 | `07-release-delivery/`、`08-operations-maintenance/` | 说明什么时候能发、如何交付、如何运行和接手 |
| 追踪与演进 | `09-evolution/`、`10-traceability/` | 说明模式级改进、需求覆盖和接口责任 |

## 4. 维护规则

- 根 `docs/index.md` 是唯一的全站导航源；本文件负责“入口解释”和“按角色索引”，不重复维护整棵页面树。
- 任何新增、删除或移动页面，都要同步更新根 `docs/index.md`、本文件和 `.factory/memory/doc-map.md`。
- `docs/project-process/` 与 `docs/model-development/` 不再作为正式入口保留。
- 当前事实以代码、当前文档和可重复验证结果为准。

## 5. 最近同步

- 2026-04-22：已新增 `module-hosted-ui-framework.md`，将“模块不得直接使用 `PyQt6`、宿主统一托管模块页面、最小化 UI 框架 V1 只公开 `Page/Section/Text/Button/DataTable`”正式沉淀为设计文档；`docs/index.md`、`module-boundaries.md`、`api-design.md`、`interface-matrix.md` 与 `.factory/memory/` 摘要已同步到同一口径。
- 2026-04-22：`deployment-guide.md`、根 `README.md`、`packages/crawler4j/README.md` 与 `.env.example` 已同步补记 macOS Sparkle 内部分发的两项新口径：改写 bundle 后自动 ad-hoc 重签，以及 `generate_appcast` 可通过 keychain account / 私钥文件 / 私钥串读取 EdDSA 私钥，不再只依赖默认 `ed25519` 账户名。
- 2026-04-22：`deployment-guide.md`、运维目录索引、根 `README.md` 与 `packages/crawler4j/README.md` 已同步补记 macOS Sparkle unsigned 内部分发的签名口径：`package-macos-internal-release` 当前会写入 `SUEnableCodeSigningValidation=false` 与空 `SUPackageSigningCertificate`，只关闭宿主 app 的苹果代码签名校验，更新包仍保留 EdDSA 校验。
- 2026-04-21：已修正根 `docs/index.md` 中 `ctrip-real-site-e2e-closeout.md` 对应导航项的非法 YAML 标题写法，并把测试收口页标题与本文件入口统一收口为普通字符串，恢复 `docs-stratego` 对文档根索引的解析。
- 2026-04-21：`docs/04-project-development/06-testing-verification/index.md` 与 `test-plan.md` 已同步补记宿主 `qasync` UI 重入回归：REM 环境列表页的创建/编辑/销毁及异步操作提示现统一走非阻塞对话框，仪表盘刷新则改为取消旧 pending load 后再启动新一轮；对应 `.factory/memory/tests.summary.md` 已新增 `TC-043`。
- 2026-04-20：`docs-stratego` 联动发布口径已从 `feature/task-plugin-system` 收口到 `main`；`deployment-guide.md`、运维目录索引与 notify workflow 现统一说明主分支是唯一自动通知来源，且 dispatch token 会先去掉意外换行再发起 `repository_dispatch`。
- 2026-04-20：固定环境池语义已进一步收紧并同步到开发/设计/测试文档：当前只从 `eligible=true + READY + 无租约` 环境集合发号，`KEEP_ALIVE` 留下的 `RUNNING` 环境不会自动回池；若候选在 `get_env` / 租约阶段被别人先抢走，任务会回到等待席位而不是直接失败；对应 ATM/REM 单测已补锁。
- 2026-04-19：已对固定环境池 / 环境队列开发者文档执行“1 个专业文档 reviewer + 2 个模块开发者 reviewer”的三轮苛刻复核；`docs/03-developer-guide/index.md`、`reference-core-capabilities.md`、`build-modules.md`、`debugging.md`、`troubleshooting.md` 以及 `api-design.md`、`atm-resource-pool-queue-design.md` 现统一钉死 `Service Job` 前提、`resource_pool / selector_name / wait_timeout` 语义、`env_id` 来源、`@env_selector(...)` 入口、`replace_resource_pool_snapshot(...)` 全量重建和等待状态文案分层，最终 3 个 reviewer 全部给出 `无 blocker`。
- 2026-04-19：已新增 `docs/04-project-development/02-discovery/atm-resource-pool-queue-brainstorm.md` 与 `docs/04-project-development/04-design/atm-resource-pool-queue-design.md`，把“模块资源池资格标签 + 宿主等待队列 + FIFO 补位 + 黑号先停发号再销毁”的方案沉淀为正式 discovery/design 输入；根 `docs/index.md` 与 `.factory/memory/doc-map.md` 已同步接入。
- 2026-04-17：`docs/01-getting-started/` 已进一步压缩为单页模式，当前只保留 `了解 crawler4j` 这一篇作为正式入口；正文改为面向客户的产品介绍，不再拆成多页教读者选路径，原辅助页已删除。
- 2026-04-17：新增 `docs/02-user-guide/exception-cases.md`，把“应用打不开、页面空白、模块未启用、执行一次没反应、任务实例全失败、环境不可用、升级失败、结果找不到”统一收敛为按症状分诊的异常案例页；每个案例都固定给出“现象 / 先看哪里 / 先做什么 / 什么情况升级给管理员或研发”，并同步接入 `docs/index.md` 与 `docs/02-user-guide/index.md`。
- 2026-04-17：新增 `docs/02-user-guide/job-detail-guide.md`，把“作业详情整图说明”单独收口为培训讲义页，固定按 `任务实例表 -> 结果/错误 -> 任务日志 -> 成功/失败判据 -> 不同状态下一步动作` 的顺序讲解；当前正文已可直接用于培训。
- 2026-04-20：`docs/02-user-guide/configuration.md`、`system-architecture.md`、`api-design.md` 与 `atm-resource-pool-queue-design.md` 已同步补记 ATM Service Job 的 5 秒兜底巡检改为 `JobController` 挂在主 async loop 上的后台协程循环，不再复用 `APScheduler` 周期 job / `run_coroutine_job()` 包装；启动时先做 bootstrap 调和、作业激活/更新时定向调和，5 秒 periodic loop 仅作后续兜底。统一日志服务对 `APScheduler` 周期性心跳日志仍维持 `WARNING` 下限，对应控制器回归测试与日志口径已同步更新。
- 2026-04-17：`docs/02-user-guide/` 已按“普通用户真正能照着走”的标准做第二次完全重写，正式顺序调整为 `安装与第一次打开`、`首次设置`、`开始使用`、`日常使用`、`管理员指南`；本轮补齐了“新手先点哪 3 个入口”“设置参数从哪里拿”“运行模板入口”“结果只认一个入口”“作业状态下一步动作”“IP 池最短操作闭环”“可复制报障模板”，并同步更新根 `docs/index.md` 导航顺序。
- 2026-04-17：按用户要求执行了 3 个专业产品文档子 agent 分工重写和 6 个普通用户子 agent 两轮苛刻复核。普通用户首轮反馈为 `3 PASS / 3 FAIL`，集中指出入口顺序、参数来源、运行模板入口、状态决策和结果入口收束仍不够傻瓜；二次修订后，第二轮 6 个普通用户子 agent 全部给出 `PASS`，并明确表示愿意将当前 `docs/02-user-guide/` 原样发给新同事使用。
- 2026-04-17：`docs/04-project-development/06-testing-verification/` 新增 `ctrip-real-site-e2e-closeout.md`，把真实站点 E2E 的前置条件、Phase A/B/C 执行顺序、证据要求与放行条件收敛为单一正式入口；发布/运维阅读路径已同步纳入该页。
- 2026-04-17：`docs/03-developer-guide/` 已从旧多层目录重排为产品式平铺结构，首页改为正式开发者入口页，`Quick Start`、`Guide`、`Reference`、调试、交付与排障全部一级直达；旧迁移页与对应入口已下线。
- 2026-04-17：开发者指南中的 CLI 命令面已再次对齐到当前本地 `crawler4j-sdk` 实现，统一使用 `module/task/workflow/page/data-table/env-selector/config/package/release/host/check` 分组命令；文档不再固定 `crawler4j-sdk==某个版本`，`reference-sdk-and-cli.md` 的总表与最小安全顺序已补成完整可复制命令。
- 2026-04-17：`docs/03-developer-guide/` 已根据 6 个“小白模块开发者”子 agent 的两轮苛刻复核继续补强：新增 `--repo` 占位值说明、`module set default-workflow`、`ui:DashboardPage` / `ui/__init__.py` 导出关系、`TaskResult.data` / `run_subtask()` 真实语义、CLI 宿主桥接与宿主 UI 安装的互斥路径、DevLink/ATM 最短调试判据，以及 `core:data_table` / 调试 / 排障分叉清单；最终 6 个子 agent 全部给出 PASS。
- 2026-04-17：`docs/02-user-guide/configuration.md`、`docs/04-project-development/04-design/module-config-runtime-data-contract.md` 与开发者指南相关章节已统一模块配置 / 运行态 / 单次运行内状态 / 数据表边界；`core:data_table` schema / records 当前只读写 `data.db`，运行时代码不包含旧 `state.db.kv_store` 自动迁移逻辑。
- 2026-04-18：开发者指南与模块运行时数据契约已补齐“快照数据 vs 审计事件”的统一口径：`db.list_records` / `db.replace_records` 与 `core:data_table` 继续只服务当前快照，append-only 历史单独归到审计事件通道；精确工具签名和持久化表名继续以当前宿主实现为准。
