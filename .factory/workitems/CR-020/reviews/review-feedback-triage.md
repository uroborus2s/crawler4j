# TASK-040 Review Feedback Triage

来源：`.factory/workitems/CR-020/reviews/TASK-040-independent-review.md`

## CR-020-REV-001 共享环境生命周期锁与原子回绑

- severity：Important
- 理解：锁必须由 REM/Manager 共享给 ensure 与普通 start/stop，并把稳定 handle 取得和 TaskContext/tools 回绑放在锁释放前。
- 是否清楚：yes
- 技术核实：正确。当前 Service 私有锁不能阻止 Manager 的外部生命周期操作，回绑也发生在锁外。
- 用户决策冲突：no
- 处理：Fixed。Manager 持有 keyed lock；start/stop 使用同一锁；ensure 在锁内调用 unlocked 生命周期方法，并通过内部 callback 在锁内回绑。
- 验证：新增外部生命周期竞争和回绑顺序测试。

## CR-020-REV-002 严格关闭不得把查询失败视为已关闭

- severity：Important
- 理解：严格 wait 路径必须让运行列表查询异常直接失败，不能复用宽松 `_is_window_open_unlocked()`。
- 是否清楚：yes
- 技术核实：正确。当前宽松方法捕获异常返回 False，会把“未知”当“未运行”。
- 用户决策冲突：no
- 处理：Fixed。新增严格查询方法；关闭 wait 使用严格方法；增加查询异常与轮询耗尽测试。

## CR-020-REV-003 Core 异常不得泄漏 Provider/API 名称

- severity：Important
- 理解：Provider adapter 可以内部使用 endpoint 名称，但模块可见异常必须转换为稳定 Core 语义且不保留敏感 cause。
- 是否清楚：yes
- 技术核实：正确。当前 Provider RuntimeError 会穿透 `env.cookie.ensure`。
- 用户决策冲突：no
- 处理：Fixed。Service 在持久化读写边界转换异常，测试断言不含 VirtualBrowser、endpoint、API Key 和 Cookie value。

## CR-020-REV-004 有效期严格比较

- severity：Important
- 理解：实测支持 float 原值持久化，因此没有依据保留 1 秒容差。
- 是否清楚：yes
- 技术核实：正确。当前容差可能跳过必要替换。
- 用户决策冲突：no
- 处理：Fixed。改为 float 严格相等，补亚秒和 1 秒差异测试。

## CR-020-REV-005 关键失败与空集合测试

- severity：Important
- 理解：补 ensure 空列表、stop/start/runtime 失败、取消后锁释放、严格轮询异常/耗尽和日志安全测试。
- 是否清楚：yes
- 技术核实：正确。当前测试覆盖主成功链，但不足以证明所有 fail-closed 语义。
- 用户决策冲突：no
- 处理：Fixed。按反馈逐项补测试并运行目标、相邻和全量验证。

## CR-020-REV-006 锁表增长

- severity：Minor
- 理解：避免按历史 env_id 永久保留锁。
- 是否清楚：yes
- 技术核实：正确但非当前规模阻塞；锁 owner 调整后可低成本处理。
- 处理：Fixed。Manager 使用弱引用 keyed lock registry，空闲且无调用引用的锁可回收。
