# 构建模块

这一页讲模块代码应该怎么写。

如果你只想记一条规则，记这个:

- 一个 task 做一个原子业务动作
- 一个 workflow 做流程编排
- 相同逻辑先抽到 task；task 内部若还有真实重复，再抽一层纯函数

## 开发顺序

推荐始终按这个顺序开发:

1. 用 CLI 生成骨架
2. 写 task
3. 写 workflow
4. 补 `module.yaml`
5. 跑 `uv run crawler4j check full`
6. 进入 DevLink / ATM 调试

## 写 TaskScript

`TaskScript` 是模块里的最小原子业务单元。

一个动作满足下面任意条件，就应该是 task:

- 可以单独调试
- 可以被多个 workflow 复用
- 本质上只做一个原子业务动作

例如:

- 登录
- 打开目标页
- 抓取一页列表
- 提交一个表单

### task 的合同

一个 task 只做三件事:

1. 读取必要配置和运行态
2. 完成一个原子业务动作
3. 返回一个清晰结果

一旦出现下面任意一种情况，就应该上升到 workflow:

- 第二个业务阶段
- 明显的阶段切换
- 多页循环
- 状态机
- 多次重试编排

### 最小写法

```python
from crawler4j_sdk import TaskContext, TaskResult, TaskScript


class FetchHotelsTask(TaskScript):
    name = "fetch_hotels"
    display_name = "抓取酒店列表"
    description = "抓取当前城市酒店列表"

    async def execute(self, ctx: TaskContext) -> TaskResult:
        if not ctx.page:
            return TaskResult.fail(
                message="当前环境没有可用 Page",
                error="page_not_available",
            )

        city = ctx.get_config("city", "shanghai")
        await ctx.page.goto(f"https://example.com/hotels?city={city}")
        records = [{"id": "hotel-001", "name": "示例酒店", "city": city}]
        return TaskResult.ok(
            message="抓取完成",
            data={"records": records},
        )
```

### task 类属性约定

| 属性 | 是否必须 | 说明 |
|---|---|---|
| `name` | 是 | 稳定的 `snake_case` 标识 |
| `display_name` | 建议 | UI 和日志展示名 |
| `description` | 建议 | 一句话说明 |
| `default_config` | 可选 | task 层局部默认值说明 |

## 写 Workflow

`TaskFlow` 负责业务流程编排。

workflow 只负责:

- 顺序
- 分支
- 循环
- 停止判断
- 阶段切换

workflow 不负责:

- 页面细节
- 大量字段解析
- 第二套调度框架

### 最小写法

```python
from crawler4j_sdk import TaskContext, TaskFlow, TaskResult


class HotelSyncWorkflow(TaskFlow):
    name = "hotel_sync"
    display_name = "酒店同步"
    description = "同步酒店列表"

    async def run(self, ctx: TaskContext):
        ctx.state["phase"] = "fetch_hotels"
        payload = await ctx.run_subtask("fetch_hotels")
        if payload is False:
            return TaskResult.fail(
                message="fetch_hotels 执行失败",
                error="fetch_hotels_failed",
            )
        records = payload.get("records", []) if isinstance(payload, dict) else []
        return {"records": records}
```

### `ctx.run_subtask(...)` 的真实语义

```python
payload = await ctx.run_subtask("fetch_hotels", page_no=1)
```

它会:

1. 先把 `kwargs` 合并进 `ctx.state`
2. 再调用目标 task
3. 优先返回 `TaskResult.data`
4. 如果没有 `data`，返回布尔成功语义

所以:

- 子任务返回 `TaskResult.ok(data={"records": records})` -> 你拿到 `{"records": records}`
- 子任务返回 `TaskResult.ok()` -> 你拿到 `True`
- 子任务返回 `TaskResult.fail(...)` -> 你拿到 `False`

workflow 里的硬规则:

- 不允许把 `False` 静默降级成空列表、空字典或“成功但无数据”
- 只要子任务失败，就必须显式返回 `TaskResult.fail(...)`、发出 `TaskSignal`，或直接抛异常

## 当前快照和历史轨迹分开写

如果同一条业务既要更新“现在的结果”，又要保留“发生过什么”，把两件事分开:

- 当前可展示状态继续维护成 snapshot dataset
- 历史轨迹只走宿主提供的审计通道

不要把历史事件塞进 `ctx.state`，也不要把 data table handler 当成记录审计历史的主入口。

### `kwargs` 只能传少量控制参数

正确用法:

- `page_no=1`
- `force_refresh=True`
- `phase="detail"`

错误用法:

- 把大列表对象塞进去
- 把业务实体对象在多个 task 之间来回传
- 用它替代明确的返回值

## 结果怎么返回

按这个决策表选:

| 场景 | 正确做法 |
|---|---|
| 正常完成业务动作 | `return TaskResult.ok(...)` |
| 业务预期内失败，比如登录失败、没数据、账号不可用 | `return TaskResult.fail(...)` |
| 需要让宿主等待确认、取消、明确销毁环境 | 在 `TaskResult` 里带 `signal=TaskSignal.*(...)` |
| 代码写错、第三方库异常、你根本不知道怎么恢复 | 直接抛异常 |

## 代码风格和抽象边界

允许存在的业务层只有:

1. `workflows/`
2. `tasks/`
3. `utils/` 里的纯函数
4. `module_runtime.py` 里的薄 hook
5. `ui/` 里的页面类

命中下面任意一项，这个模块就应视为不合格，必须回退重构:

- 新增 `services/`、`repositories/`、`controllers/`、`stores/`、`managers/`、`clients/`、`facades/`、`adapters/`
- 新增 `BaseTask`、`BaseWorkflow`、`AbstractClient`、`ContextFacade`、`DbClient` 这类包宿主能力的抽象层
- 在 `module_runtime.py` 写主要业务流程、批量循环、复杂数据转换
- 在 workflow 里塞大量页面细节和字段解析
- 在 task / workflow / UI 里直接操作宿主内部数据库或 ORM

代码评审时可以直接按下面两条判定:

```bash
rg --files tasks workflows ui utils
rg -n "(service|repository|controller|store|manager|client|facade|adapter|BaseTask|BaseWorkflow|AbstractClient|ContextFacade|DbClient)" __init__.py module_runtime.py tasks workflows ui utils
```

如果第二条命中的是你自建的业务抽象，而不是第三方库名称，默认判不通过。

### `module_runtime.py` 的边界

它只做:

- 根装配需要的薄扩展
- 生命周期 hook
- `declare_ui`
- 很薄的同步 data table handler

### `on_cleanup` 该怎么理解

`on_cleanup` 是任务结束前的最后一个模块级清理 hook。

你现在应该按下面的事实写它:

- 只会调用当前任务对应的 `hooks_module.on_cleanup(...)`
- 不会把所有模块的 cleanup 都调一遍
- 对已经进入模块执行阶段的任务，`on_cleanup` 会先执行，再由宿主关闭或删除环境
- 如果任务还没真正进入模块执行，只是在环境申请/启动阶段就失败或被中止，不保证会调用 `on_cleanup`

这意味着:

- 需要依赖 `ctx.page`、`ctx.context`、已登录态或页面内按钮/接口做收尾时，把逻辑放在 `on_cleanup`
- 不要假设 cleanup 执行时环境已经被宿主关掉
- 不要在 cleanup 里再实现第二套环境回收逻辑；真正的关环境 / 删环境仍由宿主负责

`on_cleanup` 的硬约束:

- 要幂等。重复执行一次不能把数据清坏
- 要尽快返回。不要在里面做无限等待
- 手动中止时，宿主会主动 cancel 正在执行的模块协程；如果你的代码在 `ctx.wait()` 或 `ctx.run_subtask()` 上挂起，它们会提前抛 `asyncio.CancelledError`
- 需要长流程提前退出时，平时仍应在 task / workflow 主链路主动检查 `ctx.should_stop()`，不要把 stop 处理只押在 cleanup
- 如果需要根据宿主最终动作做分支，只能读取宿主已经放进 `ctx.runtime` 的运行态，不要自己猜

不要做:

- 主要业务流程
- 大段页面操作
- 自建 service / repository / facade

## 开发完成后的最小自检

改完一批代码后，至少问自己:

- 这个逻辑应该在 workflow 还是 task
- 这里是不是又造了一层宿主已经给的能力
- 这里的数据应该进 `ctx.state` 还是 `db.*`
- 这个 helper 是真实复用，还是为了看起来“更架构”
- 新人第一次看能不能顺着目录和名字理解代码

然后跑:

```bash
uv run crawler4j check full
```

想继续做页面和托管数据表，接着看 [UI 与数据表](ui-and-data-table.md)。
