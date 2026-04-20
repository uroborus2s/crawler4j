# ATM 模块资源池等待队列设计

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已确认，V1 已落地  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 模块开发者  
**上游输入：** `docs/04-project-development/02-discovery/atm-resource-pool-queue-brainstorm.md` | 当前 ATM / REM / MMS 实现 | `ctrip_crawler` 固定环境池场景  
**下游输出：** `docs/04-project-development/05-development-process/implementation-plan.md` | `docs/04-project-development/06-testing-verification/test-plan.md` | `.factory/memory/architecture.summary.md` | `.factory/memory/api.summary.md`  
**最后更新：** 2026-04-19

## 1. 设计目标

- 让固定环境池场景从“抢不到即失败”改为“等待可分配工位”。
- 让服务型作业的目标并发由“服务席位”来表达，而不是由不断失败重试的模块实例来表达。
- 保持宿主对环境生命周期、并发补位和任务终态的统一治理。
- 让模块只负责同步业务资格，不负责实现候场、轮询和叫号。

## 2. 当前问题

- ATM 在旧语义里把 `select_env -> None` 视为硬失败，适合一次性任务，不适合常驻服务。
- REM 当前只提供通用环境列表与状态，不知道“哪些环境对某个模块当前可接单”。
- 模块自己的业务表里已经有“绑定账号 -> 绑定环境”之类事实，但宿主无法直接安全复用这些私有语义。

## 3. 核心概念

### 3.1 服务席位

- 服务席位表示宿主为某个 Service Job 维持的并发目标单位。
- 一个席位要么处于运行中，要么处于等待环境中。
- `运行中 + 等待中 = 目标并发`。

### 3.2 资源池

- 资源池表示“某个模块、某一类工位”的稳定业务分组。
- 例子：`bound_account_ready`
- 对模块作者暴露的 `resource_pool` / `pool_name` 只写池名；宿主内部 metadata key 会按根模块名归一化后再拼 `<root_module>:<pool_name>`
- 当前实现的归一化规则是先取模块运行名里第一个 `.` 之前的根模块，例如 `demo.foo` 会归一成 `demo`

### 3.3 资格卡片

- 资格卡片表示“某个环境当前是否属于某个资源池，并且现在能不能接新任务”。
- 宿主只根据资格卡片和环境状态做排队补位，不读取模块私有业务表。

## 4. 宿主侧总体方案

### 4.1 队列模型

- 只有 `Service Job` 进入 `select + resource_pool` 模式后，宿主才不再把“没选到环境”视为失败。
- 宿主先补齐服务席位；拿到环境的席位进入运行，拿不到环境的席位进入等待。
- V1 仍复用底层 `TaskStatus.PENDING` 作为等待中的底层状态，但 UI 与运营口径统一展示为“等待环境”。
- 如果只是旧的 `select + selector_name`，而没有 `resource_pool`，那么当前轮没命中仍然是失败，不进入等待队列。

### 4.2 叫号与补位

- V1 固定按 FIFO 补位。
- 容量变化时，宿主按“新增可分配工位数”连续从队列头部补位。
- 宿主总是优先消化已有等待席位，再考虑是否新增新的等待席位。

### 4.3 容量变化触发源

宿主对以下事件执行资源池级调和：

- 某个运行中的任务释放环境
- 新环境创建完成并进入可分配状态
- 暂停或异常环境恢复到可分配状态
- 模块更新了某个环境的资源池资格

此外保留轻量定时巡检作为兜底，用于纠正漏事件或状态漂移。当前实现已把这条兜底链路收口为 `JobController` 挂在主 async loop 上的后台协程循环，不再复用 `APScheduler` 的 `run_coroutine_job()` / 周期 job 包装；活跃 Job 会在控制器启动时先做 bootstrap 调和，作业启动或更新时也会定向 `reconcile_job(...)`，随后 5 秒 periodic loop 再按节奏兜底。单轮巡检卡住时会通过超时取消自动恢复下一轮。

## 5. 资源池资格卡片

### 5.1 持久化位置

- 卡片存储在宿主内部 `env_metadata`
- 不进入 `core:data_table`
- 不暴露为业务数据表

### 5.2 建议的存储形态

V1 建议每个“模块 + 资源池”在单个环境上对应一条 JSON 卡片：

- `namespace = scheduler.resource_pool`
- `key = <root_module>:<pool_name>`
- `value` 为 JSON 对象，至少包含：
  - `module_name`
  - `pool_name`
  - `eligible`
  - `reason`
  - `exclusive`
  - `updated_at`

示例：

```json
{
  "module_name": "ctrip_crawler",
  "pool_name": "bound_account_ready",
  "eligible": true,
  "reason": "",
  "exclusive": true,
  "updated_at": "2026-04-19T10:20:00+08:00"
}
```

### 5.3 宿主分配条件

宿主当前通过 `EnvironmentManager.list_allocatable_envs(module_name, pool_name)` 认定“当前可分配”的条件为：

1. metadata key 命中当前模块（按宿主归一后的模块名）与当前资源池
2. 资格卡片存在且 `eligible = true`
3. `env.kind = BROWSER`
4. `env.status = READY`
5. `env.lease_id` 为空，也就是当前无租约占用

## 6. 模块与宿主的责任分工

### 6.1 模块负责

- 定义稳定资源池名
- 在业务事实变化时更新环境资格卡片
- 在需要时执行资源池全量重建/对账

### 6.2 宿主负责

- 维护等待队列
- 按 FIFO 叫号与补位
- 监听容量变化并调和
- 处理任务状态、环境租约和终态收口

## 7. 模块开发者适配面

### 7.1 SDK helper

不要求模块开发者直接调用底层 metadata API。V1 已落地的 SDK helper 为：

- `bind_resource_pool(context, *, pool_name, env_id=None, eligible=True, reason="", exclusive=True)`
- `mark_resource_pool_eligible(context, *, pool_name, env_id=None, reason="")`
- `mark_resource_pool_ineligible(context, *, pool_name, env_id=None, reason)`
- `remove_resource_pool(context, *, pool_name, env_id=None)`
- `replace_resource_pool_snapshot(context, *, pool_name, entries)`

补充口径：

- 这些 helper 都是对宿主 `env.*` 工具的异步封装，必须 `await`
- `pool_name` 只写池名，不要手写 `<module_name>:<pool_name>`
- 当前上下文没有绑定环境时，不要省略 `env_id`；`bind / eligible / ineligible / remove` 默认都会回退到 `context.env_id`
- 这里的 `env_id` 是宿主 `environments.id` 主键，不是外部浏览器 ID，也不是业务账号 ID
- `prepare_env` 阶段的 `TaskContext.env_id` 当前固定是 `0`，不应在该阶段写资源池卡片
- `replace_resource_pool_snapshot(context, *, pool_name, entries)` 的 `entries` 必须是这个资源池的完整权威列表；未出现的环境卡片会被宿主删除
- `exclusive` 当前只是随卡片持久化的元数据，V1 分配器不会依据它改变调度路径；除非模块另有对账约束，否则保持默认值即可

### 7.2 业务事件点

模块开发者只需在关键业务事件点同步卡片：

- 账号绑定完成，环境正式可复用
- 账号解绑或人工停用
- 账号封禁、黑号、风控失效
- 宿主重启后的全量对账

实现落点补充：

- 当前 `TaskContext` 已经绑定环境的 hook / task，可以省略 `env_id`
- 离线对账、宿主启动恢复或批量扫描这类没有环境上下文的逻辑，必须显式传 `env_id`，或者直接提交 `replace_resource_pool_snapshot(...)`

### 7.3 不要求模块做的事

- 不要求自己维护等待队列
- 不要求自己写轮询等待
- 不要求在环境占用时移入/移出资源池
- 不要求自己实现“目标并发 10”的补位逻辑

## 8. 占用、选择器与细粒度选择

### 8.1 占用不移池

- 环境被任务占用时，不移出资源池。
- 资源池归属是稳定业务身份，占用只是临时运行状态。
- 释放后只要卡片仍有效，环境会自动重新成为该资源池的可分配工位。

### 8.2 资源池与选择器分层

- 资源池负责“宿主只看哪一批环境”。
- 选择器负责“从当前这批候选里挑哪一个更合适”。

V1 约定：

- `resource_pool` 用于宿主级排队和容量感知
- `selector_name` 可选，用于模块侧细粒度挑选
- 如果定义了 `selector_name`，宿主只把当前资源池内可分配的候选传给它
- 如果没有定义 `selector_name`，宿主不会调用 `select_env`，而是直接取当前池里的第一个可分配候选
- 这对已有 selector 模块来说属于显式迁移动作，不是无害默认；清空 `selector_name` 就意味着接受宿主默认挑选顺序
- 当前实现没有给这个“第一个可分配候选”定义额外业务排序承诺；只有任何候选都等价时，才适合把 `selector_name` 留空
- 模块作者真正实现的是 `module_runtime.py` 里通过 `@env_selector(...)` 声明的 selector；运行时 `select_env(...)` 是框架包装壳

在新的队列模式下：

- 只有带 `resource_pool` 的路径里，选择器本轮返回“没有命中”时，才不应直接把任务判失败
- 正确语义是“保持等待，等待下一个合适工位”
- 不带 `resource_pool` 的旧选择模式里，`select_env` 返回 `None` 仍然应该直接失败

## 9. 黑号与删除环境

黑号场景统一按两步走：

1. 先停发号  
   把该环境在对应资源池下标成 `eligible = false`，并写明 `reason = blacklisted`
2. 再处理环境  
   按业务策略选择“直接销毁”或“保留待人工处理”

如果选择销毁环境：

- 模块只需要先停发号，再调用宿主销毁环境
- 当前实现沿 `EnvironmentManager.destroy_env() -> EnvPool.remove() -> DELETE FROM environments` 删除环境记录
- 因 `env_metadata.env_id -> environments.id` 配置了 `ON DELETE CASCADE`，环境删除后对应卡片会自动清理

## 10. UI 与运营口径

对固定环境池 Service Job，V1 UI 统一展示：

- 目标并发
- 当前运行
- 当前等待
- 当前资源池可分配工位数
- 容量状态（充足 / 不足）

任务级状态对外口径收敛为：

- `运行中`
- `等待环境`
- `已结束`
- `失败`

失败只用于真正异常，例如：

- 资源池配置错误
- 模块资格同步异常
- 等待超时类错误（当前实现文案为 `等待环境池工位超时: <pool> (<seconds>s)`）
- 人工停止后的终态收口

术语分层补充：

| 名称 | 当前语义 |
|---|---|
| `TaskStatus.PENDING` | 固定池等待席位复用的底层状态，不等于所有 `PENDING` 都是环境队列 |
| `等待环境` | UI / 运营层展示文案 |
| `等待环境池工位: <pool>` | 固定池等待中的 `task.message` |
| `等待环境池工位超时: <pool> (<seconds>s)` | 固定池等待超时后的失败错误 |

## 11. V1 边界

### 11.1 本轮明确包含

- 资源池资格卡片
- 宿主等待队列
- FIFO 补位
- 容量变化事件触发补位
- 控制器在主 async loop 上运行的轻量定时巡检兜底（带单轮超时收口）
- 黑号先停发号再销毁的规则

### 11.2 本轮明确不做

- 优先级队列、多租户抢占策略
- 模块自己实现等待轮询
- 把卡片暴露成业务数据表
- 在通用 `Environment` 上新增强绑定 `module_id`

### 11.3 当前已落地补充

- `wait_timeout` 已同时用于已选中环境后的租约获取，以及固定环境池 `PENDING` 等待席位自动超时收口。
- 当前实现不会单独用 `wait_timeout` 中断 `select_env(...)` 本身；慢选择逻辑会占用整体调度时间，但没有独立 selector 超时。
- 固定池等待从任务第一次进入等待席位并写入 `waiting_since` 时开始计时；`wait_timeout = 0` 时当前不会自动超时收口。
- 当前实现的失败文案为 `等待环境池工位超时: <pool> (<seconds>s)`，语义已从“环境选择返回 none”收敛为等待超时类错误。
- 固定池只把 `eligible=true`、`READY` 且 `lease_id` 为空的环境视为可发号工位；`KEEP_ALIVE` 留下的 `RUNNING` 环境不会自动回池复用。
- 如果候选环境在 `get_env` / 租约阶段被其他任务先抢走，当前任务会回到等待席位并保留原 `waiting_since`，而不是直接记失败。

## 12. 验收口径

- 目标并发 10、可用工位 2 时，系统稳定表现为“运行中 2、等待中 8”
- 容量从 2 增长到 5 时，系统一次性补位 3 个，表现为“运行中 5、等待中 5”
- 环境释放后，宿主优先消化已有等待席位，不制造新的假失败
- 黑号环境不会在销毁前继续被新任务叫号
- 环境删除后，对应资格卡片自动消失
