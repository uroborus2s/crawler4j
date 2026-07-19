# 当前状态

- 更新时间：2026-07-19
- 当前阶段：IMPLEMENTATION
- 当前版本：root/runtime `0.4.40`；SDK `0.4.5` 已发布；Contracts `0.4.4` 已发布
- 当前协议：Core `0.4.0` / `core-native-v2`

## 当前条目

| ID | 状态 | 下一动作 |
| --- | --- | --- |
| `CR-023` / `TASK-043` | `host_slice_committed` | 外部 ctrip 改接与 Windows 发布门 |
| `TASK-042` | `pypi_published_pending_remote_push` | 最终 evidence commit 并推送 `origin/0.4.0` |
| `CR-022` | `core_packages_released` | none |
| `TASK-039` | `verification_passed` | none |
| `TASK-036` | `CORE_PACKAGES_RELEASED` | 业务模块接线与 E2E |
| `CR-019` / `TASK-038` | `remote_push_done` | none |
| `TASK-037` | `done` | none |

## 最近可复用事实

- full runtime 已注册异步 `http.request`：模块传有序 headers/raw body/代理/HTTP2 约束，Core 返回标准类型 mapping 并拒绝协议降级；模块不直接使用第三方 HTTP 包。
- root 0.4.40 wheel 隔离安装自动带入 HTTP2/Brotli 依赖；macOS PyInstaller app 已通过冻结 runtime check。签名发布资产和 Windows 证据未完成。
- Hosted UI DataTable 批量编辑的公共契约已支持 `selection_mode=none/single/multi`；Core 传递保序、类型敏感去重的主键数组和表单 payload，业务模块负责校验与 `ctx.db` 写入。
- 行按钮 `open_page` 与整行点击/多选交互已分离；对应实现和测试见 `.factory/workitems/CR-019/`。
- 当前 0.4.40 宿主候选验证：unit `1265 passed`，CR-023 定向/邻近 `152 passed`；Ruff、lock、JSON、docs 和 diff check 通过；root wheel/sdist、隔离 wheel 安装与 macOS arm64 PyInstaller runtime 诊断通过。
- PyPI 已发布 Contracts `0.4.4` 和 SDK `0.4.5`，在线哈希、SDK 依赖元数据与隔离安装通过。

## 当前风险

- ctrip 外部模块改接 `http.request`、真实站点 E2E、Windows 真机发布证据和完整 0.4.x 交付批次仍未闭环。
- memory summary 只作恢复索引；需要精确结论时回读 ledger/evidence/docs。

## 事实源

- 项目元数据：`.factory/project.json`
- 工作状态：`.factory/workitems/*/ledger.jsonl`
- 评审与验证：`.factory/workitems/*/{reviews,evidence,reports}/`
- 正式文档映射：`.factory/memory/doc-map.md`
