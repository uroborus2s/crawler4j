# 数据模型：自动化爬虫 GUI

## 数据库: SQLite (`crawler.db`)

## 核心概念

**调度逻辑**:
1. 从携程号码池选择一个状态为 `active` 的账号
2. 检查该账号是否已存在环境 (通过 `environments` 表)
3. **有环境**: 直接启动该环境执行任务
4. **无环境**: 从劳保号码池选择一个状态为 `active` 且未被绑定的账号，创建新环境
5. **携程账号被封/退登**: 删除对应环境，将携程账号状态置为 `blacklisted`

---

### 表: `ctrip_accounts` (携程账号表)

存储携程平台账号池，包含接码平台配置。

| 列名 | 类型 | 约束 | 描述 |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 唯一 ID |
| phone | TEXT | UNIQUE NOT NULL | 登录手机号 |
| password | TEXT | | 登录密码 (可选) |
| status | TEXT | DEFAULT 'active' | 状态: active (正常), blacklisted (已封/置黑), disabled (禁用) |
| sms_platform_url | TEXT | | 接码平台 API 地址 |
| sms_platform_key | TEXT | | 接码平台 API Key |
| sms_platform_type | TEXT | | 接码平台类型 (用于区分不同平台的接口) |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

---

### 表: `labor_accounts` (劳保平台账号表)

存储劳保平台账号池，包含任务统计。

| 列名 | 类型 | 约束 | 描述 |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 唯一 ID |
| phone | TEXT | UNIQUE NOT NULL | 登录手机号/用户名 |
| password | TEXT | NOT NULL | 登录密码 |
| status | TEXT | DEFAULT 'active' | 状态: active (正常), blacklisted (已封), disabled (禁用) |
| completed_count | INTEGER | DEFAULT 0 | 统计: 已完成题数 |
| discarded_count | INTEGER | DEFAULT 0 | 统计: 已废弃题数 |
| approved_count | INTEGER | DEFAULT 0 | 统计: 审核通过数 |
| rejected_count | INTEGER | DEFAULT 0 | 统计: 审核拒绝数 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

---

### 表: `environments` (环境表)

绑定携程账号与劳保账号、浏览器配置的关系表。环境是持久的，复用可保持登录状态。

| 列名 | 类型 | 约束 | 描述 |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 唯一 ID |
| ctrip_account_id | INTEGER | FOREIGN KEY UNIQUE NOT NULL | 关联携程账号 (唯一，一个携程号仅一个环境) |
| labor_account_id | INTEGER | FOREIGN KEY UNIQUE NOT NULL | 关联劳保账号 (唯一) |
| browser_profile_id | TEXT | NOT NULL | 指纹浏览器配置 ID |
| status | TEXT | DEFAULT 'idle' | 运行状态: idle (空闲), running (运行中) |
| last_run_at | DATETIME | | 最后运行时间 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**注意**: 当携程账号被封时，删除该环境记录，释放劳保账号供其他携程账号使用。

---

### 表: `task_logs` (任务日志表)

| 列名 | 类型 | 约束 | 描述 |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| environment_id | INTEGER | FOREIGN KEY | 关联环境 ID |
| level | TEXT | | INFO, ERROR, WARNING |
| message | TEXT | | 日志内容 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | |

---

### 表: `settings` (设置表)

| 列名 | 类型 | 约束 | 描述 |
|--------|------|-------------|-------------|
| key | TEXT | PRIMARY KEY | 配置键名 |
| value | TEXT | | JSON 序列化的值 |

**预设键值**:
- `browser_type`: `bitbrowser` 或 `virtualbrowser`
- `browser_api_url`: 如 `http://127.0.0.1:54345`
- `concurrency_limit`: 最大并发数

---

## 调度流程图

```
┌─────────────────────────────────────────────────────────────┐
│                      开始调度                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  从 ctrip_accounts 选择 status='active' 的账号              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  查询 environments 表: 该账号是否已有环境?                   │
└─────────────────────────────────────────────────────────────┘
                      │               │
                      ▼ (有)          ▼ (无)
           ┌──────────────────┐  ┌───────────────────────────┐
           │ 启动已有环境     │  │ 选择 status='active' 且   │
           │ 执行任务         │  │ 未绑定的 labor_account    │
           └──────────────────┘  │ 创建新环境并执行任务      │
                      │          └───────────────────────────┘
                      ▼                       │
           ┌──────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│  执行任务 (登录 → 领题 → 搜索 → 提交)                        │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼ (成功)                        ▼ (携程被封/退登)
┌─────────────────────────┐    ┌─────────────────────────────┐
│ 更新劳保账号统计        │    │ 删除环境                    │
│ 环境 status='idle'     │    │ 携程账号 status='blacklisted'│
└─────────────────────────┘    └─────────────────────────────┘
```
