# 6.1 TaskScript（原子任务契约）

TaskScript 是最小可执行单元：对外表现为“给定上下文与配置，执行一次业务动作并返回结构化结果”。

## 6.1.1 需求说明

### 面向任务开发者

- MUST 只需要实现一个主方法：`execute(ctx) -> TaskResult`（异步）。
- SHOULD 可选实现生命周期钩子：`on_init/on_error/on_cleanup`，用于初始化、错误补救、资源清理。
- MUST 使用 `ctx` 获取框架能力（浏览器/HTTP/日志/存储等），不得直接耦合 Core 的内部对象。

### 面向框架运行时

- MUST 以“一次执行”实例化并运行 TaskScript；不得复用同一个实例跨多次执行（避免隐式共享状态）。
- MUST 捕获 `execute()` 抛出的异常，并调用 `on_error()`（若实现），最终转换为 `TaskResult.fail(...)` 或等价失败语义。
- SHOULD 在任何情况下调用 `on_cleanup()`（finally 语义）。

## 6.1.2 需求分析分解（契约要素）

TaskScript 的稳定契约包括：

1. **元数据**（类属性）

- MUST: `name: str` —— 任务唯一标识（稳定、可追溯、用于调度/引用）。
- SHOULD: `display_name: str` —— 面向 UI/日志的可读名称。
- SHOULD: `description: str` —— 简要说明。
- MAY: `default_config: dict` —— 默认配置，运行时会与外部配置合并。

2. **主执行方法**

- MUST: `async def execute(self, ctx: TaskContext) -> TaskResult`

3. **生命周期钩子**（可选）

- MAY: `async def on_init(self, ctx)` —— 在 execute 之前。
- MAY: `async def on_error(self, ctx, error)` —— execute 异常时。
- MAY: `async def on_cleanup(self, ctx)` —— 无论成功/失败都会执行。

4. **并发与重入语义**

- MUST: 单个 TaskScript 实例不要求线程安全；框架不得并发调用同一实例的 execute。
- SHOULD: TaskScript 逻辑应尽量“幂等/可重试”，便于上层做失败重试。

## 6.1.3 契约设计（接口/生命周期/并发语义）

### 6.1.3.1 最小接口（以当前实现为准）

当前仓库实现位于：`crawler4j_sdk/base.py`。

关键点：

- `execute` 为抽象方法（必须实现）
- `on_init/on_error/on_cleanup` 为可选覆盖

### 6.1.3.2 生命周期时序

建议的运行时调用序：

1. 构造脚本实例：`instance = ScriptClass()`
2. 调用初始化：`await instance.on_init(ctx)`
3. 调用主执行：`result = await instance.execute(ctx)`
4. 若发生异常：`await instance.on_error(ctx, error)`
5. finally：`await instance.on_cleanup(ctx)`

> 约束：`on_error()` **不得**吞掉必须上抛的结构化失败；运行时最终必须产出一个 TaskResult（成功或失败）。

### 6.1.3.3 配置合并规则（建议）

- 合并来源：
  1. `TaskScript.default_config`
  2. 任务配置（来自 module.yaml / UI / 环境配置等）
- 合并策略：
  - MUST: 外部配置覆盖 default_config
  - SHOULD: 深合并（dict 递归合并），避免 default_config 大段被覆盖丢失
  - SHOULD: 对关键字段进行校验（类型、取值范围、必填项）

### 6.1.3.4 并发语义与状态管理

- MUST: 通过 `ctx.state` 存储跨方法共享状态（如 token、临时缓存）。
- SHOULD: 避免使用全局变量缓存会话/账号等数据（会导致多环境/多任务串扰）。
- SHOULD: 在 `ctx` 的事件循环内执行异步 I/O；不得在 async 方法里进行长时间阻塞调用。

### 6.1.3.5 结果与错误语义（简要）

- 推荐：
  - 业务失败（可预期，如登录失败、验证码错误）→ `TaskResult.fail(message, error=...)`
  - 不可预期异常（代码 bug、网络库崩溃）→ 允许抛异常，由运行时转换为失败结果，并记录诊断信息

> 更完整的错误/重试建议见：6.7。

## 6.1.4 功能级规格（按模板）

本节用于为具体 TaskScript（如 `claim_task`、`login`）编写功能级规格。

- 建议模板：`docs/archive/reference-srs/templates/feature.md` / `docs/archive/reference-srs/templates/usecase.md`
- 每个 TaskScript 至少给出：输入（ctx.config 关键项）/输出（TaskResult.data）/失败场景/可重试建议/验收标准。

### 6.1.4 任务上下文 (TaskContext)

`run(self, ctx: TaskContext)` 中的 `ctx` 对象是任务与系统交互的唯一入口。

#### 核心属性

| 属性 | 类型 | 说明 |
| :--- | :--- | :--- |
| `ctx.task_id` | str | 当前任务唯一ID |
| `ctx.config` | dict | 任务级参数 (Task Params) |
| `ctx.global_config` | dict | 模块级全局配置 (Global Config, Read-Only) |
| `ctx.browser` | BrowserAPI | 浏览器操作句柄 (Playwright/Selenium 封装) |
| `ctx.storage` | StorageAPI | 数据持久化接口 |

#### 持久化接口 (ctx.storage)

```python
# 1. 读取全局配置 (定义的 Schema)
accounts = ctx.global_config.get("account_pool", [])

# 2. 管理运行时状态 (KV Store)
# 场景: 登录成功后保存 Cookie
ctx.storage.state.set(
    key=f"cookies:{username}", 
    value=browser_cookies, 
    ttl=86400 # 24小时过期
)

# 场景: 检查是否已有缓存 Cookie
cached_cookies = ctx.storage.state.get(f"cookies:{username}")
if cached_cookies:
    ctx.browser.add_cookies(cached_cookies)

# 3. 提交业务数据
ctx.emit({
    "order_id": "10023",
    "amount": 99.0
})
```
