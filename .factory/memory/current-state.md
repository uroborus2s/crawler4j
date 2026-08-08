# 当前状态

- 更新时间：2026-08-08
- 当前阶段：IMPLEMENTATION
- 当前源码版本：root/runtime `0.4.41`；SDK `0.4.6`；Contracts `0.4.5`（三包新版本未发布）
- 当前协议：Core `0.4.0` / `core-native-v2`

## 当前条目

| ID | 状态 | 下一动作 |
| --- | --- | --- |
| `CR-025` / `TASK-045` | `human_approved_pending_commit` | 使用 gitcommitzh 提交全部 CR-025 变更并推送 `origin/0.4.0` |
| `CR-024` / `TASK-044` | `committed` | none |
| `CR-023` / `TASK-043` | `host_slice_committed` | 外部 ctrip 改接与 Windows 发布门 |
| `TASK-042` | `pypi_published_pending_remote_push` | 最终 evidence commit 并推送 `origin/0.4.0` |
| `CR-022` | `core_packages_released` | none |
| `TASK-039` | `verification_passed` | none |
| `TASK-036` | `CORE_PACKAGES_RELEASED` | 业务模块接线与 E2E |
| `CR-019` / `TASK-038` | `remote_push_done` | none |
| `TASK-037` | `done` | none |

## 最近可复用事实

- `@env_candidates` 支持同步/异步 provider 与 `EnvCandidateResult`；同次 JSON-safe context 通过 `TaskContext.candidate_context` 注入 workflow，候选 surface 仅开放 `http.request`，租约后不重跑 provider。
- 外部模块使用本轮能力的最低源码版本为 Contracts `0.4.5`、SDK `0.4.6`；PyPI 仍分别是 `0.4.4` / `0.4.5`，本轮不发布。
- 承载本轮 Core 能力的根应用 / 客户端源码版本为 `0.4.41`；root wheel/sdist 已本地构建，未构建桌面资产。
- `core-native-v2` 模块 ZIP 会保留非忽略的任意资源；CR-024 使用现有能力携带 Cheese JavaScript，无需新增 Core/SDK 契约或依赖。
- full runtime 已注册异步 `http.request`：模块传有序 headers/raw body/代理/HTTP2 约束，Core 返回标准类型 mapping 并拒绝协议降级；模块不直接使用第三方 HTTP 包。
- root 0.4.40 wheel 隔离安装自动带入 HTTP2/Brotli 依赖；macOS PyInstaller app 已通过冻结 runtime check。签名发布资产和 Windows 证据未完成。
- Hosted UI DataTable 批量编辑的公共契约已支持 `selection_mode=none/single/multi`；Core 传递保序、类型敏感去重的主键数组和表单 payload，业务模块负责校验与 `ctx.db` 写入。
- 行按钮 `open_page` 与整行点击/多选交互已分离；对应实现和测试见 `.factory/workitems/CR-019/`。
- CR-025 最终验证：目标功能+版本/打包 `320 passed`、integration/acceptance `32 passed`、full unit `1287 passed`；Ruff、lock、docs、JSON/diff 通过，两包构建和 Contracts wheel 隔离公开导入通过；独立复评 `100/100`。
- PyPI 已发布 Contracts `0.4.4` 和 SDK `0.4.5`，在线哈希、SDK 依赖元数据与隔离安装通过。

## 当前风险

- CR-025 已 bump 客户端/Contracts/SDK 源码 patch 版本但未发布；外部模块需等待 Contracts `0.4.5` / SDK `0.4.6` 正式发布。
- CR-024 的仓库验证不连接真实设备；Cheese Android 设备 E2E 需要用户在已授权设备上通过官方 IDE 插件运行。
- ctrip 外部模块改接 `http.request`、真实站点 E2E、Windows 真机发布证据和完整 0.4.x 交付批次仍未闭环。
- memory summary 只作恢复索引；需要精确结论时回读 ledger/evidence/docs。

## 事实源

- 项目元数据：`.factory/project.json`
- 工作状态：`.factory/workitems/*/ledger.jsonl`
- 评审与验证：`.factory/workitems/*/{reviews,evidence,reports}/`
- 正式文档映射：`.factory/memory/doc-map.md`
