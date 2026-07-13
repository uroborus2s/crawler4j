# Core `env.cookie.ensure` 原子能力需求简报

- 项目：crawler4j
- Work item：`CR-020`
- 状态：`requirements_ready`
- 场景：`add_requirement`
- 版本：`0.1.0`
- 日期：2026-07-13
- 来源：模块侧已确认设计并委托 Core 实施
- 关联任务：`TASK-040`

## 目标

作为 `core-native-v2` 模块开发者，我希望通过一个供应商无关的 Core 工具确保当前环境的 Cookie 已持久化并进入新浏览器运行态，以便业务模块只表达认证意图，不直接操作 VirtualBrowser 生命周期。

模块通过 `ctx.tools.call("env.cookie.ensure", ...)` 提交当前环境的完整目标 Cookie 集合。Core 负责全量替换、持久化校验、必要重启、CDP 重连、运行态校验以及 `TaskContext` 的 Page/Context 回绑；任何阶段失败均抛异常，模块不得继续业务流程。

## 精确公开契约

```python
result = await ctx.tools.call(
    "env.cookie.ensure",
    env_id=ctx.env_id,
    cookies=[
        {
            "name": "cticket",
            "value": cticket,
            "domain": ".ctrip.com",
            "path": "/",
            "expires": expires_at,
            "secure": True,
            "httpOnly": True,
        }
    ],
    reload="restart_if_changed",
    verify="runtime",
)
```

返回 Mapping 至少包含 `persisted`、`restarted`、`browser_ready`、`runtime_matched` 四个布尔值。成功必须满足 `runtime_matched is True`；失败直接抛异常。

## 业务规则

- 工具只注册到 full runtime surface。
- `env_id` 必须等于当前 `TaskContext.env_id`，模块不能修改其他环境。
- Core API 保留公开 Cookie 字段 `httpOnly`，`expires` 接受 Unix seconds `float`。
- `cookies` 表示环境替换后的完整 Cookie 集合；未传入的既有 Cookie 必须删除，空列表表示清空全部 Cookie。
- Core 不向模块暴露 `updateCookie/getCookie/stopBrowser/launchBrowser` 等 Provider API。
- Cookie 持久化集合不完全一致时全量写入并通过 `getCookie` 复核；比较覆盖名称、值、域名、路径、有效期和安全属性，其中有效期按 float Unix seconds 严格比较。
- 环境运行中且 Cookie 发生变化时，必须完整停止、等待旧运行态和 CDP 关闭、重新启动并连接。
- 发生 stop/start 后，Core 必须把新 `BrowserHandle.page/context` 回绑到当前 `TaskContext`，并重新 bind tools。
- 运行态 Cookie 必须从新 BrowserContext 读取并匹配；不匹配时抛异常。
- 日志、异常和返回值不得包含 API Key 或完整 Cookie value。

## 异常流程

- 环境不存在、不是当前环境、Provider 不支持持久化 Cookie、参数无效：在写入和重启前失败。
- 写入或持久化复核失败：不进入后续业务流程。
- 停止未完成、CDP 未关闭、启动失败、CDP 连接失败：抛异常，不返回部分成功。
- 运行态校验失败：抛异常，不返回 `runtime_matched=False` 的正常结果。

## 非目标

- 不新增模块配置、manifest 字段或 SDK 扫描声明。
- 不允许模块直接调用 VirtualBrowser API。
- 不在本轮实现其他 Provider 的持久化 Cookie 适配。
- 不在返回 Mapping 中暴露 Browser、Context、Page 或 Cookie value。

## 验收标准

- `AC-020-001`：full runtime surface 注册异步工具 `env.cookie.ensure`，其他受限 surface 不注册。
- `AC-020-002`：公开调用接受委托中精确字段和参数，成功 Mapping 包含四个必需 bool 且 `runtime_matched=True`。
- `AC-020-003`：持久化和运行态 Cookie 集合与传入集合完全一致时不写入、不重启。
- `AC-020-004`：持久化集合不完全一致（包括存在未传入 Cookie）时，严格执行全量替换、持久化复核、停止等待、启动连接和运行态复核。
- `AC-020-005`：同一 `env_id` 并发 ensure 被 Core 串行化。
- `AC-020-006`：stop/start 后 `ctx.page`、`ctx.context` 和 browser tools 均指向新 BrowserHandle。
- `AC-020-007`：任一阶段失败均抛异常，不能正常返回 `runtime_matched=False`。
- `AC-020-008`：测试日志和异常不包含 API Key 或完整 Cookie value。

## 非功能需求

- `NFR-020-001` 安全：Cookie value 和 API Key 在请求日志、错误日志、异常消息及结果中零明文出现。
- `NFR-020-002` 并发：Manager 共享的同环境生命周期锁同时覆盖 ensure、普通 start/stop 和 TaskContext 回绑，锁在异常和取消后释放。
- `NFR-020-003` 可维护性：Core 编排依赖供应商无关 Provider 能力，VirtualBrowser 字段与 endpoint 映射限制在 Provider 层。
- `NFR-020-004` 兼容性：现有 `env.*`、`browser.*` 工具和受限 runtime surface 行为不变。

## baseline 影响分析

- 领域：REM 继续拥有环境生命周期，ATM 只暴露并回绑当前运行上下文，模块只表达业务意图。
- 架构：新增 REM Cookie 协调服务和 Provider 可选能力，不改变 Core runtime owner 边界。
- API：新增 `API-022 env.cookie.ensure`，属于 `TaskContext.tools` 向后兼容扩展。
- 数据库：无影响。
- UI：无影响。
- 文档：更新 Core capabilities 和 API 设计事实。

## 风险与回滚

- 风险：VirtualBrowser Cookie endpoint 与公开文档存在版本差异；Client 适配以 2026-07-13 本机实测的顶层 `cookies` 请求和 `data` 数组响应为准，并由单元测试锁定。
- 风险：现有 `close()` 为宽松成功语义；Cookie 重启必须使用可验证的严格停止路径。
- 回滚：移除工具注册、Cookie 协调服务和 VirtualBrowser Cookie 适配即可；无数据迁移。
- 决策：用户于 2026-07-13 明确确认全量替换语义，模块传入什么就替换为什么，删除其他全部 Cookie。
- 未决问题：无。公开字段和成功/失败语义以本简报为准。
