# 实施计划：自动化爬虫 GUI

**分支**: `001-auto-crawler-gui` | **日期**: 2025-12-24 | **规格说明书**: [spec.md](spec.md)
**输入**: 来自 `specs/001-auto-crawler-gui/spec.md` 的功能规格说明书

## 摘要

本项目旨在构建一个带有 GUI (PyQt6) 的桌面自动化工具，用于管理浏览器环境（通过 BitBrowser/VirtualBrowser API）。它自动化了一个特定的工作流程：登录 -> 领题 -> 搜索 (携程) -> 提交 (劳保平台)。它支持并发执行、双账号池管理（携程账号 + 劳保账号）、浏览器类型选择和实时日志记录。

## 技术背景

**语言/版本**: Python 3.10+
**主要依赖**:
- `PyQt6` (GUI 界面)
- `requests` (用于与浏览器控制器 API 交互)
- `playwright` (浏览器自动化 - 异步原生，更稳定)
- `pandas` (数据导入/导出)
**存储**: SQLite (本地配置和账号池管理)
**测试**: `pytest` (单元测试), `pytest-asyncio` (异步测试), `pytest-qt` (GUI 测试)
**目标平台**: Windows / macOS
**项目类型**: 桌面应用程序
**性能目标**: 支持 10+ 并发浏览器实例；GUI 延迟 <1s。
**约束**: 必须集成第三方浏览器应用 (BitBrowser 或 VirtualBrowser，用户可选)。

## 宪章检查

*关卡：必须在阶段 0 研究之前通过。*

1. **代码质量 (KISS)**: 系统设计将 GUI (视图) 与逻辑 (控制器/工作者) 分离。使用 SQLite 存储账号池和配置。
2. **测试标准**: 每个核心逻辑组件 (调度器, 账号管理器, 浏览器检测) 都必须有单元测试。
3. **用户体验一致性**: 浏览器选择界面需明确显示安装状态；操作反馈即时。
4. **性能要求**: 使用 Playwright 异步 API 配合 `qasync` 或 `QThread` 实现并发。

## 项目结构

### 文档 (本功能)

```text
specs/001-auto-crawler-gui/
├── plan.md              # 本文件 (实施计划)
├── research.md          # 阶段 0 输出 (技术研究)
├── data-model.md        # 阶段 1 输出 (数据模型)
├── quickstart.md        # 阶段 1 输出 (快速开始)
└── tasks.md             # 阶段 2 输出 (任务清单)
```

### 源代码 (仓库根目录)

```text
src/
├── main.py                # 入口点
├── config.py              # 配置加载器
├── ui/
│   ├── main_window.py     # 主 GUI 窗口
│   ├── settings_dialog.py # 设置对话框 (浏览器选择、并发设置)
│   ├── widgets/           # 可复用控件 (日志视图, 账号列表)
│   └── styles/            # QSS 样式表
├── core/
│   ├── scheduler.py       # 任务编排
│   ├── account_manager.py # 账号池管理 (携程 + 劳保)
│   ├── browser_api.py     # BitBrowser/VirtualBrowser 接口抽象
│   ├── browser_detector.py # 检测指纹浏览器是否安装
│   └── events.py          # UI 更新事件总线
├── automation/
│   ├── driver.py          # Playwright 封装
│   └── workflows.py       # 具体业务逻辑 (登录, 搜索, 提交)
└── utils/
    ├── logger.py
    └── storage.py         # 数据库操作
```

**结构决策**: 采用模块化结构，分离 UI、核心逻辑 (调度器/状态) 和底层自动化，便于测试和维护。新增 `browser_detector.py` 用于检测浏览器安装状态。

## 复杂性跟踪

| 违规项 | 为何需要 | 拒绝更简单替代方案的原因 |
|--------|----------|-------------------------|
| 多线程/异步 | 并发浏览器控制 & 响应式 GUI | 单线程应用在网络/浏览器操作期间会冻结 UI。|
| 双账号池 | 携程和劳保是独立系统，需要分别管理 | 单一账号池无法区分两个平台的登录凭证。|
| 浏览器抽象层 | 支持 BitBrowser 和 VirtualBrowser 切换 | 硬编码单一浏览器会导致用户锁定。|
