# Core 接手与日常维护

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** Core 维护者 | 开发 | QA  
**上游输入：** `src/ui/app.py` | `src/core/` | `crawler4j_sdk/` | `.factory/project.json`  
**下游输出：** 各阶段过程文档 | `.factory/memory/`  
**最后更新：** 2026-03-28  

## 1. 先记住这 8 个当前事实

1. 根应用真实入口是 `src.ui.app:main`，`uv run start` 与它一致。
2. 应用启动链会初始化数据库、日志、REM、ATM，再创建 `Shell`。
3. `modules/` 现在只是占位目录；真实模块来自应用数据目录下的安装包或 DevLink。
4. `ModuleRegistry` 支持扫描 builtin、external、dev link 三类来源，但正式交付链仍以 zip 安装验收为准。
5. 调试会话只允许针对 `ModuleSource.DEV_LINK` 模块创建。
6. `crawler4j_sdk` 和 `crawler4j_contracts` 已独立成包，CLI 入口是 `crawler4j_sdk.cli.commands:main`。
7. 当前默认质量门仍以 `uv run pytest -q`、`uv run ruff check .`、UI smoke、build 验证为主。
8. 当前最大剩余风险不是文档，而是 `ctrip` 真实站点 E2E 仍未回放。

## 2. 日常开发最常用命令

```bash
uv sync
uv run start
uv run python -m src.ui.app
uv run pytest -q
uv run ruff check .
uv run python scripts/smoke_test_ui.py
uv run python -m crawler4j_sdk.cli.commands --help
uv build --out-dir /tmp/crawler4j-build-check
```

## 3. 改动某块代码时要同步什么

| 改动区域 | 至少同步这些文档 |
|---|---|
| 应用入口、启动链、桌面壳层 | `docs/03-solution/system-architecture.md`、`docs/03-solution/api-design.md`、`docs/07-operations/deployment-guide.md` |
| Core 服务边界（ATM/MMS/REM/TSM/Debug/Persistence/System） | `docs/03-solution/system-architecture.md`、`docs/03-solution/module-boundaries.md`、`docs/05-quality/test-plan.md` |
| SDK CLI、模板、模块契约 | `docs/03-solution/technical-selection.md`、`docs/model-development/index.md`、`docs/05-quality/test-plan.md` |
| 文档结构、导航、过程规则 | `docs/index.md`、`docs/project-process/index.md`、`docs/traceability/document-index.md`、`docs/05-quality/quality-gates.md` |
| 版本、发布、构建 | `docs/06-release/version-governance.md`、`docs/06-release/release-notes.md`、`docs/07-operations/deployment-guide.md` |

## 4. 当前文档使用边界

- 要理解 Core 当前事实，优先读 `docs/project-process/` 与编号过程文档。
- 要理解模块作者如何创建、调试和交付模块，先读 `docs/model-development/index.md`，再按需进入对应章节。
- 要追历史背景、旧规格或旧设计，读 `docs/archive/`，但不得把它直接当成当前事实源。

## 5. 当前风险与注意事项

- `docs/archive/` 里保留了大量旧资料，默认不要散读，只有在当前文档证据不足时才回看。
- 工作区可能处于多人并行编辑状态；只收口你负责的文档面，不顺手覆盖别人正在整理的章节。
- `backend-design.md` 已不再是当前事实入口，涉及 Core 实现时以 `system-architecture.md`、`module-boundaries.md` 和当前代码为准。
