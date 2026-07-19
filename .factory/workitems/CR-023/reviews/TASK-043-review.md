# TASK-043 独立评审

- Work item: `CR-023`
- Task: `TASK-043`
- reviewer_type: `independent_subagent`
- reviewer_id: `/root/cr023_independent_review`
- reviewer_independence_evidence: reviewer 未参与 TASK-043 的需求、计划或实现；未读取实现者会话历史，仅读取任务简报、实现报告、验证证据、独立评审输入、brief、plan、ledger、当前 `git diff HEAD`、新增未跟踪代码/测试及相关正式 docs/memory。
- review_status: `approved`
- next_gate_status: `pending_human_confirmation`
- author_self_check_score: `n/a`
- review_score: `94 / 100`

## Inputs

- `.factory/workitems/CR-023/task-briefs/TASK-043.md`
- `.factory/workitems/CR-023/reports/TASK-043.md`
- `.factory/workitems/CR-023/evidence/TASK-043.md`
- `.factory/workitems/CR-023/reviews/TASK-043-review-input.md`
- `.factory/workitems/CR-023/brief.md`
- `.factory/workitems/CR-023/plan.md`
- `.factory/workitems/CR-023/ledger.jsonl`
- 当前 tracked diff、untracked `http_tools.py` / `http_runtime.py` / 两组新增测试，以及相关正式 docs/memory

## Spec Review

- `REQ-014` / `AC-023-001` / `AC-023-004`：满足。`http.request` 只进入 full surface，标记为 async；公开输入输出不泄漏第三方类型；实现保留有序 headers/raw body，固定 `trust_env=False`，支持显式 proxy，并在 `require_http2=True` 时拒绝非 HTTP/2 响应。pyproject、lock、wheel 依赖事实与 PyInstaller hidden imports/metadata 配置一致。
- `REQ-015` / `AC-023-002` / `AC-023-003`：当前任务范围满足。源码、隔离 wheel 与 macOS arm64 冻结入口证据均复用 `verify_host_http_runtime()`；入口在 updater、数据库和 GUI 初始化前短路，异常不被降级为成功。
- `REQ-016` / `AC-023-005`~`AC-023-007`：满足。既有 ZIP 安装边界未扩展为依赖安装器；正式文档明确模块不得直接 import/install `httpx/h2/brotli`，并保留 manifest capability/version negotiation 后续项。
- `AC-023-008`：未伪造完成。实现报告、正式 docs 与 memory 均明确 `ctrip_crawler` 外部接线和真实房型 E2E 尚未完成。
- Scope：未发现修改禁止范围、HTTP/1.1 回退、异常吞噬或模块依赖安装器。

## Quality Review

- 分层一致：Module → `ctx.tools` → Core ATM HTTP 实现 → 宿主依赖；发布诊断留在 Core system，桌面入口只负责早分派。
- 实现保持小而直接；没有新增通用依赖系统或不必要抽象。
- 定向测试覆盖 surface、async 标记、raw body、proxy/trust_env、HTTP/2 降级、非法 URL/参数、宿主运行时、入口顺序和打包配置。
- wheel 与 macOS 冻结 smoke 的首轮 metadata 失败、修复及复建结果均有文件化 RED/GREEN 证据；Windows 与外部业务 E2E 被准确列为残余 gate。

## Findings

### Critical

- none

### Important

- none

### Minor

- [`packages/crawler4j/tests/unit/test_core/test_atm/test_http_tools.py:71`] 请求侧样例使用的 header 名称互不重复；重复项断言实际只覆盖响应 headers（第 84–88 行），且没有执行一次真实 Brotli 解码路径。实现本身使用 `httpx.Request` 和 `response.aread()`，当前运行时/打包证据也证明依赖可用，因此不阻塞本次评审；建议补充重复请求头与 `Content-Encoding: br` 回归，避免后续 transport 重构削弱 `AC-023-001`。
- [`docs/04-project-development/07-release-delivery/release-notes.md:45`] 当前 0.4.40 证据表仍记录旧的 `1235 passed + 13` 基线；`acceptance-checklist.md:22`、`.factory/memory/current-state.md:12`、`.factory/memory/runtime-brief.md:14`、`.factory/memory/tasks.summary.md:7` 和 `.factory/memory/release.summary.md:16` 也仍把已完成的全量门禁写为待执行或保留旧结果。ledger、TASK evidence、test plan 与 `.factory/project.json` 已记录 `1258 passed`，故不影响本次代码/验证结论，但应在人工确认或提交前统一当前事实，避免恢复和发布判断漂移。

## N/A 与偏离审查

- UI 设计/可见界面 `N/A`：接受。该能力是无界面诊断参数，并已在 QApplication/数据库初始化前返回；不需要新增 UI。
- Windows 冻结 runtime smoke：接受为目标平台后续 gate，仅覆盖 Windows 发布物，不扩大当前 macOS 构建证据；不得据本评审声明 Windows 已通过。
- 外部 `ctrip_crawler` 改接与真实 DevLink/ZIP 房型 E2E：接受为外部仓库后续 gate；本评审只批准 crawler4j 宿主切片，不批准业务 E2E 完成。

## Verification

- `.venv/bin/pytest ...test_http_tools.py ...test_runtime_capabilities.py ...test_http_runtime.py ...test_app.py ...test_packaging_config.py ...test_external_module_install.py -q -p no:cacheprovider`：`145 passed in 1.17s`，exit code 0。
- `.venv/bin/ruff check`（TASK-043 相关实现和测试）：`All checks passed!`，exit code 0。
- `git diff --check` + `.venv/bin/python -m json.tool .factory/project.json`：exit code 0。
- 文件化发布证据：全量 unit `1258 passed`、wheel 隔离安装与 macOS frozen runtime `http2_client=ok`；本 reviewer 未重复运行全量测试或重新构建发布物。

## Score

- 需求符合度：`29 / 30`
- 架构一致性：`20 / 20`
- 测试充分性：`18 / 20`
- 代码质量：`19 / 20`
- 文档与记忆同步：`8 / 10`
- 总分：`94 / 100`

## Gate

`pending_human_confirmation`

`approved` 仅表示独立 reviewer 通过，不等于人工确认，不得把 TASK-043 标记为 `done`。
