# 概览 (Home)

欢迎使用 **Crawler4j** —— 为企业级桌面自动化而生的任务运行平台。

## 当前文档入口

当前正式的人类文档体系已经统一到编号目录，仓库根 `docs/` 下不再保留平行的 legacy 专题根目录：

- `docs/00-governance/` 到 `docs/08-handover/`
- `docs/traceability/`

如果你是第一次接手这个仓库，建议按以下顺序阅读：

1. [当前真实状态](01-discovery/current-state-analysis.md)
2. [文档重组与参考层说明](01-discovery/legacy-doc-audit.md)
3. [系统架构](03-solution/system-architecture.md)
4. [任务分解](04-delivery/task-breakdown.md)
5. [质量门与文档导航规则](05-quality/quality-gates.md)
6. [部署与运行说明](07-operations/deployment-guide.md)

历史 SRS、设计、测试、用户指南和模块开发文档，已经分别并入编号目录下的 `reference-*` 子目录，作为同一套文档树里的详细参考层。完整映射见 [文档索引](traceability/document-index.md)。

## 🎯 核心价值

Crawler4j 旨在解决传统 Python 爬虫/自动化脚本的痛点：

*   **开箱即用**: 无需配置 Python 环境，下载即可运行。
*   **统一管理**: 像管理 APP 一样管理你的爬虫脚本。
*   **可视化调度**: 内置强大的策略引擎，可视化配置任务执行计划。
*   **插件化扩展**: 丰富的插件生态，支持第三方业务模块热插拔。

## 🏗️ 架构理念 (Core + Modules)

Crawler4j 采用 **微内核 (Micro-kernel) + 插件化 (Plugin-based)** 的架构设计：

*   **内核 (Core)**: 坚若磐石的基础设施。负责资源调度、环境隔离、日志记录和数据持久化。
*   **模块 (Modules)**: 灵活多变的业务逻辑。每个业务场景（如：机票抓取、报表生成）都是一个独立的插件。

您只需要关注业务逻辑的编写，剩下的——并发控制、防反爬、异常重试——都交给内核处理。

## 🚀 下一步

*   **我是用户**: 想要直接使用软件？请查看 [快速开始](08-handover/getting-started.md)。
*   **我是开发者**: 想要从零开始开发模块？请查阅 [模块开发指南](08-handover/module-developer-guide.md)。
*   **我是运维**: 需要部署和监控？请参考 [部署与运行说明](07-operations/deployment-guide.md)。  
*   **我是维护者**: 想看当前正式文档体系？请从 [当前真实状态](01-discovery/current-state-analysis.md) 开始。
 
