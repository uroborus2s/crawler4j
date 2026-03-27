# 测试设计文档：[Module-04] 数据持久化层 (Persistence)

## 1. 测试范围与目标

本测试文档覆盖《需求规格说明书 5.9》及《详细设计文档 Module-04》中定义的所有功能需求 (FR)。
目标是验证数据层 (DataLayer) 能正确封装 SQLite 操作，提供稳定的 Config/State/Data 读写接口，并处理并发与锁。

**测试对象**: `src.core.persistence` 包
**核心类**: `DatabaseManager`, `ConfigRepository`, `StateRepository`, `DataCollection`

## 2. 功能需求测试 (FR Testing)

### FR-DATA-001 基础数据库操作

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_DB_001 | **数据库初始化** | 无 DB 文件 | 启动 Core | 1. 创建 `crawler4j.db`<br>2. WAL 模式开启<br>3. 自动应用 Migrations 创建表 | P0 |
| TC_DB_002 | **连接池管理** | 运行中 | 并发申请 Connection | 能够复用连接，不泄露 | P1 |

### FR-DATA-002 配置存储 (Config Store)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_DB_003 | **配置写入 (Upsert)** | 无或已有值 | `set_config("key", {"a":1})` | DB 中记录更新，JSON 序列化正确 | P0 |
| TC_DB_004 | **配置读取** | 有值 | `get_config("key")` | 返回反序列化后的 dict | P0 |
| TC_DB_005 | **配置读取缺省** | 无值 | `get_config("key", default=0)` | 返回 0 | P1 |

### FR-DATA-003 运行时状态存储 (Runtime State KV)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_DB_006 | **带 TTL 写入** | 无 | `state.set("k", "v", ttl=1)` | 写入成功，expire_at 字段正确 设置 | P0 |
| TC_DB_007 | **未过期读取** | Key 存在且未过期 | `state.get("k")` | 返回 "v" | P0 |
| TC_DB_008 | **已过期读取** | Key 存在但已过期 | `state.get("k")` | 返回 None | P0 |
| TC_DB_009 | **过期数据清理 (GC)** | 存在过期 Key | `state.cleanup()` | count(sys_kv_store) 减少 | P2 |
| TC_DB_010 | **作用域隔离** | 写入 `scope="module:A"` | 读取 `scope="module:B"` | 返回 None，确保不串号 | P1 |

### FR-DATA-004 业务数据采集 (Data Collection)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_DB_011 | **数据写入** | 无 | `data.emit("orders", {id:1})` | `sys_collections` 增加一条记录 | P0 |
| TC_DB_012 | **批量写入** | 无 | `data.emit_batch([...])` | 事务提交，全部写入成功 | P1 |
| TC_DB_013 | **按任务 ID 查询** | 有数据 | `query(task_run_id="abc")` | 仅返回该任务产生的数据 | P1 |

## 3. 非功能需求测试 (NFR Testing)

### NFR-DATA-001 并发性能 (Concurrency)

*   **TC_DB_PERF_001**: 模拟 50 个并发 Task 同时调用 `emit()` 写入大量数据。
    *   验证：不抛出 `sqlite3.OperationalError: database is locked` (依赖 WAL 模式)。
    *   验证：数据完整性 100%。

### NFR-DATA-002 数据类型兼容性 (Serialization)

*   **TC_DB_TYPE_001**: 尝试写入包含 `datetime` 对象的 dict。
    *   验证：存入时自动转 ISO 字符串，或抛出明确的 `SerializationError` (取决于实现约定)。
