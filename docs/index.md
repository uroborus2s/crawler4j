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
            - title: 发布说明
              path: 04-project-development/07-release-delivery/release-notes.md
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

## 维护规则

- 只有根 `docs/index.md` 声明全站 `mkdocs.nav`、页面路径和页面权限。
- 子目录 `index.md` 只作为正文首页和资源权限锚点，不再承担导航声明职责。
- 页面、图片和附件跟随所属目录维护；资源文件放在当前目录或当前目录的 `assets/` 下。
- 仓内链接统一使用相对路径，不写机器绝对路径。
- 新增、删除或移动 Markdown 页面后，同步刷新根 `docs/index.md` 的目录树和子目录概览页。
