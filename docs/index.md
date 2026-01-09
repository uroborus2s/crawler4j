# Crawler4j

**简介与架构理念**

Crawler4j 是一个自动化监控与任务执行平台。

## 核心技术
- Python 3.12+
- Asyncio
- Type Hinting

## 架构原则
- **微内核 (Framework Core)**: 负责生命周期管理、调度、配置加载、事件总线，保持极简。
- **SDK**: 提供给开发者使用的标准接口、上下文对象（Context）、工具链。
- **插件 (Plugins/Modules)**: 具体的业务逻辑实现。
