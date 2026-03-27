# 综合测试设计文档 (Comprehensive Test Design Document)

## 1. 测试策略分析 (Test Strategy)

根据《需求规格说明书》与《详细开发设计文档》，本项目的测试策略采取 **"测试金字塔 (Test Pyramid)"** 模型，重点投入在单元测试与集成测试，并辅以核心链路的 E2E 验证。

### 1.1 测试范围与重点 (Scope & Focus)

| 测试层级 | 关注点 | 覆盖范围 | 工具/框架 |
| :--- | :--- | :--- | :--- |
| **Unit Testing** | 逻辑正确性、边界条件、异常分支 | Core Services (TSM/MMS), SDK Logic, Utils | `pytest`, `pytest-asyncio`, `unittest.mock` |
| **Integration Testing** | 组件交互、数据库 I/O、进程管理 | REM (Pool/Provider), Persistence (SQLite), EventBus | `pytest`, `aiosqlite` |
| **E2E Testing** | 用户视角的全链路、UI 交互、崩溃恢复 | 完整任务执行链路 (UI -> Core -> Env -> Task), GUI 渲染 | `pytest-qt` (UI), `playwright` (Browser) |

### 1.2 关键测试挑战与应对

1.  **环境管理 (REM)**: 涉及真实进程与浏览器，测试耗时且不稳定。
    *   *应对*: 大量使用 `MockProvider` 进行逻辑测试；仅在 Integration 阶段运行真实 `PlaywrightProvider`。
2.  **崩溃恢复 (Crash Recovery)**: 难以模拟真实物理掉电/进程杀停。
    *   *应对*: 测试夹具 (Fixture) 预写入 "Zombie State" 到 DB，启动 Core 后断言 `GC` 行为。
3.  **UI 异步性**: PyQt6 与 Asyncio 结合的死锁风险。
    *   *应对*: 严格使用 `qasync` 测试插件，验证 UI 不卡顿。

---

## 2. 详细测试用例设计 (Detailed Test Cases)

### 2.1 [Module-01] 运行时环境管理 (REM)

重点关注：生命周期状态机流转、资源配额控制、僵尸环境回收。

| 用例ID | 模块/接口 | 测试场景 | 前置条件 | 操作步骤 | 输入数据 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| TC_REM_001 | EnvManager | **正常创建与租用** (Happy Path) | Pool 为空，Quota 未满 | 调用 `acquire` 申请新环境 | `req={kind:browser, tags:[chromium]}` | 1. Provider.create 被调用<br>2. 返回有效 Lease<br>3. Env 状态=BUSY | P0 |
| TC_REM_002 | EnvManager | **复用空闲环境** | Pool 中有 READY 态环境 | 调用 `acquire` 申请匹配环境 | `req={tags:[chromium]}` | 1. 不调用 Provider.create<br>2. 返回现有 Env 的 Lease<br>3. Env 状态变更为 BUSY | P0 |
| TC_REM_003 | EnvManager | **配额超限拦截** (Boundary) | Pool 已满 (达到 max_instances) | 调用 `acquire` | `req={...}` | 抛出 `ResourceExhaustedError` 或进入等待队列 | P1 |
| TC_REM_004 | EnvManager | **释放并重置** | 环境处于 BUSY 状态 | 调用 `release` | `lease_id=xyz` | 1. Provider.reset 被调用<br>2. Env 状态变更为 READY<br>3. Lease 失效 | P0 |
| TC_REM_005 | GC Worker | **僵尸环境回收** (Sad Path) | DB 中存在 BUSY 记录但无内存对象 | Core 启动，执行 Startup 扫描 | 无 | 1. 对应 Env 状态置为 DEAD<br>2. 触发 Provider.destroy 清理物理残留 | P1 |
| TC_REM_006 | Provider | **创建超时处理** | Provider 模拟卡死 | 调用 `acquire` | `timeout=5s` | 抛出 `SpawnTimeoutError`，不残留中间状态数据 | P2 |

### 2.2 [Module-02] 任务策略管理 (TSM)

重点关注：并发桶逻辑、策略合并优先级、YAML 热更新。

| 用例ID | 模块/接口 | 测试场景 | 前置条件 | 操作步骤 | 输入数据 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| TC_TSM_001 | Admission | **全局并发正常准入** | 全局活跃数 < global_max | 提交新任务 | `task_req` | 返回 `AdmissionResult.OK`，全局计数器+1 | P0 |
| TC_TSM_002 | Admission | **模块级配额拦截** (Boundary) | 模块 A 活跃数 = bucket_limit | 提交模块 A 的新任务 | `task_req(module=A)` | 返回 `AdmissionResult.REJECTED` (或 QUEUED) | P1 |
| TC_TSM_003 | StrategyMgr | **策略合并优先级** | Global/Module/Task 均配置了超时 | 获取生效策略 | `Global=10s, Module=20s, Task=30s` | 最终策略超时时间为 30s (Task Override 优先) | P1 |
| TC_TSM_004 | StrategyMgr | **YAML 格式校验** (Sad Path) | 无 | 加载损坏的 YAML 策略文件 | `str: invalid_yaml: [` | 捕获解析异常，回退到 Default 策略，记录 Error 日志 | P2 |
| TC_TSM_005 | HotReload | **动态扩容生效** | 任务在 Pending 队列 | 修改并保存策略，增加配额 | `global_max: 10 -> 20` | 1. 触发 `STRATEGY_UPDATED` 事件<br>2. Pending 任务被调度执行 | P2 |

### 2.3 [Module-03] 模块管理系统 (MMS)

重点关注：Manifest 校验、SDK 版本兼容性、ZIP 路径安全。

| 用例ID | 模块/接口 | 测试场景 | 前置条件 | 操作步骤 | 输入数据 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| TC_MMS_001 | Loader | **加载合法模块** (Happy Path) | 目录下存在标准模块包 | 调用 `load_module` | `path=./modules/ctrip` | 1. 返回 Valid Package 对象<br>2. 解析出 Workflows 列表 | P0 |
| TC_MMS_002 | Loader | **SDK 版本不兼容拦截** | 当前 SDK=0.5.0 | 加载模块 | `manifest.sdk_version=">=1.0.0"` | 模块状态标记为 `INCOMPATIBLE`，错误信息包含版本对比 | P0 |
| TC_MMS_003 | Installer | **Zip Slip 攻击防御** (Security) | 无 | 上传恶意构造的 ZIP 包 | `file.zip` (包含 `../../etc/passwd`) | 安装失败，抛出 `SecurityError`，未发生文件覆盖 | P0 |
| TC_MMS_004 | Registry | **禁用模块生效** | 模块处于 ACTIVE 状态 | 在设置中禁用模块 | `module_name=ctrip` | 1. 状态变更为 DISABLED<br>2. `get_active_modules` 不再返回该模块 | P1 |

### 2.4 [Module-04] 数据持久化层

重点关注：分层读写隔离、SQLite WAL 并发性能、JSON 序列化。

| 用例ID | 模块/接口 | 测试场景 | 前置条件 | 操作步骤 | 输入数据 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| TC_DB_001 | StateRepo | **KV 写入与读取** (Happy Path) | DB 连接正常 | 1. set key<br>2. get key | `k="token", v={"a":1}` | 读取到的 value 与写入一致（反序列化后） | P0 |
| TC_DB_002 | StateRepo | **TTL 过期清理** (Boundary) | 无 | 1. set key with ttl=1s<br>2. sleep 2s<br>3. get key | `ttl=1` | 返回 `None` (数据已逻辑或物理删除) | P1 |
| TC_DB_003 | ConfigRepo | **配置更新持久化** | 无 | update config | `module:A:cfg, val={}` | 重启 Database Manager 后，仍能读取到最新值 | P0 |
| TC_DB_004 | DataRepo | **高并发写入** (Performance) | WAL 模式开启 | 启动 10 个协程并发 emit | `doc={...} * 1000` | 1. 不抛出 `DatabaseLocked`<br>2. 最终记录数 = 1000 | P2 |

### 2.5 [Module-05] SDK 核心契约

重点关注：TaskContext 能力注入、异常传递、TaskResult 结构。

| 用例ID | 模块/接口 | 测试场景 | 前置条件 | 操作步骤 | 输入数据 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| TC_SDK_001 | TaskContext | **能力注入** | 任务启动 | 检查 ctx 属性 | 无 | `ctx.page`, `ctx.log`, `ctx.storage` 均不为 None | P0 |
| TC_SDK_002 | TaskScript | **任务执行成功** | Mock Context | 运行 TaskScript.run | 无 | 返回 `TaskResult(status=SUCCESS, data={...})` | P0 |
| TC_SDK_003 | TaskScript | **异常向外抛出** (Sad Path) | 无 | Task 内部抛出未捕获异常 | `raise ValueError("oops")` | 1. 调用者捕获到异常<br>2. 能够获取到完整的 StackTrace | P1 |
| TC_SDK_004 | StorageAPI | **Mock 存储测试** | 使用 MockStorage | 调用 `ctx.storage.state.set` | `k, v` | 数据写入 Mock 字典，未产生真实 IO | P2 |

### 2.6 [Module-06] UI Host

重点关注：声明式表单渲染、Micro-app 崩溃隔离、路由导航。

| 用例ID | 模块/接口 | 测试场景 | 前置条件 | 操作步骤 | 输入数据 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| TC_UI_001 | SchemaForm | **JSON 渲染为表单** | Schema 有效 | 加载 SchemaFormWidget | `{"type":"string"}` | 界面显示一个 QLineEdit 输入框 | P0 |
| TC_UI_002 | MicroApp | **加载受信 Widget** | 模块受信 | 加载 Micro-app 页面 | `entry="ui.py"` | 成功显示自定义 Widget 内容 | P1 |
| TC_UI_003 | MicroApp | **未受信降级** (Security) | 模块未签名/白名单外 | 加载 Micro-app 页面 | `entry="ui.py"` | 自动降级显示“通用模块页”，提示“未被信任” | P0 |
| TC_UI_004 | ErrorBoundary| **Widget 内部崩溃** (Sad Path) | 加载 Buggy Widget | 初始化时触发异常 | `raise RuntimeError` | App 不闪退，页面区域显示“加载失败”及错误堆栈 | P1 |

---

## 3. 接口测试规范 (API Test Specification)

虽然主要是内部 API，但针对 Core 与 SDK/UI 的边界，需定义明确的断言。

### 3.1 模块加载接口 `MMS.load(path)`

*   **Request**: `path: Path`
*   **Response**: `ModulePackage`
*   **Assertion Rules**:
    1.  `pkg.manifest` 必须非空且符合 Pydantic Model。
    2.  `pkg.entry_points` 中的函数必须可被 `inspect` 获取签名。

### 3.2 任务提交接口 `Scheduler.submit(flow)`

*   **Request**: `TaskFlow` 对象, `Strategies` (Optional)
*   **Response**: `run_id: str`
*   **Assertion Rules**:
    1.  `run_id` 必须是 UUID4 格式。
    2.  提交后立即查询 `Scheduler.get_status(run_id)` 应返回 `PENDING` 或 `RUNNING`。

### 3.3 存储接口 `Storage.set(key, val)`

*   **Request**: `key: str`, `val: Any` (Must be JSON serializable)
*   **Assertion Rules**:
    1.  如果 `val` 包含不可序列化对象 (如 datetime)，应抛出 `SerializationError`。
    2.  设置后 `get(key)` 返回的值类型应与输入一致 (dict 仍为 dict, list 仍为 list)。
