# Core `env.cookie.ensure` 实施计划

> **给执行者：** 计划评审通过后，把状态交还 `using-shanforge` 流程总控判断执行。

**目标：** 在 full runtime surface 交付供应商无关的 `env.cookie.ensure`，由 Core 原子完成 Cookie 持久化、必要重启、CDP 重连、运行态校验和当前 TaskContext 回绑。

**架构：** ATM 的 `CoreEnvTools` 只负责当前环境授权、调用 REM 和回绑 `TaskContext`；新建 REM Cookie 协调服务负责 Cookie 规范化、完整集合匹配、按环境加锁和生命周期编排；VirtualBrowser Client/Provider 只负责实测 `getCookie/updateCookie` JSON 协议、字段映射与严格停止等待。模块与 Contracts 不感知 Provider API，也不新增模块配置或 manifest 字段。

**技术栈：** Python 3.12、asyncio、httpx、Playwright、pytest、ruff、uv。

**工作项：** `CR-020`

**任务：** `TASK-040`

**状态：** `completed`

---

## 输入

- 已确认契约：当前会话 `<codex_delegation>` 中的精确 `ctx.tools.call(...)` 调用、结果四个 bool、异常和上下文回绑语义。
- 当前工作项简报：`.factory/workitems/CR-020/brief.md`
- 相关摘要：`.factory/memory/api.summary.md`、`.factory/memory/architecture.summary.md`
- 正式文档：`docs/03-developer-guide/v0.4.0/reference-core-capabilities.md`、`docs/04-project-development/04-design/api-design.md`
- Provider 实测事实：VirtualBrowser `GET /api/getCookie?id=<id>` 返回 `data` Cookie 数组；`POST /api/updateCookie` 接收 `id + cookies`，并以传入数组全量替换现有 Cookie。证据见 `.factory/workitems/CR-020/evidence/virtualbrowser-cookie-api-probe.md`。

## 范围

### 目标

- 注册并实现 full runtime `env.cookie.ensure`。
- 支持公开字段 `name/value/domain/path/expires/secure/httpOnly`，其中 `expires` 接受 Unix seconds float。
- 模块传入替换后的完整 Cookie 集合；Core 删除所有未传 Cookie，空列表清空全部 Cookie。
- 同一环境 ensure 串行执行；Cookie 或运行态不匹配时严格停止、等待旧 CDP 关闭、启动、连接和运行态复核。
- stop/start 后把新 BrowserHandle page/context 回绑当前 TaskContext 并重新 bind tools。
- 失败抛安全异常，不返回正常的 `runtime_matched=False`。

### 非目标

- 不新增 Contracts 类型、SDK scanner、module.yaml 或 manifest 字段。
- 不实现 BitBrowser、Playwright local 等其他 Provider 的持久化 Cookie。
- 不返回 Browser/Context/Page 或 Cookie value。
- 不执行真实携程业务模块 E2E；本工作项只交付 Core 可测试能力。

## 文件

| 类型 | 路径 | 职责 |
|---|---|---|
| 新建 | `packages/crawler4j/src/core/rem/cookie_service.py` | 公开 Cookie 规范化、完整集合匹配、按 env_id 加锁及 ensure 编排 |
| 修改 | `packages/crawler4j/src/core/rem/provider.py` | VirtualBrowser getCookie/updateCookie 适配、严格 stop 等待及敏感日志保护 |
| 修改 | `packages/crawler4j/src/core/rem/manager.py` | 向 Cookie Service 提供当前 REM 生命周期入口，不向 ATM 泄漏 Provider |
| 修改 | `packages/crawler4j/src/core/atm/runtime_capabilities.py` | full surface 注册工具、校验当前 env、回绑 TaskContext 和 tools |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_rem/test_env_cookie_service.py` | 规范化、幂等、更新重启、失败和并发编排行为 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py` | 实测 getCookie/updateCookie endpoint、payload、字段映射、解析和敏感错误语义 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py` | 严格停止、运行列表与 CDP 关闭等待 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py` | 工具 surface、精确调用和 TaskContext/tools 回绑 |
| 文档 | `docs/03-developer-guide/v0.4.0/reference-core-capabilities.md` | 模块精确调用、字段、返回、失败和旧 Page 禁止规则 |
| 文档 | `docs/04-project-development/04-design/api-design.md` | 登记 `API-022` Core/REM/Provider 边界 |
| 记忆 | `.factory/memory/api.summary.md` | 索引 API-022 稳定契约 |
| 记忆 | `.factory/memory/tasks.summary.md` | 索引 CR-020/TASK-040 状态和证据路径 |

## 边界

- 层级：Module → `TaskContext.tools` → ATM adapter → REM Cookie Service → Provider adapter。
- 领域：REM 拥有环境和浏览器生命周期；ATM 拥有当前 TaskContext 回绑；模块拥有 cticket 获取与业务时序。
- 接口归属方：`env.cookie.ensure` 归 Core Runtime API；VirtualBrowser Cookie JSON 归 Provider。
- 下游依赖：现有 `EnvironmentManager.start_env/stop_env`、`BrowserHandle`、Playwright BrowserContext cookies。
- 禁止耦合：模块代码、Contracts 和 SDK 不得 import VirtualBrowser Client；REM Service 不得依赖业务 Cookie 名或携程域名。

## 任务 1：TASK-040 Core Cookie ensure 纵向切片

**任务切片：**

- 设计方案：以模块传入的完整 Cookie 集合为期望状态；先读持久化和运行态，集合不一致时原样全量替换，复核后执行严格重启并从新 Context 验证。
- 接口设计：公开调用和字段严格遵循 brief；成功 Mapping 固定含 `persisted/restarted/browser_ready/runtime_matched` 四个 bool。
- UI：`N/A`，该能力只属于模块运行时与 REM，不新增用户界面。
- 测试设计：单元测试覆盖完整集合匹配、删除未传 Cookie、实测 Provider payload、幂等分支、重启顺序、同环境并发锁、异常路径、full surface 以及 context/tools 回绑。
- 开发：先实现无 I/O 的 Cookie helpers，再实现 Provider I/O，随后接入 REM 编排和 ATM adapter。
- 单测：使用 AsyncMock/fake provider 精确断言调用顺序和结果，不连接真实 VirtualBrowser。
- review：实现者只提交 `ready_for_review` 状态和评审输入包。
- 集成测试：运行 REM、ATM 相邻单测及完整 unit；真实 VirtualBrowser/携程 E2E 记录为未运行。
- 失败断言：缺测试设计则失败；UI 写 `N/A` 但无原因则失败；发现占位语则失败。

**文件：** 使用“文件”表中全部源文件、测试、文档和 memory 文件。

- [x] **步骤 1：RED——写公开契约、Provider 和协调服务失败测试**

  新增测试断言：
  - `env.cookie.ensure` 只存在于 full surface。
  - VirtualBrowser Client 使用实测 endpoint、顶层 `cookies` payload 和 `data` 数组响应。
  - 传入集合少于当前集合时，未传 Cookie 被删除；空列表清空全部 Cookie。
  - 相同 Cookie 不重启；不相同时按 `read → write → read → stop → wait → start → runtime verify` 执行。
  - 同 env 并发最大活跃 ensure 数为 1。
  - restart 后 `ctx.page/context` 与新 handle 一致，tools 重新绑定。
  - 所有失败路径抛异常，安全消息不含 Cookie value/API Key。

- [x] **步骤 2：运行 RED 并确认失败原因是目标能力缺失**

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_env_cookie_service.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py -q -p no:cacheprovider
```

期望：新增测试因 `cookie_service`、Client 方法或 `env.cookie.ensure` 未实现而失败；既有测试不出现无关故障。

- [x] **步骤 3：GREEN——实现 Cookie 规范化和 VirtualBrowser 适配**

  - `cookie_service.py` 接受公开 camelCase Cookie 字段，以完整集合执行规范化、排序和等价比较。
  - `get_cookie()` 解析实测 `data` 数组，并可兼容历史嵌套响应；空值归一为空列表。
  - `update_cookie()` 将 `expires` 映射为 `expirationDate`，发送 `{"id": id, "cookies": [...]}`，不记录 payload/response body。
  - `sameSite` 比较大小写不敏感；敏感日志 sanitizer 识别 Cookie 容器中的 `value/jsonStr`。

- [x] **步骤 4：GREEN——实现 ensure 编排和严格重启**

  - 同 env keyed lock 包围完整 read/write/restart/verify。
  - `reload` 只接受 `restart_if_changed`，`verify` 只接受 `runtime`。
  - 当前运行态匹配且持久化未变化时返回 `restarted=False`。
  - 持久化变化或运行态不匹配时严格 stop/wait/start；等待同时确认运行列表消失与旧 CDP 端口不可连接。
  - 新 Context Cookie 完整集合不匹配（包括存在额外 Cookie）则抛异常。

- [x] **步骤 5：GREEN——注册工具并回绑上下文**

  - full surface 和 CoreTools 注册 `env.cookie.ensure` 异步 handler。
  - handler 拒绝 `env_id != ctx.env_id`。
  - ensure 成功后从新 `env.handle` 更新 `ctx.page/context`，再调用 `ctx.tools.bind_task_context(ctx)`。

- [x] **步骤 6：运行 GREEN 和相邻回归**

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_env_cookie_service.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py -q -p no:cacheprovider
uv run pytest packages/crawler4j/tests/unit/test_core/test_rem packages/crawler4j/tests/unit/test_core/test_atm -q -p no:cacheprovider
```

期望：目标测试和 REM/ATM 相邻单测全部通过，失败数为 0。

- [x] **步骤 7：文档、证据和记忆同步**

  - 更新两份正式文档和两份 memory summary。
  - 写 `.factory/workitems/CR-020/evidence/TASK-040.md`。
  - 写 `.factory/workitems/CR-020/reports/TASK-040.md`。
  - 写 `.factory/workitems/CR-020/reviews/TASK-040-review-input.md`。
  - 追加 ledger `ready_for_review` 事件。

- [x] **步骤 8：质量门和评审门**

```bash
uv run ruff format --check packages/crawler4j/src/core/rem/cookie_service.py packages/crawler4j/src/core/rem/provider.py packages/crawler4j/src/core/rem/manager.py packages/crawler4j/src/core/atm/runtime_capabilities.py packages/crawler4j/tests/unit/test_core/test_rem/test_env_cookie_service.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py
uv run ruff check packages/crawler4j/src/core/rem/cookie_service.py packages/crawler4j/src/core/rem/provider.py packages/crawler4j/src/core/rem/manager.py packages/crawler4j/src/core/atm/runtime_capabilities.py packages/crawler4j/tests/unit/test_core/test_rem/test_env_cookie_service.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py
uv run pytest packages/crawler4j/tests/unit -q -p no:cacheprovider
git diff --check
```

  期望：format check、Ruff、完整 unit 和 diff check 全部通过。实现者状态只能进入 `ready_for_review`。

## 测试策略

- 红灯：四个目标测试文件，确认失败源于缺少工具、Service 或 Provider 方法。
- 绿灯：同一测试集合通过。
- 定向回归：REM Cookie Service、VirtualBrowser Client/Provider、ATM runtime capabilities。
- 邻近回归：完整 REM 与 ATM unit。
- 全量回归：`packages/crawler4j/tests/unit`。
- 已运行接口探针：一次性 VirtualBrowser 环境验证读写结构、字段映射和全量替换语义，环境已删除。
- 未运行项：真实携程页面和业务模块 E2E。
- 未运行原因：需要真实 cticket 和业务模块配合，不属于可重复 Core 单元测试范围。

## 文档同步

- 正式文档：登记 API-022，并给出模块调用、结果和 Page 换代规则。
- `.factory/memory/`：只记录 API/任务状态和产物路径，不复制 Cookie 值或长测试输出。
- 工作项流水账：计划、实现、评审、验证和提交各自写独立事件。

## 评审门

- 计划评审：`completed`
- 任务评审：`approved (99/100)`
- 验证：`passed`
- 提交：`completed (afae0136)`
- 记忆同步：`completed`

## 计划自审

- 规格覆盖：AC-020-001 至 AC-020-008 均映射到 TASK-040 的测试与实现步骤。
- 占位符扫描：无占位符或未定义交付。
- 发现占位语则失败：通过。
- 缺测试设计则失败：通过，已列 RED/GREEN、定向、相邻和全量测试。
- UI 写 `N/A` 但无原因则失败：通过，已说明无 UI 变更。
- 类型一致性：公开 camelCase Cookie Mapping、float expires 和四个 bool 与委托一致。
- 可构建性：文件、调用顺序、真实命令和期望输出完整。
- Shanforge 门禁：包含 evidence、report、review、ledger、memory 和提交前验证。
