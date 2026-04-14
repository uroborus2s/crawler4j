# 4.5 Core 注入能力 API 参考 (SDK 1.1.0)

本页提供 `TaskContext.tools` 的完整 API 参考。这是模块与宿主 (Core) 交互的唯一官方扩展通道。

## 1. `ctx.tools` (ToolsCapability)

| 方法 | 说明 |
|---|---|
| `has_tool(name)` | 检查某个工具是否存在 |
| `list_tools()` | 列出当前可用工具及其说明 |
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
| `get_config(key, default=None)` | 安全获取模块配置（来自 `module.yaml` 或 UI 输入）。 |
| `logger.info(msg)` | 模块专用日志，由 Core 统一收集并在控制台/UI 展示。 |
| `wait(seconds)` | 异步等待，支持框架级停止请求检测。 |
| `screenshot(name)` | 捕获当前浏览器快照并自动保存至指定目录。 |
| `should_stop()` | 检查宿主是否发出了停止信号，长循环任务应主动检测。 |

---

## 8. 标准返回类型 `TaskResult`

```python
from crawler4j_sdk import TaskResult

# 成功
return TaskResult(success=True, message="完成", data={"count": 10})

# 失败
return TaskResult(success=False, message="登录失败")
```
