# 任务摘要

更新时间：2026-07-15。只保留活跃、最近关闭和有后续动作的任务。

## 需要后续动作

- `TASK-042`：Contracts 0.4.4 / SDK 0.4.5 / 客户端 0.4.39 发布候选已通过构建、dry-run 和发布前 gate；待 PyPI 正式上传、在线哈希/隔离安装验证、最终提交和 `origin/0.4.0` 推送。
- `CR-022`：Hosted UI Form 能力、共享 label/input 网格和隐藏式滚动条已完成实现、TDD、独立 review 与本地提交；由 `TASK-042` 负责包发布。
- `CR-021`：公共下拉、移除随机 IP、VirtualBrowser 清缓存和指纹浏览器 ID 列已实现；修复两项独立评审反馈后以 `94/100` 通过复评，待本地中文提交。
- `TASK-036-managed-dataset-bulk-field-update`：`CORE_PACKAGES_RELEASED`；接入真实业务模块并补 E2E。
- `TASK-039-bump-client-0.4.30-and-push`：历史 `verification_passed`；当前客户端版本由 `TASK-042` 推进到 0.4.39，桌面包和跨平台发布仍另行处理。
- 0.4.x 发布收口：补齐 `ctrip` 真实站点 E2E、Windows 真机证据、Git tag / GitHub release 资产和正式交付批次。

## 最近已关闭

- `CR-020` / `TASK-040`：`env.cookie.ensure` 已通过真实接口探针、`1191` 完整单测和 `99/100` 独立复评，本地提交 `afae0136`；真实携程业务模块 E2E 由模块侧后续接线。
- `TASK-037-release-contracts-0.4.3-sdk-0.4.4`：Contracts / SDK 已发布并完成安装验证。
- `CR-019` / `TASK-038`：行按钮 `open_page` 已推送到 `origin/0.4.0`。
- `TASK-035`：VirtualBrowser 创建期随机指纹调整已完成聚焦验证。
- `TASK-0402` 至 `TASK-0409`：0.4.0 v2 装饰器、scanner、CLI、descriptor、对象装配、data、page action 主链已完成各自阶段工作；精确状态以对应 task ledger 为准。

历史任务清单不再复制在本文件；完整索引在 `.factory/workitems/`。
