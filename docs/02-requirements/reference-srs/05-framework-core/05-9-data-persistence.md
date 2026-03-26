# 5.9 数据持久化与状态管理 (Data Persistence & State Management)

## 5.9.1 存储架构概览

Crawler4j 采用 **嵌入式 SQLite** 作为默认的核心存储引擎，以确保部署的轻量化与零依赖。同时也支持通过接口适配 PostgreSQL/MySQL（企业版扩展）。

### 存储分层模型

系统数据分为三类，分别存储：

| 数据类型 | 典型内容 | 存储位置 | 特性 | 访问方式 |
| :--- | :--- | :--- | :--- | :--- |
| **配置数据 (Configuration)** | 全局设置、模块 Config Schema数据、账号列表(初始) | `auth.db` / `config` 表 | **读多写少**<br>结构化 JSON | 仅 Admin via UI 修改<br>Module 只读 |
| **运行时状态 (Runtime State)** | **账号Cookies**、Token、Session、环境Lease状态 | `state.db` / `kv_store` 表 | **高频读写**<br>键值对 (KV) | Module via SDK `ctx.storage` 读写 |
| **业务数据 (Business Data)** | 抓取的订单信息、商品详情 | `data.db` / `collections` 表 | **只写/批量读**<br>Schema-less | Module via SDK `ctx.emit` |

---

## 5.9.2 模块配置存储 (Module Configuration)

当用户在 **[UI-19] 模块全局配置页** 保存配置时：

1.  UI 将表单数据序列化为 JSON。
2.  Core 接收并校验 Schema。
3.  Core 将 JSON 存入 `config` 表，Key 为 `module:{module_name}:config`。
    *   *SQL 示例*: `INSERT INTO configs (key, value, updated_at) VALUES ('module:ctrip:config', '{"account_pool": [...]}', NOW())`
4.  **快照机制**: 任务启动时，Core 会将当前的配置快照 (Snapshot) copy 一份到任务 Context 中，确保任务执行期间配置不变。

---

## 5.9.3 动态状态管理 (Dynamic State Management)

针对“携程账号登录状态保持”这类场景，不能修改静态配置，必须使用 **SDK 状态存储 API**。

### 场景推演：携程账号池状态维护

1.  **初始化**:
    *   用户在 [配置页] 录入 100 个账号密码。
    *   数据存入 `Configs` 表。

2.  **登录执行**:
    *   Module 代码读取 Config 中的账号 (User A)。
    *   执行登录动作 -> 成功 -> 获取 Cookies。

3.  **状态持久化 (关键步骤)**:
    *   Module 调用 SDK: `ctx.storage.state.set("account:user_a:cookies", cookie_dict, ttl=3600*24)`
    *   Core 将数据写入 `kv_store` 表。

4.  **后续任务复用**:
    *   新任务启动 -> Module 检查 `ctx.storage.state.get("account:user_a:cookies")`。
    *   若存在且有效 -> `ctx.browser.add_cookies(cookies)` -> 直接进入订单页 (跳过登录)。
    *   若失效 -> 重新走第2步登录流程。

## 5.9.4 SDK 存储接口规范

```python
class StorageAPI:
    """ctx.storage"""
    
    @property
    def config(self) -> dict:
        """[只读] 获取当前模块的静态全局配置"""
        pass

    @property
    def state(self) -> KeyValueStore:
        """[读写] 运行时状态存储 (KV)
        适用于: Cookies, Tokens, 指纹Offset, 增量游标
        """
        pass

    @property
    def data(self) -> CollectionStore:
        """[只写] 业务数据存储
        适用于: 抓取结果
        """
        pass
```
