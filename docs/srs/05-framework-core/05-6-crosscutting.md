# 5.6 横切关注点 (Cross-cutting Concerns)

## 5.6.1 需求概述

本章定义了所有模块必须共同遵守的非业务性规范，包括可观测性、错误处理模型、线程安全边界及敏感数据治理。

## 5.6.2 可观测性 (Observability)

### FR-OBS-001 结构化日志
- **规范**: 所有日志必须包含上下文键值对。
- **必选字段**: `timestamp`, `level`, `env_id` (如有), `task_id` (如有), `module_name`.
- **脱敏**: 日志输出前必须经过 `LogSanitizer` 处理，屏蔽 `phone`, `password`, `cookies`.

### FR-OBS-002 审计事件
- **事件源**: 环境创建/销毁、任务状态变更、敏感配置修改。
- **存储**: 必须持久化到 SQLite `audit_logs` 表，不可被清理规则轻易删除。

## 5.6.3 错误处理模型 (Error Model)

### FR-ERR-001 错误归一化 (Error Envelope)
- 系统内所有异常必须映射为标准错误码 (Error Code).
- **格式**: `E-{SCOPE}-{TYPE}-{CODE}` (e.g., `E-CORE-ENV-001`).

### FR-ERR-002 恢复策略
- **Transient (临时错误)**: 网络超时、503 -> 指数退避重试。
- **Permanent (永久错误)**: 401/403、配置错误 -> 立即失败，不重试。
- **Critical (严重错误)**: 磁盘满、OOM -> 触发熔断保护。

## 5.6.4 线程与并发安全

### FR-CON-001 UI 线程保护
- **原则**: 耗时操作 (>50ms) **MUST** 在 worker thread 或 asyncio loop 中执行。
- **通信**: Worker -> UI 必须通过 `QtSignal` 或 `qasync.asyncSlot`。

### FR-CON-002 资源锁
- 对 `Environment` 和 `Profile` 的写操作必须加互斥锁。

## 5.6.5 安全与基线

- **模块加载**: 只加载 `verified` 列表中的模块 (生产环境).
- **文件与网络**: 禁止模块访问 `~/.ssh`, `/etc` 等敏感目录 (通过代码扫描+运行时检查).
