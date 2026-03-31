# 需求分析

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 发布负责人  
**上游输入：** `prd.md` | `current-state-analysis.md`  
**下游输出：** `requirements-verification.md` | `docs/04-project-development/04-design/` | `docs/04-project-development/05-development-process/`  
**关联 ID：** `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`, `REQ-006`, `BUG-001`, `CR-001`, `CR-002`  
**最后更新：** 2026-03-31  

## 1. 需求实现现状判断

| ID | 摘要 | 当前状态 | 依据 |
|---|---|---|---|
| `REQ-001` | 桌面 Core 可启动且入口一致 | 满足 | `start` 脚本已对齐 `src.ui.app:main`，headless smoke 与 PyInstaller 出包通过 |
| `REQ-002` | 模块可执行目标工作流 | 基本满足 | 登录工作流可执行，`labor_workflow` 已恢复基础运行时兼容，但真实站点 E2E 未验证 |
| `REQ-003` | SDK / Contracts / CLI 可用 | 基本满足 | SDK/Contracts build 成功，CLI help 可运行 |
| `REQ-006` | 模块根入口可由工具托管 | 满足 | 根 `__init__.py` 已收敛为稳定薄壳，`ModuleAssembler` 负责默认发现与分发，旧模块升级路径统一为按最新模板重新初始化 |
| `REQ-004` | 发布与文档链路可追溯 | 满足 | 根应用工作区版本、运行时镜像、最近正式 tag 与 release 文档口径已明确分层 |
| `REQ-005` | 软件工厂治理基线存在 | 本次建立 | `AGENTS.md`、`GEMINI.md`、`.factory/`、编号文档已新增 |

## 2. 需求影响分析

### `REQ-001`

- 该需求已在本轮实现中闭环：声明入口、headless smoke、PyInstaller 出包已经对齐。
- 后续仍需保留这组验证，避免入口再次漂移。

### `REQ-002`

- `ctrip` 是仓库中最像真实业务模块的 builtin module。
- 目前 `modules/ctrip/__init__.py` 已显式写出迁移期 fallback 行为，说明维护者已经意识到完整链路未完成。
- 因此该问题不属于“文档与实现不一致”，而是“实现处于兼容性退化状态”。

### `REQ-003`

- SDK/Contracts 是当前仓库最健康的分发链路。
- 因为 SDK CLI 已能提供脚手架入口，所以这部分更适合作为后续规范化的正向样板。

### `REQ-006`

- 根 `__init__.py` 已固定为托管薄壳，运行时组装逻辑收敛到 SDK 的 `ModuleAssembler`。
- 默认工作流解析顺序已经稳定为 `context.config.workflow -> module_runtime.DEFAULT_WORKFLOW -> module.yaml.workflows[0].name`。
- `module_runtime.py` 已明确为可选扩展点，默认脚手架不会生成该文件，只有模块需要自定义 hooks 或手动注册时才创建。
- 本轮不再把“兼容旧模块模板”作为目标，旧模块升级路径统一为按最新脚手架重新初始化。

### `REQ-004`

- `CR-001` 已完成：根应用版本事实源、运行时镜像和最近正式 tag 的关系已经写清。
- SDK / Contracts 继续保留独立版本线，不再要求与根应用共用版本号。

### `REQ-005`

- 工厂基线已经建立，并已开始执行第一轮基于 workitem 的实施。
- 当前阶段应视为 `IMPLEMENTATION`，而不是停留在 `PLAN`。

## 3. 风险与优先级

| 优先级 | 项目 | 原因 |
|---|---|---|
| P1 | `REQ-006` / `TASK-013` 模块根入口自动托管 | 影响模块开发体验、模板稳定性与后续契约演进成本 |

## 4. 结论

该仓库当前已经进入实现阶段，但仍不适合直接跳到“继续开发新功能”的节奏。  
更合理的路径是：

1. 以 `IMPLEMENTATION` 作为当前工厂阶段
2. 维持当前默认质量门与文档导航规则
3. 将 `REQ-006` / `TASK-013` 视为已闭环能力，后续只做回归维护
4. 再处理剩余治理项与真实站点 E2E
5. 然后进入发布收口阶段
