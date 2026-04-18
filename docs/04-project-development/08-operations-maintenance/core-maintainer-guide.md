# Core 接手与日常维护

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** Core 维护者 | 开发 | QA
**上游输入：** `packages/crawler4j/src/ui/app.py` | `packages/crawler4j/src/core/` | `packages/crawler4j-sdk/` | `.factory/project.json`
**下游输出：** 各阶段过程文档 | `deployment-guide.md` | `operations-runbook.md` | `.factory/memory/`
**关联 ID：** `OPS-003`, `DOC-105`, `REQ-005`
**最后更新：** 2026-04-17

## 1. 第一小时阅读包

1. [接手入口](../../02-user-guide/user-guide.md)
2. [当前真实状态分析](../02-discovery/current-state-analysis.md)
3. [技术选型与工程规则](../04-design/technical-selection.md)
4. [系统架构](../04-design/system-architecture.md)
5. [模块边界](../04-design/module-boundaries.md)
6. [实施方案](../05-development-process/implementation-plan.md)
7. [执行记录](../05-development-process/execution-log.md)
8. [运行手册](operations-runbook.md)

## 2. 先记住这 8 个当前事实

1. 根应用真实入口是 `src.ui.app:main`，当前从 workspace 根通过 `uv run python -m src.ui.app` 启动。
2. 应用启动链会初始化数据库、唯一日志服务、REM、ATM，再创建 `Shell`。
3. `packages/crawler4j/modules/` 现在只是占位目录；真实模块来自应用数据目录下的安装包或 DevLink。
4. `ModuleRegistry` 支持扫描 builtin、external、dev link 三类来源，但正式交付链仍以 zip 安装验收为准。
5. 调试会话只允许针对 `ModuleSource.DEV_LINK` 模块创建。
6. `crawler4j-sdk` 和 `crawler4j-contracts` 已独立成包，CLI 入口是 `crawler4j_sdk.cli.commands:main`。
7. 当前默认质量门仍以 `uv run pytest -q`、`uv run ruff check .`、UI smoke、build 验证为主。
8. 当前最大剩余风险不是文档，而是 `ctrip` 真实站点 E2E 仍未回放。
9. 客户端下拉框已统一走 `src.ui.components.combo_box.StyledComboBox`；新增 UI 时不要再直接实例化原生 `QComboBox`，也不要在页面级样式里覆盖整套 `QComboBox` 外观。
10. 仓库根 `scripts/` 当前保留 `build_workspace_packages.py`、`smoke_test_ui.py` 和 `db_cli.py` 三个维护脚本；其中 `build_workspace_packages.py` 现在通过 root `pyproject.toml` 暴露为 `uv run build` / `uv run publish` 两个短命令；旧的本地调试壳与图标生成脚本已清理。
11. 当前全系统日志已收口到一个统一日志服务：Core `logger`、模块 `ctx.logger` 和标准库 `logging` 都应汇入同一条链路；`系统设置 -> 资源` 修改日志级别/保留天数后应立即热更新，而不是等待重启。

## 3. 日常开发最常用命令

```bash
uv sync --all-packages
uv run python -m src.ui.app
uv run pytest -q
uv run ruff check .
uv run python scripts/smoke_test_ui.py
uv run python -m crawler4j_sdk.cli.commands --help
uv run build
UV_PUBLISH_TOKEN=<your-token> uv run publish crawler4j-sdk
```

## 4. 改动某块代码时要同步什么

| 改动区域 | 至少同步这些文档 |
|---|---|
| 应用入口、启动链、桌面壳层 | `docs/04-project-development/04-design/system-architecture.md`、`docs/04-project-development/04-design/api-design.md`、`docs/04-project-development/08-operations-maintenance/deployment-guide.md` |
| Core 服务边界（ATM/MMS/REM/RunProfile/Debug/Persistence/System） | `docs/04-project-development/04-design/system-architecture.md`、`docs/04-project-development/04-design/module-boundaries.md`、`docs/04-project-development/06-testing-verification/test-plan.md` |
| SDK CLI、模板、模块契约 | `docs/04-project-development/04-design/technical-selection.md`、`docs/03-developer-guide/index.md`、`docs/04-project-development/06-testing-verification/test-plan.md` |
| 文档结构、导航、过程规则 | `docs/index.md`、`docs/01-getting-started/index.md`、`docs/04-project-development/10-traceability/document-index.md`、`docs/04-project-development/06-testing-verification/quality-gates.md` |
| 版本、发布、构建 | `docs/04-project-development/07-release-delivery/version-governance.md`、`docs/04-project-development/07-release-delivery/release-notes.md`、`docs/04-project-development/08-operations-maintenance/deployment-guide.md` |

## 5. 遇到不同问题先看哪里

| 问题 | 优先文档 |
|---|---|
| 入口、模块加载或架构边界不清楚 | `system-architecture.md`、`module-boundaries.md` |
| 模块开发链路或 CLI 行为有疑问 | `docs/03-developer-guide/index.md`、`api-design.md` |
| `ctrip` 发布前真实站点验证怎么做 | `docs/04-project-development/06-testing-verification/ctrip-real-site-e2e-closeout.md` |
| 部署、发布或交付前检查 | `deployment-guide.md`、`acceptance-checklist.md`、`delivery-package.md` |
| 日常巡检、故障分级和恢复动作 | `operations-runbook.md` |

## 6. 当前文档使用边界

- 要理解 Core 当前事实，优先读 `docs/01-getting-started/index.md` 与 `docs/04-project-development/`。
- 要理解模块作者如何创建、调试和交付模块，先读 `docs/03-developer-guide/index.md`，再按需进入对应章节。
- 不再回读旧归档正文，也不再使用 `docs/project-process/` 或 `docs/model-development/` 作为正式入口。

## 7. 当前风险与注意事项

- 工作区可能处于多人并行编辑状态；只收口你负责的文档面，不顺手覆盖别人正在整理的章节。
- `backend-design.md` 已不再是当前事实入口，涉及 Core 实现时以 `system-architecture.md`、`module-boundaries.md` 和当前代码为准。
- 发布和运维动作优先复用新增的验收、交付和运行文档，不再把检查项散落在聊天记录或临时清单里。
