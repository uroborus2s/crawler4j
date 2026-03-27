---
title: crawler4j
mkdocs:
  home_access: public
  nav:
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
        - title: reference srs
          children:
            - title: 概览
              path: 02-requirements/reference-srs/index.md
              access: public
            - title: 第 1 章 文档控制信息（Document Control）
              path: 02-requirements/reference-srs/01-document-control.md
              access: public
            - title: 第 2 章 项目需求概述（Project Overview）
              path: 02-requirements/reference-srs/02-project-overview.md
              access: public
            - title: 第 3 章 需求分析 (Requirements Analysis)
              path: 02-requirements/reference-srs/03-requirements-analysis.md
              access: public
            - title: 第 4 章 项目架构设计（Architecture）
              path: 02-requirements/reference-srs/04-architecture.md
              access: public
            - title: 05 framework core
              children:
                - title: 概览
                  path: 02-requirements/reference-srs/05-framework-core/index.md
                  access: public
                - title: 5.1 模块管理系统（Module Management）
                  path: 02-requirements/reference-srs/05-framework-core/05-1-module-management.md
                  access: public
                - title: 5.10 系统基础能力（System Capabilities）
                  path: 02-requirements/reference-srs/05-framework-core/05-10-system-capabilities.md
                  access: public
                - title: 5.2 运行环境管理（Runtime Environment Management）
                  path: 02-requirements/reference-srs/05-framework-core/05-2-runtime-environment-management.md
                  access: public
                - title: 5.3 任务策略管理 (TSM)
                  path: 02-requirements/reference-srs/05-framework-core/05-3-task-strategy-management.md
                  access: public
                - title: 5.4 自动化任务管理 (Automation Task Management)
                  path: 02-requirements/reference-srs/05-framework-core/05-4-automation-task-management.md
                  access: public
                - title: 5.5 UI Host & 微前端承载（UI Framework & Micro-frontend Host）
                  path: 02-requirements/reference-srs/05-framework-core/05-5-ui-host-microfrontend.md
                  access: public
                - title: 5.6 横切关注点 (Cross-cutting Concerns)
                  path: 02-requirements/reference-srs/05-framework-core/05-6-crosscutting.md
                  access: public
                - title: 5.7 测试规格与验收标准 (Testing & Acceptance)
                  path: 02-requirements/reference-srs/05-framework-core/05-7-testing-acceptance.md
                  access: public
                - title: 5.8 部署发布与运维 (Operations & Release)
                  path: 02-requirements/reference-srs/05-framework-core/05-8-operations-release.md
                  access: public
                - title: 5.9 Core 附录
                  path: 02-requirements/reference-srs/05-framework-core/05-9-appendix.md
                  access: public
                - title: 5.9 数据持久化与状态管理 (Data Persistence & State Management)
                  path: 02-requirements/reference-srs/05-framework-core/05-9-data-persistence.md
                  access: public
            - title: 06 sdk
              children:
                - title: 概览
                  path: 02-requirements/reference-srs/06-sdk/index.md
                  access: public
                - title: 6.1 TaskScript（原子任务契约）
                  path: 02-requirements/reference-srs/06-sdk/06-1-taskscript.md
                  access: public
                - title: 6.2 TaskFlow（工作流编排契约）
                  path: 02-requirements/reference-srs/06-sdk/06-2-taskflow.md
                  access: public
                - title: 6.3 TaskContext（执行上下文与能力注入）
                  path: 02-requirements/reference-srs/06-sdk/06-3-taskcontext.md
                  access: public
                - title: 6.4 TaskResult（结果模型）
                  path: 02-requirements/reference-srs/06-sdk/06-4-taskresult.md
                  access: public
                - title: 6.5 CLI（模块脚手架与扩展）
                  path: 02-requirements/reference-srs/06-sdk/06-5-cli.md
                  access: public
                - title: 6.6 数据模型与持久化（SDK 视角）
                  path: 02-requirements/reference-srs/06-sdk/06-6-data-model.md
                  access: public
                - title: 6.7 错误处理与可靠性（SDK 视角）
                  path: 02-requirements/reference-srs/06-sdk/06-7-error-reliability.md
                  access: public
                - title: 6.8 非功能需求（SDK）
                  path: 02-requirements/reference-srs/06-sdk/06-8-nfr.md
                  access: public
                - title: 6.9 测试/运维/附录（SDK）
                  path: 02-requirements/reference-srs/06-sdk/06-9-testing-ops-appendix.md
                  access: public
            - title: 07 modules
              children:
                - title: 概览
                  path: 02-requirements/reference-srs/07-modules/index.md
                  access: public
                - title: 7.1 模块通用规范 (General Module Specification)
                  path: 02-requirements/reference-srs/07-modules/07-1-general-spec.md
                  access: public
                - title: 7.2 模块规格说明书模板 (Module Specification Template)
                  path: 02-requirements/reference-srs/07-modules/07-2-module-template.md
                  access: public
                - title: 7.3 Ctrip 模块 (Ctrip Module)
                  path: 02-requirements/reference-srs/07-modules/07-3-ctrip.md
                  access: public
                - title: 7.4 其他模块（预留）
                  path: 02-requirements/reference-srs/07-modules/07-4-others.md
                  access: public
                - title: 7.5 Modules 附录
                  path: 02-requirements/reference-srs/07-modules/07-5-appendix.md
                  access: public
            - title: appendix
              children:
                - title: 概览
                  path: 02-requirements/reference-srs/appendix/index.md
                  access: public
                - title: 附录 A：术语表与对象字典
                  path: 02-requirements/reference-srs/appendix/A-glossary.md
                  access: public
                - title: 附录 B：错误码索引
                  path: 02-requirements/reference-srs/appendix/B-error-codes.md
                  access: public
                - title: 附录 C：配置项索引
                  path: 02-requirements/reference-srs/appendix/C-config-index.md
                  access: public
                - title: 附录 D：需求追溯矩阵
                  path: 02-requirements/reference-srs/appendix/D-traceability-matrix.md
                  access: public
                - title: 附录 E：图表索引
                  path: 02-requirements/reference-srs/appendix/E-diagram-index.md
                  access: public
                - title: 附录 F：兼容性与迁移指南
                  path: 02-requirements/reference-srs/appendix/F-compat-migration.md
                  access: public
            - title: templates
              children:
                - title: 概览
                  path: 02-requirements/reference-srs/templates/index.md
                  access: public
                - title: API 契约模板（API Contract Template）
                  path: 02-requirements/reference-srs/templates/api-contract.md
                  access: public
                - title: 数据契约模板（Data Contract Template）
                  path: 02-requirements/reference-srs/templates/data-contract.md
                  access: public
                - title: 功能级模板（Feature Template）
                  path: 02-requirements/reference-srs/templates/feature.md
                  access: public
                - title: 模块级模板（Module Template）
                  path: 02-requirements/reference-srs/templates/module.md
                  access: public
                - title: 用例模板（Use Case Template）
                  path: 02-requirements/reference-srs/templates/usecase.md
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
        - title: reference architecture
          children:
            - title: 概览
              path: 03-solution/reference-architecture/index.md
              access: private
            - title: 蛛行演略（crawler4j）UI 架构指南：共享组件与模块化设计
              path: 03-solution/reference-architecture/ui_components_guide.md
              access: private
        - title: reference design
          children:
            - title: 概览
              path: 03-solution/reference-design/index.md
              access: private
            - title: 总体架构设计文档 (General Architecture Design Document)
              path: 03-solution/reference-design/01-general-architecture.md
              access: private
            - title: Job-Task 执行链路架构重塑与关系梳理设计方案
              path: 03-solution/reference-design/design-job-task-engine.md
              access: private
            - title: Strategy Configuration V2 & Environment Acquisition Design
              path: 03-solution/reference-design/design-strategy-config-v2.md
              access: private
            - title: 详细开发设计文档：[DBG-01] 基于 Core 的 Model 调试会话与 IDE 附加
              path: 03-solution/reference-design/model-debug-session.md
              access: private
            - title: 详细开发设计文档：[Module-01] 运行时环境管理 (REM)
              path: 03-solution/reference-design/module-01-runtime-environment.md
              access: private
            - title: 详细开发设计文档：[Module-02] 任务策略管理 (TSM)
              path: 03-solution/reference-design/module-02-task-strategy.md
              access: private
            - title: 详细开发设计文档：[Module-03] 模块管理系统 (MMS)
              path: 03-solution/reference-design/module-03-module-management.md
              access: private
            - title: 详细开发设计文档：[Module-04] 数据持久化层 (Data Persistence)
              path: 03-solution/reference-design/module-04-data-persistence.md
              access: private
            - title: 详细开发设计文档：[Module-05] SDK - 核心契约与开发套件
              path: 03-solution/reference-design/module-05-sdk.md
              access: private
            - title: 详细开发设计文档：[Module-06] UI - 宿主程序与扩展机制 (UI Host)
              path: 03-solution/reference-design/module-06-ui-host.md
              access: private
            - title: ATM 核心引擎优化建议报告
              path: 03-solution/reference-design/optimization_report_atm.md
              access: private
            - title: Task Engine V2 架构设计方案
              path: 03-solution/reference-design/task-engine-v2.md
              access: private
        - title: reference sdk
          children:
            - title: 概览
              path: 03-solution/reference-sdk/index.md
              access: private
            - title: Context
              path: 03-solution/reference-sdk/context.md
              access: private
            - title: Core
              path: 03-solution/reference-sdk/core.md
              access: private
            - title: Utils
              path: 03-solution/reference-sdk/utils.md
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
        - title: reference tests
          children:
            - title: 概览
              path: 05-quality/reference-tests/index.md
              access: private
            - title: 综合测试设计文档 (Comprehensive Test Design Document)
              path: 05-quality/reference-tests/01-comprehensive-test-design.md
              access: private
            - title: 测试设计文档：[Module-01] 运行时环境管理 (REM)
              path: 05-quality/reference-tests/test-01-rem.md
              access: private
            - title: 测试设计文档：[Module-02] 任务策略管理 (TSM)
              path: 05-quality/reference-tests/test-02-tsm.md
              access: private
            - title: 测试设计文档：[Module-03] 模块管理系统 (MMS)
              path: 05-quality/reference-tests/test-03-mms.md
              access: private
            - title: 测试设计文档：[Module-04] 数据持久化层 (Persistence)
              path: 05-quality/reference-tests/test-04-persistence.md
              access: private
            - title: 测试设计文档：[Module-05] SDK 核心契约 (SDK)
              path: 05-quality/reference-tests/test-05-sdk.md
              access: private
            - title: 测试设计文档：[Module-06] UI 宿主程序 (UI Host)
              path: 05-quality/reference-tests/test-06-ui.md
              access: private
    - title: 发布
      children:
        - title: 概览
          path: 06-release/index.md
          access: public
        - title: 发布说明
          path: 06-release/release-notes.md
          access: public
        - title: 版本治理规则
          path: 06-release/version-governance.md
          access: public
    - title: 运维
      children:
        - title: 概览
          path: 07-operations/index.md
          access: private
        - title: 部署与运行说明
          path: 07-operations/deployment-guide.md
          access: private
    - title: 交接
      children:
        - title: 概览
          path: 08-handover/index.md
          access: public
        - title: 接手与日常使用指南
          path: 08-handover/user-guide.md
          access: public
        - title: 快速开始 (Quick Start)
          path: 08-handover/getting-started.md
          access: public
        - title: 模块开发指南
          path: 08-handover/module-developer-guide.md
          access: public
        - title: reference module dev
          children:
            - title: 概览
              path: 08-handover/reference-module-dev/index.md
              access: public
        - title: reference user guide
          children:
            - title: 概览
              path: 08-handover/reference-user-guide/index.md
              access: public
            - title: 打包与发布 (Build & Release)
              path: 08-handover/reference-user-guide/build-release.md
              access: public
            - title: 策略配置详解 (Configuration)
              path: 08-handover/reference-user-guide/configuration.md
              access: public
            - title: 任务调度与监控
              path: 08-handover/reference-user-guide/dashboard-usage.md
              access: public
            - title: 部署与打包 (Deployment & Build)
              path: 08-handover/reference-user-guide/deployment.md
              access: public
            - title: sdk
              children:
                - title: 概览
                  path: 08-handover/reference-user-guide/sdk/index.md
                  access: public
    - title: 演进复盘
      children:
        - title: 概览
          path: 09-evolution/index.md
          access: private
    - title: 追踪矩阵
      children:
        - title: 概览
          path: traceability/index.md
          access: private
        - title: 需求追踪矩阵
          path: traceability/requirements-matrix.md
          access: private
        - title: 文档索引
          path: traceability/document-index.md
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
