# 输入与证据清单

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 发布负责人  
**上游输入：** 当前仓库事实  
**下游输出：** `current-state-analysis.md` | `prd.md` | `.factory/memory/current-state.md`  
**关联 ID：** `BIZ-001`, `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`  
**最后更新：** 2026-03-31  

## 1. 盘点范围

- 代码：`packages/crawler4j/`, `packages/crawler4j/modules/`, `packages/crawler4j-sdk/`, `packages/crawler4j-contracts/`
- 配置：根 `pyproject.toml`, `packages/crawler4j/crawler4j.spec`, `.python-version`, `uv.lock`
- 现有文档：根 `README.md`, `docs/`, `packages/crawler4j-sdk/README.md`, `packages/crawler4j-contracts/README.md`
- 发布痕迹：Git tag、`dist/`, `build/`, `packages/crawler4j-sdk/dist/`, `packages/crawler4j-contracts/dist/`
- 可用运行方式：`uv run pytest`, `uv build`, SDK CLI help, UI 入口导入

## 2. 关键事实来源

| 类别 | 证据 | 结论 |
|---|---|---|
| 仓库元信息 | 根 `pyproject.toml` | workspace 根当前只负责开发环境与锁文件，不再承载应用发布元数据 |
| 运行时代码 | `packages/crawler4j/src/ui/app.py` | 实际 UI 启动入口在 `src.ui.app:main` |
| 运行时版本 | `packages/crawler4j/src/core/system/version_service.py` | 运行时版本从包元数据或 `packages/crawler4j/pyproject.toml` 读取 |
| 历史发布 | Git tag `v0.1.1` | 最新已知正式标签日期为 2026-01-03 |
| SDK 包 | `packages/crawler4j-sdk/pyproject.toml` | SDK 当前版本为 `1.1.0`，并已统一切到 `TaskContext.tools` 扩展入口 |
| Contracts 包 | `packages/crawler4j-contracts/pyproject.toml` | Contracts 当前版本为 `1.1.0` |
| 文档体系 | `docs/` | 现已统一为仓库内 Markdown 文档树，不再依赖静态站构建 |
| 模块运行时 | `packages/crawler4j/src/automation/workflows/*`, `packages/crawler4j/src/core/models/*` | 兼容层已恢复，`labor_workflow` 不再因旧导入缺失而退化 |

## 3. 本地验证命令与结果

| 命令 | 日期 | 结果 | 备注 |
|---|---|---|---|
| `uv run pytest -q` | 2026-03-26 | 通过 | `188 passed in 5.21s` |
| `uv run ruff check .` | 2026-03-26 | 通过 | 默认 gate 已收敛到维护范围；历史 `manual/debug/verify/analyze` 脚本不再计入阻塞 |
| `uv build --package crawler4j --out-dir /tmp/crawler4j-build-check` | 2026-03-26 | 通过 | 根应用包 wheel/sdist 可产出 |
| `uv sync --all-packages` + `uv run python -m src.ui.app` 检查 | 2026-03-26 | 通过 | workspace 根可直接启动真实入口 |
| `uv run python scripts/smoke_test_ui.py` | 2026-03-26 | 通过 | headless UI smoke 通过 |
| `uv run pyinstaller --noconfirm --clean --distpath /tmp/crawler4j-pyinstaller-dist --workpath /tmp/crawler4j-pyinstaller-build packages/crawler4j/crawler4j.spec` | 2026-03-26 | 通过 | 修正后的 spec 已成功出包 |
| `uv build --package crawler4j-sdk --out-dir /tmp/crawler4j-sdk-build-check` | 2026-03-26 | 通过 | SDK wheel/sdist 可产出 |
| `uv build --package crawler4j-contracts --out-dir /tmp/crawler4j-contracts-build-check` | 2026-03-26 | 通过 | Contracts wheel/sdist 可产出 |
| `uv run python -m crawler4j_sdk.cli.commands --help` | 2026-03-26 | 通过 | CLI 命令入口可用 |

## 4. 重要输入结论

- 这是一个仍在活跃开发的历史项目，当前工作树并非干净状态。
- workspace 根的开发入口、headless smoke 与 PyInstaller 出包现已对齐。
- 根应用版本事实源已统一到 `packages/crawler4j/pyproject.toml`，运行时版本读取与 release 规则已补齐。
- 自动化测试、默认 lint gate 与 UI smoke 已恢复可用，`ctrip labor_workflow` 已恢复到真实执行链，但仍缺少真实站点 E2E 证明。
