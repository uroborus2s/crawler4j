# 4.5 Core 注入能力 API 参考 (SDK 2.0.0)

本页提供 `TaskContext` 注入能力的完整 API 参考。这是模块与宿主 (Core) 交互的唯一官方通道。

## 1. `ctx.db` (DatabaseCapability)

用于持久化模块数据和管理运行状态。

### 数据集操作
| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `list_records(dataset)` | `dataset: str` | `list[dict]` | 读取名为 `dataset` 的数据集。 |
| `replace_records(dataset, records)` | `dataset: str, records: list[dict]` | `bool` | **全量覆盖** 数据集内容。 |

### 状态管理 (Lightweight State)
用于存储登录 Cookie、翻页游标等小规模数据。
| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `get_state(key)` | `key: str` | `Any` | 读取键值。 |
| `set_state(key, value, ttl=None)` | `key: str, value: Any, ttl: int?` | `bool` | 写入键值，可设置过期秒数。 |
| `exists_state(key)` | `key: str` | `bool` | 判断键是否存在。 |

### 幂等锁 (Distributed Lock)
| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `acquire_lock(scope, key, ttl=60)` | `scope: str, key: str, ttl: int` | `bool` | 获取互斥锁。 |
| `release_lock(scope, key)` | `scope: str, key: str` | `bool` | 释放锁。 |

---

## 2. `ctx.ip_pool` (IPPoolCapability)

| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `pick_proxy(criteria=None)` | `criteria: dict?` | `dict?` | 获取代理信息，如 `{"http": "..."}`。 |

---

## 3. `ctx.env_ops` (EnvOpsCapability)

| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `set_proxy(env_id, proxy_value=None)` | `env_id: int, proxy_value: str?` | `bool` | 运行时动态修改代理设置。 |

---

## 4. `ctx.ui` (UICapability)

| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `declare_data_table(view_id, schema)` | `view_id: str, schema: dict` | `bool` | 声明数据表格的渲染 Schema。 |

---

## 5. `TaskContext` 内置常用方法

| 方法 | 说明 |
|---|---|
| `get_config(key, default=None)` | 安全获取模块配置 (来自 `module.yaml` 或 UI 输入)。 |
| `logger.info(msg)` | 模块专用日志，由 Core 统一收集并在控制台/UI 展示。 |
| `wait(seconds)` | 异步等待，支持框架级停止请求检测。 |
| `screenshot(name)` | 捕获当前浏览器快照并自动保存至指定目录。 |
| `should_stop()` | 检查宿主是否发出了停止信号，长循环任务应主动检测。 |

---

## 6. 标准返回类型 `TaskResult`

```python
from crawler4j_sdk import TaskResult

# 成功
return TaskResult(success=True, message="完成", data={"count": 10})

# 失败
return TaskResult(success=False, message="登录失败")
```
