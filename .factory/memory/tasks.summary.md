# 任务摘要

更新时间：2026-08-14。只保留活跃、最近关闭和有后续动作的任务。

## 需要后续动作

- `CR-025` / `TASK-045`：Core/SDK/Contracts 的同步/异步环境候选、结构化 context、单次计算注入、候选 HTTP surface、scanner/manifest 与文档已实现；客户端/Contracts/SDK 版本为 `0.4.41` / `0.4.5` / `0.4.6`，三包构建、完整验证与客户端增量复评 `99/100` 通过；PR #58 已合并 `main`，Contracts / SDK 已按依赖顺序发布到 PyPI。
- `CR-024` / `TASK-044`：Cheese `core-native-v2` 示例模块、Android 设置页冒烟脚本和 ZIP 资源回归已实现；定向 `1 passed`、SDK 模块端到端 `12 passed`，full/package verify、Node 语法和 Ruff 通过；独立评审 `100/100`，已提交 `f17b73b9`。
- `CR-023` / `TASK-043`：root 0.4.40 已实现 `API-024 http.request` 与宿主 HTTP2/Brotli 依赖；定向 `152 passed`、全量 `1265 passed`，wheel 隔离安装和 macOS PyInstaller runtime smoke 通过；独立复评 `100/100`，宿主切片已中文本地提交。外部 ctrip 模块接线/真实 E2E、Windows smoke 为后续 gate。
- `TASK-042`：Contracts 0.4.4 / SDK 0.4.5 已发布并通过在线哈希、依赖元数据和隔离安装验证；客户端 0.4.39 已构建；待最终 evidence commit 和 `origin/0.4.0` 推送。
- `CR-022`：Hosted UI Form 能力、共享 label/input 网格和隐藏式滚动条已完成实现、TDD、独立 review 与本地提交；由 `TASK-042` 负责包发布。
- `CR-021`：公共下拉、移除随机 IP、VirtualBrowser 清缓存和指纹浏览器 ID 列已实现；修复两项独立评审反馈后以 `94/100` 通过复评，待本地中文提交。
- `TASK-036-managed-dataset-bulk-field-update`：`CORE_PACKAGES_RELEASED`；接入真实业务模块并补 E2E。
- `TASK-039-bump-client-0.4.30-and-push`：历史 `verification_passed`；当前客户端版本由 `TASK-043` 推进到 0.4.40，签名桌面升级包和跨平台发布仍另行处理。
- 0.4.x 发布收口：补齐 `ctrip` 真实站点 E2E、Windows 真机证据、Git tag / GitHub release 资产和正式交付批次。

## 最近已关闭

- `CR-026` / `TASK-046..048`：HubStudio 指纹浏览器已接入 Provider registry、REM/ATM/System/UI，稳定 `containerCode` 与缓存 `browserID` 分离；有效代理创建会强制语言和地理位置跟随 IP，不改 DB/EnvType/原环境列。原批次 `167 passed`，补充契约 `17 passed`，Ruff、diff-check、双导入探针和独立复审通过；真实 HubStudio E2E 留待具备可销毁环境时执行。
- `CR-020` / `TASK-040`：`env.cookie.ensure` 已通过真实接口探针、`1191` 完整单测和 `99/100` 独立复评，本地提交 `afae0136`；真实携程业务模块 E2E 由模块侧后续接线。
- `TASK-037-release-contracts-0.4.3-sdk-0.4.4`：Contracts / SDK 已发布并完成安装验证。
- `CR-019` / `TASK-038`：行按钮 `open_page` 已推送到 `origin/0.4.0`。
- `TASK-035`：VirtualBrowser 创建期随机指纹调整已完成聚焦验证。
- `TASK-0402` 至 `TASK-0409`：0.4.0 v2 装饰器、scanner、CLI、descriptor、对象装配、data、page action 主链已完成各自阶段工作；精确状态以对应 task ledger 为准。

历史任务清单不再复制在本文件；完整索引在 `.factory/workitems/`。
