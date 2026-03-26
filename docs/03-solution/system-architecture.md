# 系统架构

**项目名称：** crawler4j  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 维护者  
**上游输入：** `technical-selection.md` | 现有 `src/`, `modules/`, `crawler4j_sdk/`, `crawler4j_contracts/`  
**下游输出：** `module-boundaries.md` | `api-design.md` | `docs/04-delivery/implementation-plan.md`  
**关联 ID：** `MOD-001`, `MOD-002`, `MOD-003`, `MOD-004`, `MOD-005`, `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`  
**最后更新：** 2026-03-26  

## 1. 总体结构

```text
User
  -> PyQt Desktop Shell (`src/ui`)
    -> Core Services (`src/core`)
      -> ATM / TSM / MMS / REM / Persistence / Debug / System
        -> Builtin Modules (`modules/*`)
          -> SDK Contracts (`crawler4j_sdk`, `crawler4j_contracts`)

Maintainer
  -> Markdown Docs (`docs/`)
  -> Build / Release (`uv build`, `PyInstaller`, SDK/Contracts build)
  -> Factory Control Plane (`.factory/`)
```

结合旧 `SRS` 与旧总体设计文档，当前可以把系统理解为四个稳定层次：

1. UI Host：桌面外壳、导航、日志与调试入口
2. Framework Core：MMS / TSM / ATM / REM / Persistence / Debug / System
3. SDK / Contracts：模块开发与运行时契约
4. Modules：业务模块与外部开发项目

## 2. 核心运行链

1. `src.ui.app:main` 初始化数据库、日志、事件循环与核心服务
2. REM 管理运行环境与浏览器资源
3. ATM 负责任务调度、派发与执行
4. MMS 负责发现、解析、校验和执行模块
5. 模块通过 `crawler4j_sdk` 暴露任务、工作流与 hooks
6. Contracts 负责 Core 与 SDK 共享数据结构

## 3. 依赖方向与边界

结合旧 `docs/02-requirements/reference-srs/04-architecture.md` 与当前代码，当前边界可归纳为：

- Modules 应优先依赖 SDK / Contracts 暴露的稳定契约
- Core 负责治理与编排，不负责业务语义
- SDK 应保持可独立发布，不应反向绑死 Core 内部实现
- 当前仍存在一处未闭环偏差：MMS 已补齐 settings store 与模块状态持久化，但 UI trust gate / 自定义页面加载仍只完成了部分设计目标
## 4. 当前最重要的架构事实

- Root package 的真实桌面入口已经迁移到 `src/ui/app.py`
- `crawler4j_sdk` 与 `crawler4j_contracts` 已经具备独立包形态
- 外部 `ctrip` 模块已恢复基础兼容运行时，不再因旧导入缺失直接退化
- 旧文档中的 SRS / 设计文档仍有参考价值，但必须以当前代码和验证结果校准

## 5. 架构偏差与技术债

### `ARCH-001` 根入口已修复，但需要持续回归

- `start` 脚本、headless smoke、PyInstaller spec 已在 `TASK-002` 中对齐
- 后续仍应保留对应回归，避免入口再次漂移

### `ARCH-002` 模块高阶能力仍未闭环

- `ctrip labor_workflow` 已恢复基础运行时兼容，但真实站点 E2E 仍需验证
- MMS 的 settings store、工作流导出与模块状态持久化已落地
- MMS 的模块自定义 UI 加载和 trust gate 仍未达成完整设计目标

### `ARCH-003` 版本规则已收口

- 根应用工作区版本以根 `pyproject.toml` 为事实源
- `src/__version__.py` 只做运行时镜像
- Git tag 只表示最近正式发布
- SDK / Contracts 保持独立版本线

## 6. 参考深度文档

- 旧 SRS：`docs/02-requirements/reference-srs/`
- 旧技术设计：`docs/03-solution/reference-design/`
- 旧测试设计：`docs/05-quality/reference-tests/`
- SDK 细节：`docs/03-solution/reference-sdk/`

这些文档在需要深挖某一模块时按需读取，不作为当前阶段的唯一事实源。

## 7. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-26 | 基于当前仓库事实重建总体架构摘要 | Codex |
| 2026-03-26 | 吸收旧总体架构/SRS 的层次与边界结论 | Codex |
