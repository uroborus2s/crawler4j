# 测试计划

**项目名称：** crawler4j  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** QA | 开发 | 架构 | 发布负责人  
**上游输入：** `docs/02-requirements/prd.md` | `docs/03-solution/api-design.md` | `docs/04-delivery/implementation-plan.md`  
**下游输出：** `.factory/process/quality-check-report.md` | 后续测试报告  
**关联 ID：** `TC-001`, `TC-002`, `TC-003`, `TC-004`, `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `NFR-003`  
**最后更新：** 2026-03-26  

## 1. 测试目标

- 验证当前仓库哪些链路已经稳定可用
- 明确首批实施波次需要补强的验证点

## 2. 当前测试策略

| 层次 | 目标 | 责任方 | 当前方式 |
|---|---|---|---|
| 单元测试 | 核心服务、SDK 契约、部分模块运行时 | Dev / QA | `uv run pytest -q` |
| 集成测试 | 调试会话、模块加载、CLI 场景 | Dev / QA | `tests/integration/` |
| 静态检查 | 维护范围代码风格与低级错误 | Dev / QA | `uv run ruff check .`（按 `quality-gates.md` 的维护范围规则执行） |
| 构建验证 | 确认包可以产出 wheel/sdist | Dev / Release | `uv build` 与子包 build |
| 入口 / 打包 smoke | 确认根应用入口与桌面打包可运行 | Dev / Release | root script 检查 + headless UI smoke + PyInstaller build |

## 3. 当前已知结果

| 测试项 | 结果 | 备注 |
|---|---|---|
| `TC-001` `uv run pytest -q` | 通过 | 188 passed |
| `TC-002` 根包 / SDK / Contracts build | 通过 | 当前仅证明可构建，不等于可运行 |
| `TC-003` `uv sync` + `.venv/bin/start` | 通过 | root script 已对齐 `src.ui.app:main` |
| `TC-004` `uv run python scripts/smoke_test_ui.py` | 通过 | headless UI smoke 通过 |
| `TC-005` PyInstaller build | 通过 | 修正后的 spec 成功构建到 `/tmp/crawler4j-pyinstaller-dist` |
| `TC-006` `uv run ruff check .` | 通过 | 已明确排除历史 `manual/debug/verify/analyze` 脚本 |

## 4. 重点覆盖项

| 需求/风险 | 关键场景 | 验证方式 |
|---|---|---|
| `REQ-001` / `RISK-001` | 根应用入口与打包入口一致 | root script 检查 + UI smoke + PyInstaller smoke |
| `REQ-002` / `RISK-002` | `ctrip labor_workflow` 完整路径 | 模块运行时测试 + 依赖导入验证 |
| `REQ-004` / `RISK-003` | 版本与 release 口径一致 | 元数据对照检查 |
| `NFR-003` | lint 质量门清晰 | `uv run ruff check .` 达成约定范围 |

## 5. 当前测试缺口

- 没有覆盖 `ctrip labor_workflow` 真实站点 E2E 验证
- 历史人工调试脚本仍未统一重构为正式自动化测试

## 6. 出口条件

- 模块开发者指南已经可按当前真实链路稳定复用
- `TASK-005` 已关闭，release 与质量结论可持续复用
- 默认质量门范围与文档导航规则见 `docs/05-quality/quality-gates.md`

## 7. 旧测试设计文档的承接关系

当前正式测试结论以本文件为准。旧专题测试设计继续保留为详细参考：

- `docs/05-quality/reference-tests/01-comprehensive-test-design.md`
- `docs/05-quality/reference-tests/test-01-rem.md`
- `docs/05-quality/reference-tests/test-02-tsm.md`
- `docs/05-quality/reference-tests/test-03-mms.md`
- `docs/05-quality/reference-tests/test-04-persistence.md`
- `docs/05-quality/reference-tests/test-05-sdk.md`
- `docs/05-quality/reference-tests/test-06-ui.md`

当旧测试设计与当前代码或当前验证结果冲突时，以当前代码、已验证命令和本文件为准。

## 8. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-26 | 基于当前仓库事实建立测试计划 | Codex |
| 2026-03-26 | 补充旧测试设计文档的承接关系 | Codex |
| 2026-03-26 | 补充默认 lint gate 规则，并登记 `TASK-005` 完成状态 | Codex |
