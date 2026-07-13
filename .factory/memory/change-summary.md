# 变更摘要

更新时间：2026-07-13。这里只保留最近可影响后续工作的变更，不再保存逐条历史日志。

- 2026-07-13：Core full runtime 新增 `env.cookie.ensure`，模块传入完整 Cookie 目标集合，Core 负责全量替换、必要重启、严格运行态验证和 TaskContext/tools 回绑；VirtualBrowser 实测证明未传 Cookie 会被删除，空列表会清空。提交：`afae0136`；证据：`.factory/workitems/CR-020/`。
- 2026-07-10：客户端源码版本统一到 `0.4.30`；根包、嵌入 README、构建元数据和发布文档已完成一致性验证。证据：`.factory/workitems/TASK-039/evidence/verification.md`。
- 2026-07-10：Contracts `0.4.3` 与 SDK `0.4.4` 完成构建、发布、PyPI 哈希和隔离安装验证。证据：`.factory/workitems/implementation/TASK-037-release-contracts-0.4.3-sdk-0.4.4.md` 及 TASK-037 ledger。
- 2026-07-10：Hosted UI DataTable 批量编辑公共能力完成 review、人工确认和发布；业务模块接线与 E2E 未完成。索引：`.factory/workitems/CR-018/`、`.factory/memory/cr-019.summary.md`。
- 2026-07-10：Hosted UI 行按钮 `open_page` 完成实现、验证、提交和远端推送。索引：`.factory/workitems/CR-019/`。

## 历史与回源

- 旧任务、旧变更和完整时间线以 `.factory/workitems/`、`.factory/memory/history/`、正式 `docs/` 和 Git 历史为准。
- 本文件不是变更事实源；不要为了补背景而把历史条目重新复制回来。
