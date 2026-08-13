# 会话卡

- 时间：2026-08-13
- Actor：Codex
- 阶段：IMPLEMENTATION
- Work item：`CR-026`
- Task：`TASK-046..048`
- 状态：`committed`

## 项目位置

- 项目整体进度：HubStudio 指纹浏览器支持已完成实现、独立测试、独立复审与本地提交
- 当前任务：新增 HubStudio Provider，并保持旧环境契约和列表结构不变
- 已完成：API Client/Provider、REM/ATM/System/UI 集成、ID 分离、Cookie/缓存/生命周期、状态契约和安全整改
- 正在执行：无
- 停止原因：无
- 唯一下一动作：有本地 HubStudio 客户端、API Key 和可销毁环境时补真实 E2E

## 已读取上下文

- `.factory/workitems/CR-026/brief.md`、`plan.md`、task briefs、ledger、evidence、report、review
- HubStudio 官方 API 文档与官方浏览器状态说明
- REM Provider/Manager/Handle/Model、ATM RunProfile、System Config/ExternalApp、相关 UI 和定向测试

## 未读 / 已排除上下文

- `docs/` 全量正文、其他历史 work item 正文
- 真实 HubStudio 客户端、用户 API Key 和外部环境数据

## 禁止动作

- 不新增 `EnvType`，不修改数据库 schema、公共环境接口或原环境列表列
- 不将运行时 `browserID` 持久化或覆盖稳定 `containerCode`
- 不伪造完整指纹回读与 location 原地修复能力
- 不推送远端、不开 PR

## 证据

- `.factory/workitems/CR-026/evidence/batch-hubstudio.md`
- `.factory/workitems/CR-026/reports/batch-hubstudio.md`
- `.factory/workitems/CR-026/reviews/batch-hubstudio-independent-review.md`
