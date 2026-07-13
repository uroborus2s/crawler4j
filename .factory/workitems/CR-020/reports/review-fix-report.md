# TASK-040 Review Fix Report

## 状态

独立评审列出的 5 个 Important 和 1 个 Minor 已全部处理，当前状态重新进入 `ready_for_review`。

## 架构修正

- 生命周期锁从 Cookie Service 私有锁提升为 EnvironmentManager 共享锁。
- Manager public start/stop 获取锁；Cookie Service 在已持锁状态调用 private unlocked 实现，避免重入死锁。
- ATM 通过内部 callback 在锁释放前回绑 page/context 和 tools，消除 handle 换代竞态。
- 锁 registry 使用弱引用，避免按历史 env_id 永久增长。

## Fail-closed 修正

- 严格关闭轮询不再复用吞异常的宽松状态查询。
- Management API 状态未知、CDP 端口轮询耗尽、stop/start/运行态验证失败均直接失败。
- Provider 读写异常在 REM Service 边界转换为不含 endpoint 与敏感详情的 Core 异常。
- 有效期按实测可保持的 float Unix seconds 严格比较。

## 新增回归

- 空集合 ensure 清空全部 Cookie 并重启。
- 普通生命周期操作与 ensure/rebind 的锁竞争。
- callback 取消后的锁释放。
- stop/start/runtime 三类失败。
- Management API 查询失败与 CDP 轮询耗尽。
- Provider/API Key/Cookie value 的异常和日志安全。

验证见 `.factory/workitems/CR-020/evidence/review-fix-verification.md`。
