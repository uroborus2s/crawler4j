# ATM 环境候选等待队列设计

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 架构 | 开发 | QA | 模块开发者
**最后更新：** 2026-04-30

> 文件名保留历史路径，正文已按 0.4.0 正式方案改为环境候选纯函数。固定资源池、资格卡片和同步快照方案不再是当前分支契约。

## 1. 目标

- Service Job 在候选环境暂时不可用时进入等待，而不是失败重试。
- 模块开发者只写一个同步纯函数，不维护宿主资源池同步流程。
- 账号状态、黑号、注册时间、会员等级等业务过滤都由模块自己的数据表和候选函数实时决定。
- 宿主继续负责 FIFO 等待、容量补位、租约治理和终态收口。

## 2. 术语

### 环境候选函数

环境候选函数位于 `candidates/*.py`，使用 `@env_candidates(name=...)` 声明。

```python
from crawler4j_contracts import EnvCandidates, TaskContext, env_candidates

@env_candidates(name="ready_accounts", label="可用账号")
def ready_accounts(ctx: TaskContext) -> EnvCandidates:
    return (
        EnvCandidates.from_table("accounts")
        .filter(status="ready", blacklisted=False)
        .order("last_used_at")
        .limit(20)
    )
```

函数必须是同步纯函数。它可以返回：

- `list[int]`、`tuple[int]` 或 `set[int]`
- `EnvCandidates` 链式查询对象

### 候选 DSL

`EnvCandidates` 支持组合：

- `filter()`
- `exclude()`
- `intersect()`
- `union()`
- `minus()`
- `order()` / `order_by()`
- `limit()`
- `list(ctx)`

每个函数既可以直接返回，也可以被其他候选函数组合复用。

## 3. 进入等待队列的条件

只有同时满足以下条件时，ATM 才启用候选等待队列：

- `JobType.SERVICE`
- `AcquisitionConfig.mode = select`
- `AcquisitionConfig.candidates` 非空
- 未指定固定 `env_id`

固定 `env_id` 任务直接派发。没有 `env_id` 也没有 `candidates` 的 select 模式配置非法。

## 4. 宿主调度流程

1. 读取运行模板里的候选函数名和 `candidate_params`。
2. 从 MMS descriptor 校验该候选函数已声明。
3. 在只读 `ctx.db`、无工具面的候选运行面执行同步纯函数。
4. 将返回值归一为 env id 列表。
5. 按返回顺序过滤 `READY + BROWSER + 无租约` 环境。
6. 取得租约后再次执行候选函数，确认被租约环境仍在候选集合中。
7. 若仍有效，启动任务；若已失效或被抢占，回到等待席位。

候选函数异常属于配置或业务代码错误，任务失败收口；候选为空属于正常容量不足，Service Job 进入等待。

## 5. 模块开发者职责

模块开发者只维护模块自己的业务数据和候选纯函数。

- 新增账号：写入模块账号表，下一轮候选求值自然可见。
- 黑号：更新账号表状态，例如 `blacklisted=true` 或 `status="blocked"`。
- 会员等级变化：更新账号表字段，例如 `member_tier`。
- 注册时间策略：在候选函数中用 `registered_at` 或派生字段过滤。
- 多策略组合：拆分多个纯函数，使用 `EnvCandidates.intersect()` / `union()` / `minus()` 组合。

模块不需要，也不允许，同步一份宿主资源池快照。

## 6. 宿主职责

- 维护 Service Job 的等待席位。
- 保证等待口径为 `运行中 + 等待中 = 目标并发`。
- 在环境释放、环境变为 READY、作业激活/更新和轻量巡检时重新计算容量。
- 执行租约前后两次候选校验，避免候选在竞争中变脏。
- 将候选运行面限制为只读数据库访问，不暴露环境、文件、网络或资源修改工具。

## 7. 运行模板字段

```yaml
resource:
  acquisition:
    mode: select
    candidates: ready_accounts
    candidate_params:
      min_member_days: 90
      tier: gold
    wait_timeout: 60
```

运行模板 UI 的选择环境模式直接展示候选函数下拉框，并提供“候选参数”配置窗口；窗口内容按 YAML 对象保存到 `candidate_params`，空白内容保存为空字典，调度和调试会话都会从运行模板透传该字典。

已移除字段：

- `selector_name`
- `env_selector`
- `resource_pool`

这些字段出现在运行模板时必须直接报错，不做兼容转换。

## 8. 状态文案

| 场景 | 文案 |
|---|---|
| 等待候选可用 | `等待环境候选可用: <candidates>` |
| 等待候选超时 | `等待环境候选超时: <candidates> (<seconds>s)` |
| 候选未声明 | `env_candidates 未声明: <module>.<candidates>` |

## 9. 设计结论

- 0.4.0 环境选择只有一条模块开发路径：`candidates/*.py` + `@env_candidates` 同步纯函数。
- Core 资源池能力不再对模块暴露，相关 helper、UI 列、事件和 manifest 字段都应删除。
- 业务状态的实时性来自模块数据库事实源和纯函数实时求值，不来自同步或物化快照。

## 10. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-30 | 从固定资源池等待队列改为环境候选纯函数等待队列，删除同步快照和资格卡片方案 | Codex |
