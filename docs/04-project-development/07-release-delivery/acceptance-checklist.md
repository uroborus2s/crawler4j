# 验收检查清单

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 草稿
**负责人：** 当前仓库维护者
**主要读者：** 发布负责人 | QA | Tech Lead
**上游输入：** `version-governance.md` | `release-notes.md` | `docs/04-project-development/06-testing-verification/test-plan.md` | `docs/04-project-development/08-operations-maintenance/deployment-guide.md`
**下游输出：** `delivery-package.md` | 发布决策 | `docs/04-project-development/08-operations-maintenance/operations-runbook.md`
**关联 ID：** `REL-003`, `REL-004`, `TASK-017`, `REQ-009`, `NFR-003`
**最后更新：** 2026-04-20

## 1. 使用范围

本清单用于判断“当前工作区是否可以进入正式发布或交付阶段”。它不是测试计划的替代，而是发布前的最终 Gate。

## 2. 发布前最小检查项

| 类别 | 检查项 | 证据 | 当前基线状态 |
|---|---|---|---|
| 版本 | `packages/crawler4j/pyproject.toml` 与发布目标版本一致，运行时版本服务可正确读取 | `version-governance.md` | 已具备（2026-04-19 复验；当前为 `0.2.0`） |
| 版本 | 当前工作区版本、最近正式 tag、SDK/Contracts 版本口径清楚 | `release-notes.md` | 已具备 |
| 测试 | `uv run pytest -q` 通过 | `test-plan.md` | 已具备（2026-04-20 复验为 `485 passed`） |
| 测试 | `uv run ruff check .` 通过 | `test-plan.md` | 已具备（2026-04-20 复验通过） |
| 运行 | `uv run python scripts/smoke_test_ui.py` 通过 | `test-plan.md` | 已具备（2026-04-20 复验通过） |
| 构建 | Root / SDK / Contracts build 通过 | `test-plan.md` | 已具备（2026-04-20 复验通过） |
| 构建 | 桌面客户端下载包（macOS / Windows）齐备 | `delivery-package.md` | 阻塞（2026-04-20 已本地复验 macOS PyInstaller bundle；Windows 打包链与正式产物仍缺失） |
| 业务 | `ctrip` 真实站点 E2E 完成并记录结果 | `ctrip-real-site-e2e-closeout.md` + 真实环境验证记录 | 阻塞（当前只补齐了 DevLink 活跃事实、fresh ZIP 预检与历史登录日志，仍未完成本轮 DevLink + ZIP 双链真实站点闭环） |
| 业务 | 若本次批次包含固定环境池 Service Job 队列能力，则已验证“运行中 / 等待中”口径、FIFO 补位、容量扩张补位、资源池隔离、等待超时收口和黑号停发号 | `test-plan.md` + 对应测试记录 | 已具备（当前 HEAD 已纳入 `TASK-023` / `REQ-009` 变更，`TC-026` / `TC-027` 本地回归已完成；正式切版时仍需把这组证据绑定到发布批次） |
| 文档 | 根导航、文档索引、memory 映射同步完成 | `docs/index.md`、`document-index.md`、`.factory/memory/doc-map.md` | 已具备 |
| 运维 | 部署说明、运行手册、管理员指南可独立阅读 | `deployment-guide.md`、`operations-runbook.md`、`admin-guide.md` | 已具备 |
| 交付 | 交付包内容、签收对象和阻塞项清楚 | `delivery-package.md` | 待正式发布 |

## 3. 放行规则

- 有任何一项标记为“阻塞”，不得进入正式发布。
- 标记为“待正式切版”或“待正式发布”的项，只有在本次发布确实覆盖对应动作时才能关闭。
- 如果本次只是内部验证或文档收口，可记录为“未触发发布”，但不能伪装成已放行。

## 4. 当前阻塞项

1. `ctrip` 真实站点 E2E 仍未按 `ctrip-real-site-e2e-closeout.md` 完成本轮 DevLink + ZIP 双链回放并留证；当前只复验了 DevLink 活跃状态、fresh ZIP 预检和历史真实登录日志。
2. `0.2.0` 对应的 Git tag 与正式 release 资产尚未执行。
3. 交付包还没有绑定具体发布批次。
4. 当前仅本地生成了 macOS PyInstaller bundle，仓内尚无 Windows 桌面包的打包链、正式产物或下载地址。

## 5. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-20 | 追加本轮最终 gate 结论：`485 passed`、lint、UI smoke、三包构建与 macOS PyInstaller bundle 已复验，但 `ctrip` 真站 E2E、tag/release、交付批次与 Windows 桌面包仍阻塞，结论继续保持 `No-Go` | Codex |
| 2026-04-20 | 修正 `REQ-009` 发布 gate 触发状态：当前 HEAD 已包含固定环境池队列能力，正式 release 时必须把 `TC-026` / `TC-027` 证据与发布批次绑定 | Codex |
| 2026-04-19 | 补记 `REQ-009` 的条件式发布 gate：若本次批次包含固定环境池 Service Job 队列能力，则必须补齐等待队列、FIFO 补位、资源池隔离与黑号停发号验证 | Codex |
| 2026-04-19 | 追加本轮 fresh gate 结论：版本服务、全量测试、lint、UI smoke、三包构建、DevLink 活跃状态与 fresh ZIP 预检已复验，但真实站点 E2E、tag/release 与交付批次仍阻塞，因此结论保持 `No-Go` | Codex |
| 2026-04-02 | 新增正式验收检查清单，并登记当前基线状态 | Codex |
| 2026-04-17 | 按 `0.2.0` 发布基线修正版本检查项，明确当前剩余阻塞已转为 Git tag / 交付批次与真实站点 E2E | Codex |
