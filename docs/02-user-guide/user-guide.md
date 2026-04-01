# 接手入口

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 新维护者 | Core 开发 | 模块开发者
**上游输入：** `docs/04-project-development/08-operations-maintenance/core-maintainer-guide.md` | `docs/03-developer-guide/index.md`
**下游输出：** 后续交接文档与角色阅读路径 | `admin-guide.md`
**关联 ID：** `DOC-001`, `DOC-002`, `REQ-005`
**最后更新：** 2026-04-02

## 1. 你应该去哪里

### Core 维护者

请先读：

1. [文档地图](../01-getting-started/document-map.md)
2. [Core 接手与日常维护](../04-project-development/08-operations-maintenance/core-maintainer-guide.md)
3. [当前真实状态分析](../04-project-development/02-discovery/current-state-analysis.md)
4. [实施方案](../04-project-development/05-development-process/implementation-plan.md)
5. [质量门与文档导航规则](../04-project-development/06-testing-verification/quality-gates.md)

### 模块开发者

请直接读 [开发者指南总览](../03-developer-guide/index.md)。

### 管理员 / 实施者

如果你负责部署、初始化、模块安装、验收或现场支持，请按下面顺序继续：

1. [管理员指南](./admin-guide.md)
2. [安装说明](./installation.md)
3. [配置说明](./configuration.md)
4. [部署与运行说明](../04-project-development/08-operations-maintenance/deployment-guide.md)

### 宿主使用者 / 协作者

如果你的目标是安装、配置并使用宿主应用，而不是修改 Core 或开发模块，请按下面顺序继续：

1. [安装说明](./installation.md)
2. [配置说明](./configuration.md)
3. [使用说明](./usage.md)

## 2. 当前结构说明

- 正式文档入口已收敛为 `docs/01-getting-started/`、`docs/02-user-guide/`、`docs/03-developer-guide/`、`docs/04-project-development/` 四大模块。
- `docs/02-user-guide/` 现在承担“接手入口 + 安装 + 配置 + 使用说明 + 管理员说明”的完整用户侧文档角色。
- Core 维护入口位于 `docs/04-project-development/08-operations-maintenance/core-maintainer-guide.md`。
- 第三部分 `docs/03-developer-guide/` 本身就是 module 开发指南，不再保留 `module-developer-guide/` 这一层中间目录。
- `docs/project-process/` 与 `docs/model-development/` 已退出正式入口，避免重复维护导航。
- 旧归档文档已删除，避免与当前实现形成冲突事实源。

## 3. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-02 | 新增管理员/实施者阅读路径，并接入 `admin-guide.md` | Codex |
| 2026-03-30 | 增加宿主使用者/协作者阅读路径，并接入安装、配置、使用说明 | Codex |
| 2026-03-28 | 改为四大模块结构下的跨角色接手入口，并移除旧过渡顶层入口 | Codex |
| 2026-03-26 | 初始接手指南 | Codex |
