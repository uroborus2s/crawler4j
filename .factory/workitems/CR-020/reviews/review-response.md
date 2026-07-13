# TASK-040 Review Response

来源：`.factory/workitems/CR-020/reviews/TASK-040-independent-review.md`

## 独立复评补充

首次 response 对 `CR-020-REV-001/002` 的修复范围判断不完整。第二位独立 reviewer 指出 pause/resume 未进入共享锁，且运行列表 `success=false` 仍会被解释为已停止。两项均已接受并按 `.factory/workitems/CR-020/reviews/rereview-feedback-triage.md` 修复；验证见 `.factory/workitems/CR-020/evidence/rereview-fix-verification.md`。

## Fixed

### CR-020-REV-001 共享生命周期锁与锁内回绑

Fixed. 生命周期锁 owner 移到 `EnvironmentManager`；普通 `start_env/stop_env` 和 Cookie ensure 使用同一个 keyed lock。Service 在锁内调用 unlocked 生命周期方法，并在返回前执行 ATM 提供的 `on_ready` callback，稳定取得 BrowserHandle 并完成 TaskContext/tools 回绑。

Verified:

- 外部生命周期竞争测试：回绑 callback 释放前 `external_stop` 不能进入。
- 取消测试：callback 中取消后共享锁已释放，后续 ensure 可完成。
- Manager wrapper 测试：`7` 与 `"7"` 的 start/stop 使用同一锁。

### CR-020-REV-002 严格关闭状态

Fixed. `_wait_until_window_closed()` 改用不吞异常的严格运行态查询；Management API 查询异常直接失败。旧 CDP 端口轮询 20 次仍可达时抛异常，不替换旧 handle。

Verified:

- 查询异常测试：Provider close 抛异常，旧 handle 保留。
- CDP 耗尽测试：20 次运行列表确认和端口探测后失败。

### CR-020-REV-003 Core 异常边界

Fixed. Service 对持久化读取、全量写入和写后复核分别转换为稳定 Core 异常，并使用 `from None` 阻止 Provider endpoint 与敏感 cause 穿透模块边界。

Verified:

- 读/写两条参数化测试断言异常不含 `VirtualBrowser`、`updateCookie`、API Key 或 Cookie value。
- Client 失败测试断言未产生 error/warning 日志。

### CR-020-REV-004 有效期严格比较

Fixed. 有效期改为 float 严格相等，删除 1 秒容差。

Verified:

- `+0.1s` 与 `+1.0s` 均判为不匹配。

### CR-020-REV-005 失败与空集合测试

Fixed. 新增空列表实际清空、stop 失败、start 失败、重启后运行态不匹配、取消释放、外部竞争、查询异常、CDP 耗尽和日志安全测试。

Verified:

- review 修复目标集：`118 passed in 2.65s`。
- REM/ATM 相邻回归：`513 passed in 14.85s`。
- 完整 unit：`1187 passed in 29.53s`。

### CR-020-REV-006 锁表增长

Fixed. Manager 使用 `WeakValueDictionary` 保存 keyed locks；活跃调用持有强引用，空闲且无调用引用的锁可回收。
