# TASK-040 独立评审

- Work item: `CR-020`
- Task: `TASK-040`
- Review type: Task-level Spec Review + Quality Review
- reviewer_type: `independent_subagent`
- reviewer_id: `/root/cr020_independent_review`
- reviewer_independence_evidence: 本 reviewer 未参与 TASK-040 的需求确认、设计或实现；未读取或依赖实现者会话历史，仅依据 `TASK-040-review-input.md` 所列文件化输入、当前 CR-020 相关源/测试/文档/memory diff 与未跟踪源/测试文件进行评审。
- review_status: `changes_requested`
- next_gate_status: `changes_requested`
- author_self_check_score: `n/a`
- review_score: `66/100`

## Spec Review

已确认满足或基本满足：

- `env.cookie.ensure` 仅列入 full runtime surface；其他 surface 的精确 allowlist 不包含该工具。
- 公开调用字段、四个必需 bool、当前 `TaskContext.env_id` 限制、全量集合长度比较、额外 Cookie 判为不匹配、VirtualBrowser 顶层 `cookies` 写入、`data[]` 回读及 `expires <-> expirationDate` 映射均已实现。
- 发生成功的 stop/start 后，ATM 会取得当前 `BrowserHandle.page/context` 并重新 bind tools；没有向结果返回 Browser、Context、Page 或 Cookie value。
- 修改文件均位于 TASK-040 允许范围；开发文档、API 设计和 memory 已同步。

未满足的阻塞项见 Important：同环境生命周期原子锁没有成为共享锁，严格关闭检查会把 Provider 查询失败误判为已关闭，Provider API 名称会通过异常暴露给模块，且有效期比较不是完整集合的严格比较。

## Quality Review

### Critical

- 无。

### Important

1. [`packages/crawler4j/src/core/rem/cookie_service.py:201`](../../../../../packages/crawler4j/src/core/rem/cookie_service.py) / [`packages/crawler4j/src/core/atm/runtime_capabilities.py:500`](../../../../../packages/crawler4j/src/core/atm/runtime_capabilities.py) — `EnvCookieService` 的按环境锁只被 `ensure()` 自己使用；`EnvironmentManager.stop_env/start_env` 和 Provider 的其他生命周期写操作不获取该锁，而且 TaskContext/page/context/tools 回绑发生在 `manager.ensure_cookies()` 释放锁之后。并发 ensure 虽可串行进入 Service，但外部 stop/start 可穿插 read/write/stop/start/verify，后一个 ensure 也可在前一个调用回绑之前换代 handle。该实现不满足 NFR-020-002 及 API-022 所声明的“完整原子链”，存在把后续代 BrowserHandle 回绑给先前调用、或在交叉生命周期操作后错误成功的风险。应由 REM/Manager 持有并共享同 env 生命周期锁，并把稳定 handle/generation 的取得与 TaskContext 回绑纳入同一原子边界。

2. [`packages/crawler4j/src/core/rem/provider.py:2638`](../../../../../packages/crawler4j/src/core/rem/provider.py) / [`packages/crawler4j/src/core/rem/provider.py:2866`](../../../../../packages/crawler4j/src/core/rem/provider.py) — `_wait_until_window_closed()` 依赖 `_is_window_open_unlocked()`，但后者捕获所有 Management API 异常并返回 `False`。因此运行列表查询失败时，只要 CDP 端口也不可达，就会被当作“旧运行态和 CDP 均已关闭”并正常继续启动，违反严格 stop/wait 失败必须抛异常的契约。严格关闭路径必须区分“确认未运行”和“无法确认”，并为查询异常、持续运行、CDP 持续可达三类失败补测试。

3. [`packages/crawler4j/src/core/rem/provider.py:1943`](../../../../../packages/crawler4j/src/core/rem/provider.py) / [`packages/crawler4j/src/core/rem/provider.py:2006`](../../../../../packages/crawler4j/src/core/rem/provider.py) — `get_cookies()` / `replace_cookies()` 的异常直接包含 `VirtualBrowser getCookie`、`VirtualBrowser updateCookie`，`EnvCookieService` 又不做供应商无关的异常转换，模块调用 `env.cookie.ensure` 时可以直接观察到被需求明确禁止暴露的 Provider API。应在 REM 边界转换为不含供应商 endpoint 名称和敏感正文的稳定 Core 异常；测试同时断言异常与日志不包含 Provider API、API Key 和完整 Cookie value。

4. [`packages/crawler4j/src/core/rem/cookie_service.py:136`](../../../../../packages/crawler4j/src/core/rem/cookie_service.py) — 有效期允许最多 1 秒差异仍判为集合一致，可能跳过全量写入/重启。需求要求完整目标集合严格覆盖有效期，实机证据也表明 `expirationDate` 可原值保留带小数的 Unix seconds，没有文件化依据支持该容差。应定义并文档化可接受的规范化规则，或按当前契约严格比较，并增加亚秒及恰好 1 秒差异测试。

5. [`packages/crawler4j/tests/unit/test_core/test_rem/test_env_cookie_service.py:113`](../../../../../packages/crawler4j/tests/unit/test_core/test_rem/test_env_cookie_service.py) / [`packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py:1094`](../../../../../packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py) — 验收矩阵仍有阻塞性缺口：空集合只测 comparator，未证明 ensure 会执行清空、复核和必要重启；没有 stop/start/connect/运行态不匹配失败测试；没有取消后的锁释放、与其他生命周期操作竞争、管理 API 轮询异常/耗尽测试；安全测试也未捕获日志。当前 `107 passed` 不能覆盖 AC-020-004/007/008 与 NFR-020-002 的关键失败语义。

### Minor

1. [`packages/crawler4j/src/core/rem/cookie_service.py:161`](../../../../../packages/crawler4j/src/core/rem/cookie_service.py) — `_locks` 对每个见过的 env_id 永久保留锁对象，环境长期创建/销毁时会无界增长。可在无 waiter 且调用结束后清理，或由环境生命周期 owner 管理锁表；若按 Important 1 改为 Manager 共享锁，可一并解决。

## N/A 审查

- UI：接受 N/A。本任务没有 UI 入口或 UI schema 变更，工具仅属于运行时 full surface。
- SDK/Contracts：接受 N/A。现有 `TaskContext.tools.call` 与 `bind_task_context` 足以表达本次能力，没有新增 scanner、manifest 或类型契约的必要。
- 其他 Provider：接受 N/A。需求范围仅要求 VirtualBrowser；`BaseProvider` 默认显式抛出不支持，未伪装成功。

## 评分

- 需求符合度：`18/30`
- 架构一致性：`12/20`
- 测试充分性：`10/20`
- 代码质量：`17/20`
- 文档与记忆同步：`9/10`
- review_score：`66/100`

扣分主要来自原子锁 owner、严格关闭判定、Provider 异常边界及关键失败/并发测试缺口；文档已同步，但其中“原子”“严格”“不暴露 Provider API”的表述目前超出实际实现。

## Verification

- `PYTHONDONTWRITEBYTECODE=1 uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_env_cookie_service.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py -q -p no:cacheprovider`：exit code `0`，`107 passed in 2.61s`。
- `PYTHONDONTWRITEBYTECODE=1 uv run ruff check packages/crawler4j/src/core/rem packages/crawler4j/src/core/atm/runtime_capabilities.py packages/crawler4j/tests/unit/test_core/test_rem packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py`：exit code `0`，`All checks passed!`。
- `git diff --check`：exit code `0`，无输出。
- 实现方文件化证据记录完整 unit 为 `1176 passed`；本 reviewer 未重复执行完整 unit。

## Gate

`changes_requested`

存在 Important，按 rubric 不得进入 `pending_human_confirmation`。修复后需重新组织独立 task review；本评审不修改实现、测试、需求、报告或 ledger。
