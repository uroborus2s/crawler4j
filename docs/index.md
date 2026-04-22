---
title: crawler4j
mkdocs:
  home_access: public
  nav:
    - title: 入门说明
      children:
        - title: 了解 crawler4j
          path: 01-getting-started/index.md
          access: public
    - title: 用户指南
      children:
        - title: 概览
          path: 02-user-guide/index.md
          access: public
        - title: 安装与第一次打开
          path: 02-user-guide/installation.md
          access: public
        - title: 首次设置
          path: 02-user-guide/configuration.md
          access: public
        - title: 开始使用
          path: 02-user-guide/user-guide.md
          access: public
        - title: 日常使用
          path: 02-user-guide/usage.md
          access: public
        - title: 作业详情整图说明
          path: 02-user-guide/job-detail-guide.md
          access: public
        - title: 异常案例
          path: 02-user-guide/exception-cases.md
          access: public
        - title: 管理员指南
          path: 02-user-guide/admin-guide.md
          access: public
    - title: 开发者指南
      children:
        - title: 概览
          path: 03-developer-guide/index.md
          access: private
        - title: 快速开始
          path: 03-developer-guide/quickstart.md
          access: private
        - title: 核心概念
          path: 03-developer-guide/core-concepts.md
          access: private
        - title: 模块结构
          path: 03-developer-guide/module-structure.md
          access: private
        - title: 构建模块
          path: 03-developer-guide/build-modules.md
          access: private
        - title: UI 与数据表
          path: 03-developer-guide/ui-and-data-table.md
          access: private
        - title: 调试模块
          path: 03-developer-guide/debugging.md
          access: private
        - title: 交付模块
          path: 03-developer-guide/shipping.md
          access: private
        - title: 常见问题
          path: 03-developer-guide/troubleshooting.md
          access: private
        - title: SDK 与 CLI 参考
          path: 03-developer-guide/reference-sdk-and-cli.md
          access: private
        - title: Core 能力参考
          path: 03-developer-guide/reference-core-capabilities.md
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
            - title: 头脑风暴记录：ATM 模块资源池等待队列
              path: 04-project-development/02-discovery/atm-resource-pool-queue-brainstorm.md
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
            - title: 模块宿主管理页与最小化 UI 框架设计
              path: 04-project-development/04-design/module-hosted-ui-framework.md
              access: private
            - title: ATM 模块资源池等待队列设计
              path: 04-project-development/04-design/atm-resource-pool-queue-design.md
              access: private
            - title: 模块配置与数据契约
              path: 04-project-development/04-design/module-config-runtime-data-contract.md
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
            - title: ctrip 真实站点 E2E 收口方案
              path: 04-project-development/06-testing-verification/ctrip-real-site-e2e-closeout.md
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

这是 `crawler4j` 的正式文档入口，面向第一次接触产品的人、日常使用者、现场支持、模块开发者和内部维护者。

文档按“入门说明 / 用户指南 / 开发者指南 / 项目开发文档（内）”四层组织。如果你不是在维护源码，通常只需要前两层。

## 四大模块

| 模块 | 回答的问题 | 主要读者 |
|---|---|---|
| `docs/01-getting-started/` | 面向所有人的单页产品介绍：这是什么、能做什么、从哪开始读 | 第一次接触产品的人 / 协作者 |
| `docs/02-user-guide/` | 如何安装、配置、使用 和管理宿主应用 | 宿主使用者 / 管理员 / 协作者 |
| `docs/03-developer-guide/` | 如何开发、调试、交付模块 | 模块开发者 / Core 集成人员 |
| `docs/04-project-development/` | 项目如何治理、设计、实施、验证、发布、运维和追踪 | Tech Lead / Dev / QA / Release / Ops |

## 按角色快速阅读

### 新维护者

1. [了解 crawler4j](01-getting-started/index.md)
2. [开始使用](02-user-guide/user-guide.md)
3. [Core 接手与日常维护](04-project-development/08-operations-maintenance/core-maintainer-guide.md)
4. [当前真实状态分析](04-project-development/02-discovery/current-state-analysis.md)
5. [实施方案](04-project-development/05-development-process/implementation-plan.md)

### 模块开发者

1. [开发者指南总览](03-developer-guide/index.md)
2. [快速开始](03-developer-guide/quickstart.md)
3. [核心概念](03-developer-guide/core-concepts.md)
4. [模块结构](03-developer-guide/module-structure.md)
5. [构建模块](03-developer-guide/build-modules.md)
6. [交付模块](03-developer-guide/shipping.md)

### 发布 / 运维

1. [发布与交付概览](04-project-development/07-release-delivery/index.md)
2. [验收检查清单](04-project-development/07-release-delivery/acceptance-checklist.md)
3. [交付包清单](04-project-development/07-release-delivery/delivery-package.md)
4. [部署与运行说明](04-project-development/08-operations-maintenance/deployment-guide.md)
5. [运行手册](04-project-development/08-operations-maintenance/operations-runbook.md)

### 宿主使用者 / 协作者

1. [开始使用](02-user-guide/user-guide.md)
2. [安装与第一次打开](02-user-guide/installation.md)
3. [首次设置](02-user-guide/configuration.md)
4. [日常使用](02-user-guide/usage.md)
5. [作业详情整图说明](02-user-guide/job-detail-guide.md)
6. [异常案例](02-user-guide/exception-cases.md)
7. [管理员指南](02-user-guide/admin-guide.md)

## 维护规则

- 只有根 `docs/index.md` 声明全站 `mkdocs.nav` 、页面路径和页面权限。
- 子目录 `index.md` 只作为正文首页和资源权限锚 点，不再承担导航声明职责。
- 页面、图片和附件跟随所属目录维护；资源文件放 在当前目录或当前目录的 `assets/` 下。
- 仓内链接统一使用相对路径，不写机器绝对路径。
- 新增、删除或移动 Markdown 页面后，同步刷新根 `docs/index.md` 的目录树、`docs/04-project-development/10-traceability/document-index.md` 和 `.factory/memory/doc-map.md`。
