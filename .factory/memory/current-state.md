# 当前状态

- 更新时间：2026-07-15
- 当前阶段：IMPLEMENTATION
- 当前版本：root/runtime `0.4.39`；SDK `0.4.5` 发布候选；Contracts `0.4.4` 发布候选
- 当前协议：Core `0.4.0` / `core-native-v2`

## 当前条目

| ID | 状态 | 下一动作 |
| --- | --- | --- |
| `TASK-042` | `release_candidate_validated` | 按 Contracts -> SDK 顺序发布、在线验证并推送远端 |
| `CR-022` | `implemented` | 由 TASK-042 发布公共 Contracts / SDK |
| `TASK-039` | `verification_passed` | none |
| `TASK-036` | `CORE_PACKAGES_RELEASED` | 业务模块接线与 E2E |
| `CR-019` / `TASK-038` | `remote_push_done` | none |
| `TASK-037` | `done` | none |

## 最近可复用事实

- Hosted UI DataTable 批量编辑的公共契约已支持 `selection_mode=none/single/multi`；Core 传递保序、类型敏感去重的主键数组和表单 payload，业务模块负责校验与 `ctx.db` 写入。
- 行按钮 `open_page` 与整行点击/多选交互已分离；对应实现和测试见 `.factory/workitems/CR-019/`。
- 当前发布候选验证：unit `1235 passed`，另有 13 项稳定的沙箱/只读数据库环境基线；版本/打包聚焦回归 `175 passed`；root sdist 污染已由 TDD 修复并增加 manifest gate；Ruff、lock、JSON、docs、UI smoke、三包 build、METADATA、哈希、publish dry-run 与 diff check 均通过。
- PyPI 当前已有 Contracts `0.4.3` 和 SDK `0.4.4`；Contracts `0.4.4` / SDK `0.4.5` 待正式上传。客户端源码 `0.4.39` 已完成 root wheel/sdist 构建，桌面包不在本轮范围。

## 当前风险

- 真实站点 E2E、Windows 真机发布证据和完整 0.4.x 交付批次仍未闭环。
- memory summary 只作恢复索引；需要精确结论时回读 ledger/evidence/docs。

## 事实源

- 项目元数据：`.factory/project.json`
- 工作状态：`.factory/workitems/*/ledger.jsonl`
- 评审与验证：`.factory/workitems/*/{reviews,evidence,reports}/`
- 正式文档映射：`.factory/memory/doc-map.md`
