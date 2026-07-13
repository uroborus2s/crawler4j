# TASK-040 独立复评反馈分流

来源：`.factory/workitems/CR-020/reviews/TASK-040-independent-rereview.md`

## CR-020-RER-001 pause/resume 共享生命周期锁

- severity：Important
- 理解：`pause_env()`、`resume_env()` 与 ensure、start、stop、recycle、destroy 一样，都是同一环境的生命周期写入口，必须复用同一个 keyed lock。
- 是否清楚：yes
- 技术核实：正确。首轮修复只覆盖了 start/stop/recycle/destroy，pause/resume 仍可能在 ensure 和锁内回绑期间改变环境状态。
- 用户决策冲突：no
- 处理：Fixed。pause/resume 拆为 public 加锁 wrapper 和 private unlocked 实现；共享锁测试同时覆盖 start/stop/pause/resume，并证明锁释放前四类公开入口均不能进入。

## CR-020-RER-002 严格校验运行列表业务响应

- severity：Important
- 理解：严格关闭轮询不能把 HTTP 200 但 `success=false`、缺失 `data` 或不可验证的 `data` 结构解释为浏览器已关闭。
- 是否清楚：yes
- 技术核实：正确。`is_browser_running()` 原实现对 `success=false` 返回 False，对部分无效结构也会返回 False 或抛出非语义异常。
- 用户决策冲突：no
- 处理：Fixed。查询失败和不可验证结构统一抛异常；新增 `success=false` 以及 `data=None/{}/string` 参数化测试。
