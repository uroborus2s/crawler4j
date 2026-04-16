# 4.5 Core 注入能力 API 参考 (SDK 1.2.0)

本页提供 `TaskContext.tools` 的完整 API 参考。这是模块与宿主 (Core) 交互的唯一官方扩展通道。

## 1. `ctx.tools` (ToolsCapability)

| 方法 | 说明 |
|---|---|
| `has_tool(name)` | 检查某个工具是否存在 |
| `list_tools()` | 列出当前可用工具元数据；每项都是 `ToolSpec(name, description, is_async)` |
| `call(name, **kwargs)` | 调用 Core 工具；异步工具返回 awaitable，需要 `await` |

---

## 2. `db.*`

### 数据集操作

| 工具名 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `db.list_records` | `dataset: str` | `list[dict]` | 读取名为 `dataset` 的数据集。 |
| `db.replace_records` | `dataset: str, records: list[dict]` | `bool` | 全量覆盖数据集内容。 |

### 状态管理

| 工具名 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `db.get_state` | `key: str` | `Any` | 读取键值。 |
| `db.set_state` | `key: str, value: Any, ttl: int?` | `bool` | 写入键值，可设置过期秒数。 |
| `db.exists_state` | `key: str` | `bool` | 判断键是否存在。 |

### 幂等锁

| 工具名 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `db.acquire_lock` | `scope: str, key: str, ttl: int, owner: dict?` | `bool` | 获取互斥锁。 |
| `db.release_lock` | `scope: str, key: str` | `bool` | 释放锁。 |
| `db.is_locked` | `scope: str, key: str` | `bool` | 查询锁状态。 |

---

## 3. `ip_pool.*`

| 工具名 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `ip_pool.pick_proxy` | `criteria: dict?` | `dict?` | 获取代理信息。 |

---

## 4. `env.*`

| 工具名 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `env.set_proxy` | `env_id: int, proxy_value: str?, proxy_pool_id: str?` | `bool` | 运行时动态修改代理设置。 |

注意：这是异步工具，调用方式是：

```python
await ctx.tools.call("env.set_proxy", env_id=ctx.env_id, proxy_value="http://127.0.0.1:8888")
```

---

## 5. `ui.*`

| 工具名 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `ui.declare_data_table` | `view_id: str, schema: dict` | `bool` | 声明数据表格的渲染 Schema。 |
| `ui.get_data_table` | `view_id: str` | `dict` | 读取数据表格 Schema。 |

---

## 6. `captcha.*`

| 工具名 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `captcha.match_slider` | `background_image: str \| Path \| bytes, puzzle_piece_image: str \| Path \| bytes, puzzle_piece_start_bbox: tuple[int, int, int, int]?, device: str, return_debug: bool` | `SliderCaptchaMatchResult` | 调用宿主封装的 `sinanz` 滑块模型，返回缺口中心、边界框和可选调试信息。 |
| `captcha.match_click_targets` | `query_icons_image: str \| Path \| bytes, background_image: str \| Path \| bytes, device: str, return_debug: bool` | `ClickCaptchaMatchResult` | 调用宿主封装的点选模型，返回排序后的点击目标、缺失序号和可选调试信息。 |

---

## 7. `TaskContext` 内置常用方法

| 方法 | 说明 |
|---|---|
| `get_config(key, default=None)` | 安全获取宿主持久化的模块/工作流配置。 |
| `logger.info(msg)` | 模块专用日志，由 Core 统一收集并在控制台/UI 展示。 |
| `wait(seconds)` | 纯异步等待；不会自动提前响应停止请求。 |
| `screenshot(name)` | 捕获当前浏览器快照并自动保存至指定目录。 |
| `should_stop()` | 检查宿主是否发出了停止信号，长循环任务应主动检测。 |
| `emit_signal(signal)` | 向 ATM 发出结构化流程信号。 |

`TaskContext` 还提供 `ctx.runtime: dict[str, Any]`，用于暴露 ATM 写入的运行态元数据，例如：

- `workflow`
- `devel_mode`
- `execution_params`
- `job_params`
- `params`
- `creation_params`
- `final_status`
- `task_error`
- `task_result`
- `task_signal`
- `env_action`

约束补充：

- `ctx.get_config()` 不再读取 `workflow`、调试参数或环境创建参数
- `execution.params` / `job.params` 会进入 `ctx.runtime`

规则：

- `on_cleanup` 会在环境动作之后执行
- `on_cleanup` 本身不代表环境一定已经被删除
- 是否删除环境应以 `ctx.runtime["env_action"]` 为准

---

## 8. `TaskSignal`

```python
from crawler4j_sdk import EnvAction, TaskSignal

TaskSignal.fail(
    message="检测到黑号",
    error="black_account",
    env_action=EnvAction.DESTROY,
)

TaskSignal.wait_for_confirmation(
    message="请人工确认结果",
    env_action=EnvAction.KEEP_ALIVE,
    payload={
        "review_type": "account",
        "confirmation": {
            "title": "账号复核",
            "description": "请确认该账号是否允许继续执行。",
            "fields": [
                {"label": "账号", "value": "demo-account"},
                {"label": "风险等级", "value": "high"},
            ],
            "confirm_text": "确认放行",
            "reject_text": "确认拦截",
        },
    },
)
```

当前正式动作：

- `succeed`
- `fail`
- `cancel`
- `wait_for_confirmation`

`wait_for_confirmation` 会让任务停在 `WAITING_CONFIRMATION`；ATM 暂不执行终态 hooks 或环境清理，直到后续确认成功或失败。

如果你希望 ATM 客户端自动弹出结构化确认面板，请把 UI 描述写在 `payload.confirmation` 中。当前正式支持：

- `title`
- `description`
- `fields`：`[{ "label": "...", "value": "..." }]`
- `confirm_text`
- `reject_text`

若不提供这组字段，客户端会退回展示 `message` 与 payload 键值。

---

## 9. 标准返回类型 `TaskResult`

```python
from crawler4j_sdk import EnvAction, TaskResult, TaskSignal

# 成功
return TaskResult(success=True, message="完成", data={"count": 10})

# 失败
return TaskResult(success=False, message="登录失败")

# 携带流程信号
return TaskResult.fail(
    message="检测到黑号",
    error="black_account",
    signal=TaskSignal.fail(
        message="检测到黑号",
        error="black_account",
        env_action=EnvAction.DESTROY,
    ),
)
```

`TaskResult.signal` 是模块把流程控制权交给 ATM 的正式方式。不要把“销毁环境”“等待确认”之类的控制语义塞进随意的 `data` 字段里。
