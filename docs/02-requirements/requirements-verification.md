# 需求校验

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 发布负责人  
**上游输入：** `prd.md` | `requirements-analysis.md` | 本地验证结果  
**下游输出：** `docs/03-solution/` | `docs/04-delivery/` | `.factory/process/stage-check-report.md`  
**关联 ID：** `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`, `NFR-001`, `NFR-002`, `NFR-003`, `NFR-004`  
**最后更新：** 2026-03-26  

## 1. 校验清单

| ID | 校验内容 | 结果 | 证据 |
|---|---|---|---|
| `REQ-001` | 是否存在真实可导入的 UI 入口 | 通过 | `from src.ui.app import main` 成功 |
| `REQ-001` | 是否存在可直接使用的根脚本入口 | 通过 | `uv sync` 后 `.venv/bin/start` 已导入 `src.ui.app:main` |
| `REQ-001` | 打包规格是否与真实入口一致 | 通过 | 修正后的 `crawler4j.spec` 已成功 PyInstaller 出包 |
| `REQ-002` | 登录工作流是否具备基础可执行形态 | 通过 | `tests/unit/test_core/test_mms/test_ctrip_runtime.py` 覆盖登录路径 |
| `REQ-002` | 完整 labor_workflow 是否已脱离旧依赖 | 通过 | 兼容路径已恢复，打包模块 smoke 确认不再因旧导入缺失而退化 |
| `REQ-003` | SDK / Contracts 是否可本地 build | 通过 | 子包 build 成功 |
| `REQ-003` | SDK CLI 是否可运行帮助页 | 通过 | `uv run python -m crawler4j_sdk.cli.commands --help` |
| `REQ-004` | 发布链路版本信号是否一致 | 通过 | 根应用工作区版本、运行时镜像、最近正式 tag 与 release 文档关系已明确 |
| `REQ-005` | 工厂控制面是否已补齐 | 通过 | 本次已新增 `AGENTS.md`、`GEMINI.md`、`.factory/`、编号文档 |
| `NFR-001` | 是否统一使用 `uv` | 通过 | 现有运行方式与本次验证均基于 `uv` |
| `NFR-002` | 入口与版本一致性 | 通过 | `BUG-001` 与 `CR-001` 已关闭 |
| `NFR-003` | 质量门是否稳定 | 通过 | 测试、UI smoke、build 与默认 `ruff` gate 当前均通过 |
| `NFR-004` | 是否具备可交接基线 | 通过 | 本次已完成 |

## 2. 阶段判断

### 已满足

- 基于当前仓库事实重建 requirements / solution / delivery 最小文档包
- 明确首批工作项
- 明确当前已验证能力与未关闭风险

### 未满足

- `ctrip` 真实站点 E2E 仍未形成正式验证结论

## 3. 建议结论

- 当前项目已进入软件工厂 `IMPLEMENTATION`
- 不建议直接把当前状态标记为 `RELEASE` 或 `MAINTENANCE`
- 下一步更适合安排真实站点 E2E 或发布收口波次

## 4. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-26 | 初始需求校验结论 | Codex |
| 2026-03-26 | 同步 `TASK-005` 完成后的质量门结论 | Codex |
