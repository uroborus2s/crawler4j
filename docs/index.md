---
title: crawler4j
mkdocs:
  home_access: public
  nav:
    - title: 项目过程文档
      children:
        - title: 总览
          path: project-process/index.md
          access: public
        - title: Core 接手与日常维护
          path: project-process/core-maintainer-guide.md
          access: private
        - title: 项目治理
          children:
            - title: 概览
              path: 00-governance/index.md
              access: public
            - title: 项目章程
              path: 00-governance/project-charter.md
              access: public
        - title: 调研与决策
          children:
            - title: 概览
              path: 01-discovery/index.md
              access: public
            - title: 输入与证据清单
              path: 01-discovery/input.md
              access: public
            - title: 头脑风暴记录
              path: 01-discovery/brainstorm-record.md
              access: public
            - title: 当前真实状态分析
              path: 01-discovery/current-state-analysis.md
              access: public
            - title: 旧文档审计与收敛策略
              path: 01-discovery/legacy-doc-audit.md
              access: public
        - title: 需求
          children:
            - title: 概览
              path: 02-requirements/index.md
              access: public
            - title: 产品需求文档（PRD）
              path: 02-requirements/prd.md
              access: public
            - title: 需求分析
              path: 02-requirements/requirements-analysis.md
              access: public
            - title: 需求校验
              path: 02-requirements/requirements-verification.md
              access: public
        - title: 方案设计
          children:
            - title: 概览
              path: 03-solution/index.md
              access: private
            - title: 技术选型与工程规则
              path: 03-solution/technical-selection.md
              access: private
            - title: 系统架构
              path: 03-solution/system-architecture.md
              access: private
            - title: 模块边界
              path: 03-solution/module-boundaries.md
              access: private
            - title: 接口与契约设计
              path: 03-solution/api-design.md
              access: private
        - title: 交付计划
          children:
            - title: 概览
              path: 04-delivery/index.md
              access: private
            - title: 工作分解结构（WBS）
              path: 04-delivery/wbs.md
              access: private
            - title: 实施方案
              path: 04-delivery/implementation-plan.md
              access: private
            - title: 任务分解
              path: 04-delivery/task-breakdown.md
              access: private
            - title: 执行日志
              path: 04-delivery/execution-log.md
              access: private
        - title: 质量保障
          children:
            - title: 概览
              path: 05-quality/index.md
              access: private
            - title: 测试计划
              path: 05-quality/test-plan.md
              access: private
            - title: 设计与实现一致性审查
              path: 05-quality/design-implementation-audit.md
              access: private
            - title: 质量门与文档导航规则
              path: 05-quality/quality-gates.md
              access: private
        - title: 发布与运行
          children:
            - title: 发布概览
              path: 06-release/index.md
              access: private
            - title: 发布说明
              path: 06-release/release-notes.md
              access: private
            - title: 版本治理规则
              path: 06-release/version-governance.md
              access: private
            - title: 运维概览
              path: 07-operations/index.md
              access: private
            - title: 部署与运行说明
              path: 07-operations/deployment-guide.md
              access: private
        - title: 演进与追踪
          children:
            - title: 演进概览
              path: 09-evolution/index.md
              access: private
            - title: 追踪矩阵概览
              path: traceability/index.md
              access: private
            - title: 文档索引
              path: traceability/document-index.md
              access: private
            - title: 需求追踪矩阵
              path: traceability/requirements-matrix.md
              access: private
    - title: Model 开发指南
      children:
        - title: 总览
          path: 08-handover/module-developer-guide/index.md
          access: public
        - title: 01 概念与约束
          children:
            - title: 概览
              path: 08-handover/module-developer-guide/01-concepts/index.md
              access: public
            - title: 系统地图
              path: 08-handover/module-developer-guide/01-concepts/01-system-map.md
              access: public
            - title: 真实约束
              path: 08-handover/module-developer-guide/01-concepts/02-real-constraints.md
              access: public
        - title: 02 快速开始
          children:
            - title: 概览
              path: 08-handover/module-developer-guide/02-quickstart/index.md
              access: public
            - title: 环境准备
              path: 08-handover/module-developer-guide/02-quickstart/01-environment-setup.md
              access: public
            - title: 创建第一个模块
              path: 08-handover/module-developer-guide/02-quickstart/02-create-first-module.md
              access: public
        - title: 03 项目结构与契约
          children:
            - title: 概览
              path: 08-handover/module-developer-guide/03-project-structure/index.md
              access: public
            - title: 布局与入口
              path: 08-handover/module-developer-guide/03-project-structure/01-layout-and-entrypoints.md
              access: public
            - title: 模块清单（module.yaml）
              path: 08-handover/module-developer-guide/03-project-structure/02-module-manifest.md
              access: public
        - title: 04 模块开发
          children:
            - title: 概览
              path: 08-handover/module-developer-guide/04-development/index.md
              access: public
            - title: TaskScript
              path: 08-handover/module-developer-guide/04-development/01-taskscript.md
              access: public
            - title: Workflow
              path: 08-handover/module-developer-guide/04-development/02-workflow.md
              access: public
            - title: CLI 与 UI
              path: 08-handover/module-developer-guide/04-development/03-cli-and-ui.md
              access: public
        - title: 05 调试
          children:
            - title: 概览
              path: 08-handover/module-developer-guide/05-debugging/index.md
              access: public
            - title: DevLink 与调试
              path: 08-handover/module-developer-guide/05-debugging/01-devlink-and-debug.md
              access: public
        - title: 06 交付与验收
          children:
            - title: 概览
              path: 08-handover/module-developer-guide/06-delivery/index.md
              access: public
            - title: ZIP 安装
              path: 08-handover/module-developer-guide/06-delivery/01-zip-installation.md
              access: public
            - title: 验收清单
              path: 08-handover/module-developer-guide/06-delivery/02-acceptance-checklist.md
              access: public
        - title: 07 排错
          children:
            - title: 概览
              path: 08-handover/module-developer-guide/07-troubleshooting/index.md
              access: public
            - title: 常见坑位
              path: 08-handover/module-developer-guide/07-troubleshooting/01-common-pitfalls.md
              access: public
    - title: 历史归档
      children:
        - title: 总览
          path: archive/index.md
          access: private
        - title: 旧 SRS
          path: archive/reference-srs/index.md
          access: private
        - title: 旧设计专题
          path: archive/reference-design/index.md
          access: private
        - title: 旧架构补充
          path: archive/reference-architecture/index.md
          access: private
        - title: 旧 SDK 说明
          path: archive/reference-sdk/index.md
          access: private
        - title: 旧测试专题
          path: archive/reference-tests/index.md
          access: private
        - title: 旧用户与运维说明
          path: archive/reference-user-guide/index.md
          access: private
        - title: 旧模块开发素材
          path: archive/reference-module-dev/index.md
          access: private
---

# 文档中心

当前正式文档分成两大部分：

- `项目过程文档`：面向 Core 开发、维护、QA、发布。
- `Model 开发指南`：面向外部模块开发者与做模块集成的 Core 成员。

旧 SRS、旧设计、旧测试和旧用户说明统一迁入 `docs/archive/`，只在需要追溯背景时按需阅读。
