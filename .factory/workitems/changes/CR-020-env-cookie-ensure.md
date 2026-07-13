# CR-020 Core `env.cookie.ensure`

- 状态：READY_FOR_REVIEW
- 类型：CR
- 优先级：P0
- 关联 ID：`CR-020`, `TASK-040`, `API-022`
- 提出日期：2026-07-13

## 变更动机

模块需要在领取业务题目和打开页面前确保 `cticket` 已持久化并进入当前浏览器运行态。环境锁、VirtualBrowser Cookie API、完整重启、CDP 端口释放和 BrowserContext 换代均属于 Core 运行时职责。

## 需求

- full runtime surface 新增异步工具 `env.cookie.ensure`。
- 模块传入完整目标 Cookie 集合；Core 原子编排全量替换、持久化复核、必要重启、CDP 重连和运行态复核，删除所有未传入 Cookie。
- stop/start 后把新 BrowserHandle 的 page/context 回绑到当前 TaskContext 并重新绑定 tools。
- 成功返回至少四个必需布尔值；失败抛异常。

## 非目标

- 不新增模块配置或 manifest 字段。
- 不暴露 VirtualBrowser Provider API。
- 不允许模块持有或继续使用旧 Page。

## 验收标准

以 `.factory/workitems/CR-020/brief.md` 的 `AC-020-001` 至 `AC-020-008` 为准。
