# TASK-045 客户端版本增量评审响应

| Finding | 结论 | 处理 |
| --- | --- | --- |
| shipping 的候选 HTTP surface 旧口径 | 接受 | 明确 `http.request` 可用于 full runtime 与 `@env_candidates` 只读候选面，Hosted UI 声明/只读面仍不可用。 |
| task brief 禁止提交/远端写入 | 接受 | 同步用户已授权提交本任务并推送 `origin/0.4.0`，仍禁止发布。 |
| 当前发布/项目事实混用 CR-023 历史验证 | 接受 | release notes、acceptance checklist、project JSON、release memory 更新为 CR-025 的 `1287/320/32`、当前静态门与三包 build；保留 0.4.40 隔离/桌面和既有 PyPI 版本为历史证据。 |
