# 技术选型与工程规则

**项目名称：** crawler4j  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 维护者  
**上游输入：** `docs/02-requirements/prd.md` | `docs/02-requirements/requirements-analysis.md`  
**下游输出：** `system-architecture.md` | `module-boundaries.md` | `api-design.md` | `docs/05-quality/test-plan.md`  
**最后更新：** 2026-03-26  

## 1. 技术画像摘要

- 语言：Python 3.12
- 项目管理：`uv`
- 构建后端：Hatchling
- GUI：PyQt6 + qasync
- 浏览器自动化：Playwright
- 网络与异步：aiohttp, httpx, asyncio
- 数据：SQLAlchemy, Alembic, SQLite 风格持久化
- 调度：APScheduler
- 文档：仓库内 Markdown 文档树
- 打包：PyInstaller
- 测试：pytest, pytest-asyncio, pytest-qt
- Lint：ruff

## 2. 选型目标

- 维持桌面端可交付的自动化运行平台
- 保持 SDK 与 Contracts 作为独立可分发子包
- 统一使用 `uv` 执行安装、测试、构建与文档命令
- 在不重写系统的前提下，先把当前运行链路校正到可验证状态

## 3. 必选模块

- Core 桌面应用：`src/`
- 外部模块安装位：运行时应用数据目录中的外部 zip 模块
- SDK：`crawler4j_sdk/`
- Contracts：`crawler4j_contracts/`
- 工厂控制面：`.factory/`

## 4. 工程规则

- 所有 Python 命令统一通过 `uv` 运行。
- 当前真实 UI 入口为 `src.ui.app:main`；在 `BUG-001` 关闭前，不得把 `pyproject.toml` 的 `start` 脚本视为事实源。
- 当前版本治理已按 `docs/06-release/version-governance.md` 收口；不得再把 Git tag、工作区版本和子包版本混为同一条版本线。
- `pytest`、默认 `ruff` gate、UI smoke、源码 build 已纳入当前基线验证；详细规则见 `docs/05-quality/quality-gates.md`。
- 仓库内已不再保留真实内置业务模块；对 `ctrip` 的功能性改动应优先落在外部模块仓与兼容运行时上。

## 5. 当前推荐命令

```bash
uv sync
uv run pytest -q
uv build --out-dir /tmp/crawler4j-build-check
cd crawler4j_sdk && uv build --out-dir /tmp/crawler4j-sdk-build-check
cd crawler4j_contracts && uv build --out-dir /tmp/crawler4j-contracts-build-check
uv run python -m crawler4j_sdk.cli.commands --help
uv run python -m src.ui.app
```

## 6. 同步要求

- 进入实现前必须先读本文件与 `.factory/memory/current-state.md`
- 技术栈、入口、版本、质量门发生变化时，必须同步更新：
  - `docs/03-solution/`
  - `docs/05-quality/test-plan.md`
  - `docs/06-release/release-notes.md`
  - `.factory/memory/tech-stack.summary.md`

## 7. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-26 | 基于当前仓库事实建立技术画像 | Codex |
