# `ctrip` 真实站点 E2E 收口方案

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 草稿  
**负责人：** 当前仓库维护者  
**主要读者：** QA | 发布负责人 | Core 维护者 | `ctrip` 模块维护者  
**上游输入：** `test-plan.md` | `acceptance-checklist.md` | `requirements-matrix.md` | 当前 `ctrip` 模块仓库事实  
**下游输出：** 真实环境验证记录 | `acceptance-checklist.md` 放行结论 | `release-notes.md` 发布结论  
**关联 ID：** `REQ-002`, `RISK-002`, `REL-003`  
**最后更新：** 2026-04-17

## 1. 目标

在不扩大范围的前提下，为 `0.2.0` 发布补齐 `ctrip` 模块真实站点 E2E 证据，关闭“本地运行链已恢复，但真实业务站点未回放”的剩余阻塞。

本次只验证三件事：

1. `ctrip` 模块可通过当前宿主正式链路被加载并执行。
2. 真实站点下 `login_workflow` 与 `labor_workflow` 至少各完成一轮可观察的成功闭环。
3. 发布侧能够拿到足够的证据判断 `0.2.0` 是否可放行，而不是继续依赖口头结论。

## 2. 前置条件

执行真实站点 E2E 前，以下条件必须同时满足：

- 宿主仓库处于待验证提交，且默认质量门已通过：
  - `uv run pytest -q`
  - `uv run ruff check .`
  - `uv run python scripts/smoke_test_ui.py`
  - Root / SDK / Contracts build
- 准备好真实 `ctrip` 模块源码或正式 ZIP 包。
- 已准备可登录的测试账号、验证码/短信配合方式、指纹浏览器/代理环境和允许的测试时段。
- 验证人能够读取宿主日志、模块日志、任务详情和运行环境状态。
- 若需要调试，仅允许走 `DevLink -> ATM 调试` 正式链路；不要重新启用已删除的旧调试脚本。

## 3. 测试对象与环境

### 3.1 宿主环境

- 仓库：`/Users/uroborus/PythonProject/crawler4j`
- 启动方式：`uv run python -m src.ui.app`
- 日志重点：
  - `crawler4j.log`
  - ATM 任务详情中的结构化状态
  - REM 环境状态变化

### 3.2 模块来源

按顺序验证两条链路，不能只跑其中一条：

1. **DevLink 链路**：用于快速暴露真实站点行为和调试问题
2. **ZIP 安装链路**：用于发布前确认正式安装方式没有偏差

推荐模块源码路径：

- `/Users/uroborus/PythonProject/ctrip_crawler`

如果实际路径不同，记录真实路径并保持全文一致。

## 4. 执行分阶段

## 4.1 Phase A: 宿主基线复验

目标：确认当前待发布宿主本身没有明显漂移，再进入真实站点回放。

必须执行：

```bash
uv sync --all-packages
uv run pytest -q
uv run ruff check .
uv run python scripts/smoke_test_ui.py
uv build --package crawler4j --out-dir /tmp/crawler4j-build-check
uv build --package crawler4j-sdk --out-dir /tmp/crawler4j-sdk-build-check
uv build --package crawler4j-contracts --out-dir /tmp/crawler4j-contracts-build-check
```

通过标准：

- 所有命令返回 `0`
- `crawler4j.log` 中没有启动阶段的新增 traceback

## 4.2 Phase B: DevLink 真实站点回放

目标：在最短反馈链路下确认真实站点登录与业务工作流都能进入正式执行链。

建议命令：

```bash
uv run python -m crawler4j_sdk.cli.commands host devlink add /Users/uroborus/PythonProject/ctrip_crawler
uv run python -m crawler4j_sdk.cli.commands host devlink list
uv run python -m src.ui.app
```

执行步骤：

1. 在宿主中确认 `ctrip` 以 DevLink 形式出现，且没有清单/升级源预检错误。
2. 用真实测试账号创建或选择可用运行环境。
3. 手动执行一次 `login_workflow`。
4. 确认以下观测点：
   - 任务状态从待执行进入执行中，再进入成功或明确失败
   - `crawler4j.log` 能看到模块 `ctx.logger` 输出
   - REM 环境状态符合当前语义：执行结束后回收到 `READY`，而不是被隐式销毁
5. 在相同真实环境下手动执行一次 `labor_workflow`。
6. 记录业务观测点：
   - 是否进入真实页面，不再 fallback 到登录
   - 是否产生预期页面跳转、关键 DOM 或业务结果
   - 是否触发验证码、短信、反爬、代理或权限异常

通过标准：

- `login_workflow` 至少成功 1 次
- `labor_workflow` 至少成功 1 次，且能给出业务闭环证据
- 若失败，必须能明确归因到模块、宿主、站点或环境中的哪一层

## 4.3 Phase C: ZIP 安装真实站点回放

目标：确认正式安装方式与 DevLink 观测结果一致，不存在“开发链通、交付链断”的情况。

建议步骤：

1. 在 `ctrip` 模块目录构建正式 ZIP。
2. 在宿主仓库执行安装预检与安装：

```bash
uv run python -m crawler4j_sdk.cli.commands host install preview <ctrip_zip>
uv run python -m crawler4j_sdk.cli.commands host install apply <ctrip_zip>
```

3. 重新打开宿主，确认模块显示为正式安装状态。
4. 至少重复以下场景各 1 次：
   - `login_workflow`
   - `labor_workflow`

通过标准：

- ZIP 预检和安装都通过
- 安装后的真实站点行为不低于 DevLink 验证结果
- 不出现“打包后缺依赖、入口漂移、升级源校验失败、工作流退化回登录”这类回归

## 5. 用例矩阵

| 用例 ID | 场景 | 来源 | 必需证据 | 结果判定 |
|---|---|---|---|---|
| `E2E-CTRIP-001` | 真实账号登录成功 | DevLink | 任务成功截图、日志、环境状态 | Pass / Fail |
| `E2E-CTRIP-002` | `labor_workflow` 真实站点成功闭环 | DevLink | 页面证据、任务结果、关键日志 | Pass / Fail |
| `E2E-CTRIP-003` | ZIP 安装预检通过 | ZIP | preview 输出 | Pass / Fail |
| `E2E-CTRIP-004` | ZIP 安装后 `login_workflow` 成功 | ZIP | 任务结果、日志、截图 | Pass / Fail |
| `E2E-CTRIP-005` | ZIP 安装后 `labor_workflow` 成功闭环 | ZIP | 页面证据、任务结果、关键日志 | Pass / Fail |

## 6. 证据清单

每个用例至少保留以下证据中的三类：

- 命令输出或宿主 UI 状态截图
- `crawler4j.log` 关键片段
- 任务详情页截图
- 运行环境状态截图
- 业务页面关键结果截图
- 若失败，失败时刻的错误堆栈或错误消息

建议把原始证据按本次批次统一放入一个目录，例如：

- `screenshots/ctrip-e2e-<date>/`

同时把最终结论回写到：

- `docs/04-project-development/07-release-delivery/acceptance-checklist.md`
- `docs/04-project-development/07-release-delivery/release-notes.md`

## 7. 失败分流规则

- **宿主问题**：入口、模块加载、任务调度、环境状态、日志链路异常
- **模块问题**：工作流逻辑、依赖、页面定位、数据解析异常
- **站点问题**：验证码、反爬、页面改版、账号权限、网络抖动
- **环境问题**：代理、指纹浏览器、短信/验证码配合、系统权限

所有失败都必须落到上述四类之一；不能只写“E2E 失败”。

## 8. 放行条件

满足以下条件后，`RISK-002` 才能从阻塞转为已验证：

- `E2E-CTRIP-001` 至 `E2E-CTRIP-005` 全部完成
- 至少有 1 次 `labor_workflow` 在真实站点成功闭环
- DevLink 与 ZIP 安装两条链路没有出现相互矛盾的结果
- 失败项若存在，已证明不属于 `0.2.0` 放行范围，且发布负责人明确接受

否则，`acceptance-checklist.md` 中的业务项继续保持“阻塞”。

## 9. 最终输出模板

执行结束后，用同一口径输出：

1. 测试批次与执行人
2. 宿主提交 / 模块提交 / 模块来源
3. 环境条件与账号范围
4. 用例矩阵结果
5. 失败归因与修复建议
6. 发布结论：`Go` / `No-Go`
