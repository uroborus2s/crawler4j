---
title: crawler4j
mkdocs:
  home_access: public
  nav:
    - title: 入门说明
      children:
        - title: 概览
          path: 01-getting-started/index.md
          access: public
        - title: 项目概览
          path: 01-getting-started/project-overview.md
          access: public
        - title: 快速开始
          path: 01-getting-started/quick-start.md
          access: public
        - title: 文档地图
          path: 01-getting-started/document-map.md
          access: public
    - title: 用户指南
      children:
        - title: 概览
          path: 02-user-guide/index.md
          access: public
        - title: 接手入口
          path: 02-user-guide/user-guide.md
          access: public
        - title: 安装说明
          path: 02-user-guide/installation.md
          access: public
        - title: 配置说明
          path: 02-user-guide/configuration.md
          access: public
        - title: 使用说明
          path: 02-user-guide/usage.md
          access: public
        - title: 管理员指南
          path: 02-user-guide/admin-guide.md
          access: public
    - title: 开发者指南
      children:
        - title: 概览
          path: 03-developer-guide/index.md
          access: private
        - title: 01 概念与约束
          children:
            - title: 概览
              path: 03-developer-guide/01-concepts/index.md
              access: private
            - title: 系统地图
              path: 03-developer-guide/01-concepts/01-system-map.md
              access: private
            - title: 真实约束
              path: 03-developer-guide/01-concepts/02-real-constraints.md
              access: private
        - title: 02 快速开始
          children:
            - title: 概览
              path: 03-developer-guide/02-quickstart/index.md
              access: private
            - title: 环境准备
              path: 03-developer-guide/02-quickstart/01-environment-setup.md
              access: private
            - title: 创建第一个模块
              path: 03-developer-guide/02-quickstart/02-create-first-module.md
              access: private
        - title: 03 项目结构与契约
          children:
            - title: 概览
              path: 03-developer-guide/03-project-structure/index.md
              access: private
            - title: 布局与入口点
              path: 03-developer-guide/03-project-structure/01-layout-and-entrypoints.md
              access: private
            - title: module.yaml 清单契约
              path: 03-developer-guide/03-project-structure/02-module-manifest.md
              access: private
        - title: 04 模块开发
          children:
            - title: 概览
              path: 03-developer-guide/04-development/index.md
              access: private
            - title: 编写 TaskScript
              path: 03-developer-guide/04-development/01-taskscript.md
              access: private
            - title: 编写 Workflow
              path: 03-developer-guide/04-development/02-workflow.md
              access: private
            - title: CLI 命令与 UI 配置
              path: 03-developer-guide/04-development/03-cli-and-ui.md
              access: private
            - title: Core 能力清单
              path: 03-developer-guide/04-development/04-core-capabilities.md
              access: private
            - title: Core 注入能力 API 参考
              path: 03-developer-guide/04-development/05-api-reference.md
              access: private
            - title: 模块开发最佳实践
              path: 03-developer-guide/04-development/06-best-practices.md
              access: private
        - title: 05 调试
          children:
            - title: 概览
              path: 03-developer-guide/05-debugging/index.md
              access: private
            - title: DevLink 与调试
              path: 03-developer-guide/05-debugging/01-devlink-and-debug.md
              access: private
        - title: 06 交付与验收
          children:
            - title: 概览
              path: 03-developer-guide/06-delivery/index.md
              access: private
            - title: zip 安装验收
              path: 03-developer-guide/06-delivery/01-zip-installation.md
              access: private
            - title: 交付验收清单
              path: 03-developer-guide/06-delivery/02-acceptance-checklist.md
              access: private
        - title: 07 排错
          children:
            - title: 概览
              path: 03-developer-guide/07-troubleshooting/index.md
              access: private
            - title: 常见坑位
              path: 03-developer-guide/07-troubleshooting/01-common-pitfalls.md
              access: private
        - title: 08 迁移指南
          children:
            - title: Shim 迁移
              path: 03-developer-guide/08-migration/01-shim-migration.md
              access: private
    - title: 项目开发文档（内）
      children:
        - title: 概览
          path: 04-project-development/index.md
          access: private
        - title: 项目治理
          children:
            - title: 概览
              path: 04-project-development/01-governance/index.md
              access: private
            - title: 项目章程
              path: 04-project-development/01-governance/project-charter.md
              access: private
        - title: 调研与决策
          children:
            - title: 概览
              path: 04-project-development/02-discovery/index.md
              access: private
            - title: 输入与证据清单
              path: 04-project-development/02-discovery/input.md
              access: private
            - title: 当前真实状态分析
              path: 04-project-development/02-discovery/current-state-analysis.md
              access: private
            - title: 旧文档审计与收敛策略
              path: 04-project-development/02-discovery/legacy-doc-audit.md
              access: private
            - title: 头脑风暴记录：模块根 `__init__.py` 自动托管改造
              path: 04-project-development/02-discovery/brainstorm-record.md
              access: private
        - title: 需求
          children:
            - title: 概览
              path: 04-project-development/03-requirements/index.md
              access: private
            - title: 产品需求文档（PRD）
              path: 04-project-development/03-requirements/prd.md
              access: private
            - title: 需求分析
              path: 04-project-development/03-requirements/requirements-analysis.md
              access: private
            - title: 需求校验
              path: 04-project-development/03-requirements/requirements-verification.md
              access: private
        - title: 设计文档
          children:
            - title: 概览
              path: 04-project-development/04-design/index.md
              access: private
            - title: 技术选型与工程规则
              path: 04-project-development/04-design/technical-selection.md
              access: private
            - title: 系统架构
              path: 04-project-development/04-design/system-architecture.md
              access: private
            - title: 模块边界
              path: 04-project-development/04-design/module-boundaries.md
              access: private
            - title: 接口与契约设计
              path: 04-project-development/04-design/api-design.md
              access: private
        - title: 开发过程文档
          children:
            - title: 概览
              path: 04-project-development/05-development-process/index.md
              access: private
            - title: 软件开发流程
              path: 04-project-development/05-development-process/software-development-process.md
              access: private
            - title: 实施方案
              path: 04-project-development/05-development-process/implementation-plan.md
              access: private
            - title: 执行记录
              path: 04-project-development/05-development-process/execution-log.md
              access: private
        - title: 测试与验证
          children:
            - title: 概览
              path: 04-project-development/06-testing-verification/index.md
              access: private
            - title: 测试计划
              path: 04-project-development/06-testing-verification/test-plan.md
              access: private
            - title: 设计与实现一致性审查
              path: 04-project-development/06-testing-verification/design-implementation-audit.md
              access: private
            - title: 质量门与文档导航规则
              path: 04-project-development/06-testing-verification/quality-gates.md
              access: private
        - title: 发布与交付
          children:
            - title: 概览
              path: 04-project-development/07-release-delivery/index.md
              access: private
            - title: 验收检查清单
              path: 04-project-development/07-release-delivery/acceptance-checklist.md
              access: private
            - title: 发布说明
              path: 04-project-development/07-release-delivery/release-notes.md
              access: private
            - title: 交付包清单
              path: 04-project-development/07-release-delivery/delivery-package.md
              access: private
            - title: 版本治理规则
              path: 04-project-development/07-release-delivery/version-governance.md
              access: private
        - title: 运维与维护
          children:
            - title: 概览
              path: 04-project-development/08-operations-maintenance/index.md
              access: private
            - title: 部署与运行说明
              path: 04-project-development/08-operations-maintenance/deployment-guide.md
              access: private
            - title: 运行手册
              path: 04-project-development/08-operations-maintenance/operations-runbook.md
              access: private
            - title: Core 接手与日常维护
              path: 04-project-development/08-operations-maintenance/core-maintainer-guide.md
              access: private
        - title: 演进复盘
          children:
            - title: 概览
              path: 04-project-development/09-evolution/index.md
              access: private
            - title: Skill 进化方案
              path: 04-project-development/09-evolution/skill-evolution-plan.md
              access: private
        - title: 追踪矩阵
          children:
            - title: 概览
              path: 04-project-development/10-traceability/index.md
              access: private
            - title: 需求追踪矩阵
              path: 04-project-development/10-traceability/requirements-matrix.md
              access: private
            - title: 接口追踪矩阵
              path: 04-project-development/10-traceability/interface-matrix.md
              access: private
            - title: 文档索引
              path: 04-project-development/10-traceability/document-index.md
              access: private
---

# crawler4j

这是 `crawler4j` 的正式项目文档源。AI 软件工厂在项目仓库内直接维护这些文档，`docs-stratego` 通过 Git 子模块或等价的仓级挂载方式聚合展示，但不反向改写源文档。

## 四大模块

| 模块 | 回答的问题 | 主要读者 |
|---|---|---|
| `docs/01-getting-started/` | 这是什么项目、文档怎么读、从哪里开始 | 新维护者 / 协作者 |
| `docs/02-user-guide/` | 如何安装、配置、使用和管理宿主应用 | 宿主使用者 / 管理员 / 协作者 |
| `docs/03-developer-guide/` | 如何开发、调试、交付和迁移模块 | 模块开发者 / Core 集成人员 |
| `docs/04-project-development/` | 项目如何治理、设计、实施、验证、发布、运维和追踪 | Tech Lead / Dev / QA / Release / Ops |

## 按角色快速阅读

### 新维护者

1. [文档地图](01-getting-started/document-map.md)
2. [接手入口](02-user-guide/user-guide.md)
3. [Core 接手与日常维护](04-project-development/08-operations-maintenance/core-maintainer-guide.md)
4. [当前真实状态分析](04-project-development/02-discovery/current-state-analysis.md)
5. [实施方案](04-project-development/05-development-process/implementation-plan.md)

### 模块开发者

1. [开发者指南总览](03-developer-guide/index.md)
2. [01 概念与约束](03-developer-guide/01-concepts/index.md)
3. [02 快速开始](03-developer-guide/02-quickstart/index.md)
4. [04 模块开发](03-developer-guide/04-development/index.md)
5. [06 交付与验收](03-developer-guide/06-delivery/index.md)

### 发布 / 运维

1. [发布与交付概览](04-project-development/07-release-delivery/index.md)
2. [验收检查清单](04-project-development/07-release-delivery/acceptance-checklist.md)
3. [交付包清单](04-project-development/07-release-delivery/delivery-package.md)
4. [部署与运行说明](04-project-development/08-operations-maintenance/deployment-guide.md)
5. [运行手册](04-project-development/08-operations-maintenance/operations-runbook.md)

### 宿主使用者 / 协作者

1. [接手入口](02-user-guide/user-guide.md)
2. [安装说明](02-user-guide/installation.md)
3. [配置说明](02-user-guide/configuration.md)
4. [使用说明](02-user-guide/usage.md)
5. [管理员指南](02-user-guide/admin-guide.md)

## 维护规则

- 只有根 `docs/index.md` 声明全站 `mkdocs.nav`、页面路径和页面权限。
- 子目录 `index.md` 只作为正文首页和资源权限锚点，不再承担导航声明职责。
- 页面、图片和附件跟随所属目录维护；资源文件放在当前目录或当前目录的 `assets/` 下。
- 仓内链接统一使用相对路径，不写机器绝对路径。
- 新增、删除或移动 Markdown 页面后，同步刷新根 `docs/index.md` 的目录树、`docs/04-project-development/10-traceability/document-index.md` 和 `.factory/memory/doc-map.md`。
