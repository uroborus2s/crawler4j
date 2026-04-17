# 当前真实状态分析

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 发布负责人  
**上游输入：** `input.md` | 当前仓库代码与构建结果  
**下游输出：** `docs/04-project-development/03-requirements/` | `.factory/memory/current-state.md` | 首批工作项  
**关联 ID：** `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`, `RISK-001`, `RISK-002`, `RISK-003`  
**最后更新：** 2026-03-31  

## 1. 项目形态

蛛行演略（crawler4j）当前是一个由 5 个主要部分组成的 Python monorepo：

1. `packages/crawler4j/`：PyQt6 桌面应用与核心运行时
2. `packages/crawler4j/modules/`：当前仅保留占位说明，真实业务模块已切到外部安装包模式
3. `packages/crawler4j-sdk/`：面向模块作者的 SDK 与 CLI
4. `packages/crawler4j-contracts/`：Core 与 SDK 的共享契约
5. `docs/`：统一后的 Markdown 文档树，仅保留当前正式文档

## 2. 已验证的能力

| 领域 | 状态 | 证据 |
|---|---|---|
| 自动化测试 | 通过 | `uv run pytest -q` -> `188 passed` |
| MMS settings store 基础能力 | 通过 | 模块级/工作流级 settings、导出与模块启停状态持久化已落地并有单测覆盖 |
| MMS 自定义页面 trust gate | 通过 | `ui:*` 页面已支持受信加载，外部模块默认拒绝，allowlist 命中后可真实装载 |
| 文档体系 | 通过 | `docs/` 已统一为 Markdown 文档树，不再依赖静态站构建 |
| 应用入口 | 通过 | workspace 根通过 `uv run python -m src.ui.app` 启动 `packages/crawler4j` 中的真实入口 |
| UI smoke | 通过 | `uv run python scripts/smoke_test_ui.py` 通过 |
| 外部模块安装链路 | 通过 | 已验证外部 zip 包可被安装到应用受控目录并被 Core 加载 |
| `ctrip` 登录工作流 | 通过 | 外部安装包链路下 `login_workflow` 可运行 |
| `ctrip` 完整 labor 工作流 | 主链收敛 | 旧 `src.automation.*` 兼容包已删除；当前只保留 MMS + ModuleAssembler 正式执行链 |
| 宿主 / 模块职责边界 | 已收口 | 宿主源码已移除 `src/utils` 业务辅助代码、`src/core/models` 业务模型与历史 smoke/verify 脚本；相关逻辑由模块侧独立承载并经测试验证 |
| 版本治理 | 已收口 | 根应用工作区版本由 `packages/crawler4j/pyproject.toml` 单点声明，运行时版本服务与最新正式 tag `v0.1.1` 已明确分层 |

## 3. 已验证的缺口

| 领域 | 状态 | 证据 | 影响 |
|---|---|---|---|
| 模块完整业务 E2E | 未验证 | 当前只验证了 `labor_workflow` 已进入真实执行链，不再因兼容缺失而退化 | 真实站点闭环仍需后续专门回放 |
| 历史人工脚本治理 | 已划清边界 | `uv run ruff check .` 已通过；`manual/debug/verify/analyze` 脚本已移出默认 gate | 历史脚本仍可保留，但不再阻塞默认质量门 |

## 4. 版本与发布状态

### 4.1 当前仓库中的版本信号

| 来源 | 值 |
|---|---|
| 应用包 `packages/crawler4j/pyproject.toml` | `0.1.2.dev20260326` |
| 运行时版本服务 | 从 `packages/crawler4j/pyproject.toml` 或已安装包元数据读取 |
| 最近正式 Git tag | `v0.1.1` |
| SDK | `1.1.0` |
| Contracts | `1.1.0` |

### 4.2 最新已知发布结果

- 最新已知正式 Git tag 为 `v0.1.1`，Tag 时间为 2026-01-03。
- 根仓库中保留了 `dist/Crawler4j.app`、`dist/Crawler4j/`、`build/crawler4j/` 等历史打包产物。
- SDK 与 Contracts 的 `dist/` 中保留了 `1.0.0`、`1.0.1`、`1.0.2`、`1.0.3` 等历史产物。
- 当前 SDK 代码口径已经提升到 `1.1.0`，并将宿主扩展能力收敛到 `TaskContext.tools`；旧模块需要升级到 `ctx.tools.call(...)` 统一接口。
- 当前工作区版本已统一为 `0.1.2.dev20260326`，并明确表示它领先于最新正式 tag `v0.1.1`。

## 5. 文档状态

- 当前 `docs/` 已收敛为四大模块：`docs/01-getting-started/`、`docs/02-user-guide/`、`docs/03-developer-guide/`、`docs/04-project-development/`。
- 当前正式入口以 `docs/01-getting-started/index.md`、`docs/02-user-guide/user-guide.md`、`docs/03-developer-guide/index.md` 和 `docs/04-project-development/10-traceability/document-index.md` 为主。
- 旧 SRS、旧设计、旧测试和旧用户专题文档已从当前文档树移除，避免与现行实现形成双事实源。
- 本仓不再承担独立静态文档站构建职责。
- 当前事实以代码、当前文档和本地验证结果为准。

## 6. 当前真实结论

该项目不是“无法运行的废旧仓库”，而是“核心结构、外部模块安装链路、自动化测试、文档体系、版本治理、默认质量门和 MMS 高阶能力都已经基本收敛，只剩真实站点 E2E 与正式发布收口”的历史项目。  
因此最合适的工厂接入姿势不是从零开始，而是：

1. 先把真实状态压实为文档和工作项
2. 再按批次用 `BUG` / `CR` / `TASK` 修复当前阻塞项
3. 按用户指定顺序继续推进 MMS 高阶能力收口
