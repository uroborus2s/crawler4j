# 系统架构

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 维护者  
**上游输入：** `technical-selection.md` | 现有 `packages/crawler4j/`, `packages/crawler4j-sdk/`, `packages/crawler4j-contracts/`  
**下游输出：** `module-boundaries.md` | `api-design.md` | `docs/04-project-development/05-development-process/implementation-plan.md`  
**关联 ID：** `MOD-001`, `MOD-002`, `MOD-003`, `MOD-004`, `MOD-005`, `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-009`, `TASK-023`  
**最后更新：** 2026-04-19  

## 1. 总体结构

```text
User
  -> PyQt Desktop Shell (`packages/crawler4j/src/ui`)
    -> Core Services (`packages/crawler4j/src/core`)
      -> ATM / MMS / REM / Persistence / Debug / System
        -> Job RunProfile (`packages/crawler4j/src/core/atm/run_profile.py`)
        -> External Modules (`<app-data>/modules`, `DevLink`, `packages/crawler4j/modules/`)
          -> SDK Contracts (`crawler4j_sdk`, `crawler4j_contracts`)

Maintainer
  -> Markdown Docs (`docs/`)
  -> Build / Release (`uv build`, `PyInstaller`, SDK/Contracts build)
  -> Factory Control Plane (`.factory/`)
```

结合当前代码与现行文档，当前可以把系统理解为四个稳定层次：

1. UI Host：桌面外壳、导航、日志与调试入口
2. Framework Core：MMS / ATM / REM / Persistence / Debug / System + Job RunProfile
3. SDK / Contracts：模块开发与运行时契约
4. Modules：外部安装模块与本地 DevLink 模块项目

## 2. 核心运行链

1. `src.ui.app:main` 初始化数据库、日志、事件循环与核心服务；其源码位于 `packages/crawler4j/src/ui/app.py`
2. REM 管理运行环境生命周期与浏览器资源，负责 create/open/connect/stop/destroy，不负责任务工作流编排
3. ATM 负责任务调度、派发、生命周期 hooks 与任务终态收口
4. MMS 负责发现、解析、校验和执行模块
5. 模块通过 `crawler4j_sdk` 暴露任务、工作流，并通过 `TaskSignal` 向 ATM 请求流程动作
6. Contracts 负责 Core 与 SDK 共享数据结构，模块侧通过 `TaskContext.tools` 访问 Core 扩展能力，通过 `TaskContext.runtime` 读取运行态信息

## 3. 依赖方向与边界

结合当前代码，当前边界可归纳为：

- Modules 应优先依赖 SDK / Contracts 暴露的稳定契约
- Core 负责治理与编排，不负责业务语义
- SDK 应保持可独立发布，不应反向绑死 Core 内部实现
- 仓内 `modules/` 当前只保留占位说明；真实模块发现来自应用数据目录和开发链接
- 当前仍存在一处未闭环偏差：真实业务站点 E2E 尚未回放，发布层面的最终确认仍需单独完成

## 4. 当前最重要的架构事实

- Root app package 的真实桌面入口位于 `packages/crawler4j/src/ui/app.py`
- `packages/crawler4j-sdk` 与 `packages/crawler4j-contracts` 已经具备独立包形态
- `TaskContext` 的宿主扩展能力已收敛到 `ctx.tools.call("<namespace>.<action>", **kwargs)` 单入口
- 模块生命周期 hooks 已收敛到 ATM 调度的 `module_runtime.py`；`TaskScript` / `TaskFlow` 本身只保留单入口方法
- `TaskSignal` 已成为模块到 ATM 的正式流程控制通道；等待人工确认、失败后销毁环境等行为不再通过散落回调或 UI 清理策略表达
- 外部模块运行时已收敛到 MMS + ModuleAssembler 单一执行链，不再保留 `src.automation.*` 旧兼容包
- 宿主源码已不再承载业务辅助逻辑或业务模型；酒店匹配、短信平台与本地验证码回退逻辑以模块自带实现为准
- 当前事实以当前代码和验证结果为准，不再保留并行的旧设计正文

## 5. 架构偏差与技术债

### `ARCH-001` 根入口已修复，但需要持续回归

- `start` 脚本、headless smoke、PyInstaller spec 已在 `TASK-002` 中对齐
- 后续仍应保留对应回归，避免入口再次漂移

### `ARCH-002` 模块高阶能力仍未闭环

- `ctrip labor_workflow` 已脱离旧兼容包并回到正式运行时链路，但真实站点 E2E 仍需验证
- MMS 的 settings store、工作流导出、模块状态持久化、trust gate 与自定义页面加载已落地

### `ARCH-003` 版本规则已收口

- 根应用版本以 `packages/crawler4j/pyproject.toml` 为事实源
- 运行时代码通过包元数据或 `packages/crawler4j/pyproject.toml` 读取当前版本
- Git tag 只表示最近正式发布
- SDK / Contracts 保持独立版本线

## 6. 已实现的当前设计（V1）

### ATM 模块资源池等待队列

- 固定环境池的 Service Job 已不再把“当前轮没拿到环境”视为失败，而是把它建模成正式的等待席位。
- ATM 现在按“服务席位”而不是“失败重试实例”维持目标并发；业务口径收口为“运行中 + 等待中 = 目标并发”。
- REM 继续拥有环境生命周期；模块通过宿主可读的资源池资格卡片声明“这个环境当前是否属于本模块的某个资源池、现在能否接单”。
- 宿主只会在“当前模块 + 当前资源池 + 资格有效”的环境集合里分配环境，不再面对全局浏览器池盲抢。
- 叫号与补位由宿主 FIFO 处理；当前已接入任务终态事件、资源池卡片更新事件和轻量定时调和来补位等待席位。

## 7. 说明

- 旧归档文档已删除，避免与当前实现形成双事实源。

## 8. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-26 | 基于当前仓库事实重建总体架构摘要 | Codex |
| 2026-03-26 | 吸收旧总体架构/SRS 的层次与边界结论 | Codex |
| 2026-04-15 | 补记 `TaskContext.tools` 统一工具接口已成为宿主扩展单入口 | Codex |
| 2026-04-15 | 补记 ATM hooks / `TaskSignal` / `WAITING_CONFIRMATION` 已成为正式任务生命周期链 | Codex |
| 2026-04-19 | 新增“ATM 模块资源池等待队列”下一轮架构设计摘要，并明确其为已确认、待实施方案 | Codex |
| 2026-04-19 | 固定环境池 Service Job 的等待队列、资源池资格卡片与 FIFO 补位 V1 已实现 | Codex |
