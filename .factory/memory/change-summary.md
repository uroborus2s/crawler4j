# 变更摘要

更新时间：2026-07-15。这里只保留最近可影响后续工作的变更，不再保存逐条历史日志。

- 2026-07-15：CR-022 完成 Hosted UI 公共字段 change、安全 Form Handle、通用 `ui.form.reset`、精确 create/update 初始化、长表单滚动和 1–3 列响应式布局；Contracts 0.4.4 / SDK 0.4.5 发布候选已完成构建与 dry-run，消费侧本地 editable 联调通过。证据：`.factory/workitems/CR-022/`、`.factory/workitems/TASK-042/`。
- 2026-07-15：客户端 / Core 源码提升到 0.4.39，SDK 对 Contracts 的依赖下限同步到 0.4.4；三包 wheel/sdist 与发布前 gate 通过。
- 2026-07-15：修复 root build 暂存 desktop bundle 时污染 Hatch sdist 的问题；暂存目录移出 package root，并增加拒绝 sdist 含 preserved desktop content 的发布 gate。
- 2026-07-15：Contracts 0.4.4 与 SDK 0.4.5 已按依赖顺序发布到 PyPI；在线 wheel/sdist 哈希、SDK Contracts 下限和隔离安装通过。
- 2026-07-15：CR-022 renderer 增补同逻辑列共享 label/input 物理列；标签右对齐，输入框统一左边缘并横向扩展；label/input 内部间距与声明式逻辑列 gap 分离，避免超大 gap 降为单列后把控件推出 viewport，同时保留宽屏合法 gap；不改变 schema。证据：`.factory/workitems/CR-022/evidence/shared-form-columns-tdd.md`。
- 2026-07-15：CR-022 renderer 长 Form 改为隐藏水平/垂直原生滚动槽，保留键盘、触控板/滚轮和程序化滚动以及固定按钮区；不改变 schema。证据：`.factory/workitems/CR-022/evidence/hidden-form-scrollbar-final-verification.md`。
- 2026-07-13：Core full runtime 新增 `env.cookie.ensure`，模块传入完整 Cookie 目标集合，Core 负责全量替换、必要重启、严格运行态验证和 TaskContext/tools 回绑；VirtualBrowser 实测证明未传 Cookie 会被删除，空列表会清空。提交：`afae0136`；证据：`.factory/workitems/CR-020/`。
- 2026-07-10：客户端源码版本统一到 `0.4.30`；根包、嵌入 README、构建元数据和发布文档已完成一致性验证。证据：`.factory/workitems/TASK-039/evidence/verification.md`。
- 2026-07-10：Contracts `0.4.3` 与 SDK `0.4.4` 完成构建、发布、PyPI 哈希和隔离安装验证。证据：`.factory/workitems/implementation/TASK-037-release-contracts-0.4.3-sdk-0.4.4.md` 及 TASK-037 ledger。
- 2026-07-10：Hosted UI DataTable 批量编辑公共能力完成 review、人工确认和发布；业务模块接线与 E2E 未完成。索引：`.factory/workitems/CR-018/`、`.factory/memory/cr-019.summary.md`。
- 2026-07-10：Hosted UI 行按钮 `open_page` 完成实现、验证、提交和远端推送。索引：`.factory/workitems/CR-019/`。

## 历史与回源

- 旧任务、旧变更和完整时间线以 `.factory/workitems/`、`.factory/memory/history/`、正式 `docs/` 和 Git 历史为准。
- 本文件不是变更事实源；不要为了补背景而把历史条目重新复制回来。
