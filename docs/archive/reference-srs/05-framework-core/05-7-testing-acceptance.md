# 5.7 测试规格与验收标准 (Testing & Acceptance)

## 5.7.1 测试分层策略

### Unit Testing (单元测试)
- **范围**: Utility functions, Model serialization, State machine transitions.
- **覆盖率目标**: 核心模块 > 80%.

### Integration Testing (集成测试)
- **范围**: `TaskRunner` -> `TaskContext` -> `Browser` (Headless).
- **环境**: 使用 Mock Server 模拟目标网站，测试登录、重试逻辑。

### E2E Testing (端到端测试)
- **范围**: 完整启动 UI，加载真实 Module，执行一次完整任务。
- **关键路径**: 启动 -> 任务排队 -> 环境分配 -> 执行 -> 结果持久化 -> UI 更新。

## 5.7.2 验收矩阵 (Acceptance Matrix)

| 功能点 | 验收标准 | 验证方式 |
|--------|----------|----------|
| **环境治理** | 任务结束后 30s 内无残留 Chrome 进程 | 脚本扫描进程表 |
| **崩溃恢复** | 强制 Kill 主进程后重启，能识别并标记上次未完成的任务 | 故障注入测试 |
| **长时间运行** | 连续运行 24h，内存泄漏 < 100MB | 压力测试 |
| **UI 响应** | 高频日志下 (100条/s) UI 无卡顿 (>30fps) | 性能测试 |

## 5.7.3 故障注入 (Chaos Engineering)

- **网络中断**: 模拟 DNS 失败，验证重试逻辑。
- **浏览器崩溃**: 模拟 CDP 断开，验证 `TaskResult` 是否为 Failure 且环境被标记为 Unhealthy。
