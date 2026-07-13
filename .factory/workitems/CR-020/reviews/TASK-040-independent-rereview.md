# TASK-040 独立修复复评

- Work item: `CR-020`
- Task: `TASK-040`
- Review type: Review-fix task-level Spec Review + Quality Review
- reviewer_type: `independent_subagent`
- reviewer_id: `/root/cr020_review_fast`
- reviewer_independence_evidence: 本 reviewer 未参与 TASK-040 原实现及 REV-001..006 修复；本轮只读取既有独立评审、review response、修复验证 evidence 和当前相关源/测试 diff，未读取或依赖实现者会话历史，未修改实现或测试。
- review_status: `changes_requested`
- next_gate_status: `changes_requested`
- author_self_check_score: `n/a`
- review_score: `83/100`

## REV-001..006 复核

| Feedback | 复核结论 | 依据 |
|---|---|---|
| `CR-020-REV-001` 共享生命周期锁与锁内回绑 | 部分修复，仍阻塞 | `EnvironmentManager` 已为 ensure、start、stop、recycle、destroy 提供共享 keyed lock，Service 使用 unlocked start/stop，并把 `on_ready` 回绑留在锁内；但 `pause_env()`、`resume_env()` 等同环境生命周期写操作仍绕过该锁。 |
| `CR-020-REV-002` 严格关闭状态 | 部分修复，仍阻塞 | close 已使用严格查询并同时等待旧 CDP；查询抛异常和 CDP 耗尽已有测试。但 `is_browser_running()` 在 Management API 返回 `success=false` 时仍返回 `False`，会被严格关闭路径解释为“已确认停止”。 |
| `CR-020-REV-003` Core 异常边界 | 已修复 | 持久化读取、写入和写后复核均转换为稳定 Core 异常并使用 `from None`；Client Cookie 请求不记录正文，测试覆盖异常消息与 error/warning 日志不含 Provider API、API Key 或完整 Cookie value。 |
| `CR-020-REV-004` 有效期严格比较 | 已修复 | `expires` 已改为 float 严格相等；测试覆盖 `+0.1s` 和 `+1.0s` 均不匹配。 |
| `CR-020-REV-005` 失败与空集合测试 | 部分修复 | 已新增实际清空、stop/start/runtime 失败、取消释放、外部竞争、查询异常、CDP 耗尽和日志安全测试；但未覆盖 REV-002 中 HTTP 成功而业务 `success=false` 的严格查询失败分支。 |
| `CR-020-REV-006` 锁表增长 | 已修复 | keyed lock registry 已改为 `WeakValueDictionary`；活跃持有者/等待者保留强引用，空闲锁可回收，且 int/string 同值 key 归一为同一锁。 |

## Findings

### Critical

- 无。

### Important

1. [`packages/crawler4j/src/core/rem/manager.py:948`](../../../../../packages/crawler4j/src/core/rem/manager.py) — `pause_env()` 和 `resume_env()` 仍直接读取环境并调用 `_provider_operation()`，没有获取 `get_env_lifecycle_lock(env_id)`。它们可在 Cookie ensure 的持久化、stop/start、运行态复核或回绑链路中途改变同一环境状态；这仍不满足 NFR-020-002 的“同一环境生命周期写操作互斥”，也使 REV-001 只完成了部分生命周期入口。应让这些公开生命周期写入口复用同一 keyed lock，并补与 ensure 竞争的测试。

2. [`packages/crawler4j/src/core/rem/provider.py:2048`](../../../../../packages/crawler4j/src/core/rem/provider.py) / [`packages/crawler4j/src/core/rem/provider.py:2644`](../../../../../packages/crawler4j/src/core/rem/provider.py) — 严格关闭轮询最终调用 `VirtualBrowserClient.is_browser_running()`，但 Management API 返回 HTTP 成功且 `success=false` 时，该方法返回 `False`。这不是“确认浏览器不在运行列表”，而是业务层查询失败；当前路径仍会在旧 CDP 不可达时正常继续启动，复现了 REV-002 的失败即关闭误判。严格查询必须对 `success=false`（以及不可验证的响应结构）抛异常，并增加对应测试。

### Minor

- 无。

## 评分

- 需求符合度：`24/30`
- 架构一致性：`16/20`
- 测试充分性：`15/20`
- 代码质量：`18/20`
- 文档与记忆同步：`10/10`
- review_score：`83/100`

## Verification

- 按派发要求，本 reviewer 未运行测试、格式化或其他验证命令。
- 已审阅 `.factory/workitems/CR-020/evidence/review-fix-verification.md`：文件化证据记录修复目标集 `118 passed`、REM/ATM 相邻回归 `513 passed`、完整 unit `1187 passed`、Ruff 与 `git diff --check` 通过。
- 上述证据不覆盖本复评指出的 `success=false` 严格查询分支；当前相关测试也未覆盖 pause/resume 与 ensure 的共享锁竞争。

## Gate

`changes_requested`

仍有两个 Important，不得进入 `pending_human_confirmation`。本复评只写本文件，未修改实现、测试、其他 review/evidence 或 ledger。
