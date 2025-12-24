# 任务清单：自动化爬虫 GUI

**输入**: 来自 `/specs/001-auto-crawler-gui/` 的设计文档
**前提**: plan.md, spec.md, data-model.md, research.md, quickstart.md

## 格式说明: `[ID] [P?] [Story?] 描述`

- **[P]**: 可并行执行 (不同文件，无依赖)
- **[Story]**: 所属用户故事 (US1, US2, US3)
- 描述中包含精确的文件路径

---

## 阶段 1: 项目初始化

**目的**: 使用 uv 创建项目结构，安装依赖

- [ ] T001 使用 `uv init` 初始化 Python 项目
- [ ] T002 创建项目目录结构 (src/ui, src/core, src/automation, src/utils, tests/)
- [ ] T003 [P] 使用 `uv add` 安装核心依赖: PyQt6, playwright, requests, pandas
- [ ] T004 [P] 使用 `uv add --dev` 安装开发依赖: ruff, pytest, pytest-asyncio, pytest-qt
- [ ] T005 [P] 运行 `playwright install chromium` 安装浏览器
- [ ] T006 初始化 SQLite 数据库 schema 脚本 `src/utils/init_db.py`

---

## 阶段 2: 基础设施 (阻塞性前置)

**目的**: 所有用户故事依赖的核心组件

**⚠️ 关键**: 必须完成此阶段才能开始用户故事

- [ ] T007 创建数据库操作模块 `src/utils/storage.py` (CRUD 封装)
- [ ] T008 [P] 创建携程账号模型 `src/core/models/ctrip_account.py`
- [ ] T009 [P] 创建劳保账号模型 `src/core/models/labor_account.py`
- [ ] T010 [P] 创建环境模型 `src/core/models/environment.py`
- [ ] T011 创建账号管理器 `src/core/account_manager.py` (双池调度逻辑)
- [ ] T012 [P] 创建日志模块 `src/utils/logger.py` (带时间戳的日志格式)
- [ ] T013 [P] 创建事件总线 `src/core/events.py` (Qt 信号/槽封装)
- [ ] T014 创建配置加载器 `src/config.py` (settings 表读写)

**检查点**: 基础设施就绪，可开始用户故事实现

---

## 阶段 3: 用户故事 1 - 自动化任务循环 (P1) 🎯 MVP

**目标**: 实现完整的 "登录-领题-搜索-提交" 自动化流程

**独立测试**: 使用单个测试账号和浏览器环境验证完整流程

### 实现任务

- [ ] T015 [US1] 创建浏览器 API 抽象层 `src/core/browser_api.py` (BitBrowser/VirtualBrowser 接口)
- [ ] T016 [US1] 创建浏览器检测模块 `src/core/browser_detector.py` (检测安装状态)
- [ ] T017 [US1] 创建 Playwright 封装 `src/automation/driver.py` (CDP 连接)
- [ ] T018 [US1] 实现携程登录工作流 `src/automation/workflows/ctrip_login.py`
- [ ] T019 [US1] 实现携程接码逻辑 (集成 sms_platform_url/key)
- [ ] T020 [US1] 实现劳保平台登录工作流 `src/automation/workflows/labor_login.py`
- [ ] T021 [US1] 实现劳保平台领题工作流 `src/automation/workflows/labor_claim_task.py`
- [ ] T022 [US1] 实现携程搜索工作流 `src/automation/workflows/ctrip_search.py`
- [ ] T023 [US1] 实现劳保平台提交工作流 `src/automation/workflows/labor_submit.py`
- [ ] T024 [US1] 创建任务编排器 `src/core/scheduler.py` (并发控制、环境调度)
- [ ] T025 [US1] 实现调度逻辑: 携程优先 → 查环境 → 启动/创建
- [ ] T026 [US1] 实现异常处理: 携程被封 → 删除环境 → 账号置黑

**检查点**: US1 完成，可独立运行自动化流程

---

## 阶段 4: 用户故事 2 - GUI 监控与控制 (P2)

**目标**: 提供可视化界面监控环境状态和日志

**独立测试**: 启动 GUI，模拟状态更新，验证界面响应

### 实现任务

- [ ] T027 [US2] 创建主窗口框架 `src/ui/main_window.py`
- [ ] T028 [P] [US2] 创建环境列表控件 `src/ui/widgets/environment_list.py`
- [ ] T029 [P] [US2] 创建日志查看器控件 `src/ui/widgets/log_viewer.py`
- [ ] T030 [P] [US2] 创建账号统计控件 `src/ui/widgets/account_stats.py` (显示劳保账号统计)
- [ ] T031 [US2] 实现开始/停止按钮逻辑
- [ ] T032 [US2] 集成事件总线与 UI 更新 (状态实时刷新)
- [ ] T033 [US2] 创建 QSS 样式表 `src/ui/styles/main.qss`

**检查点**: US2 完成，GUI 可显示环境状态和日志

---

## 阶段 5: 用户故事 3 - 配置管理 (P3)

**目标**: 提供账号导入、浏览器选择、设置管理功能

**独立测试**: 导入 CSV 数据，验证数据正确入库

### 实现任务

- [ ] T034 [US3] 创建设置对话框 `src/ui/settings_dialog.py`
- [ ] T035 [P] [US3] 实现浏览器类型选择 + 安装检测反馈
- [ ] T036 [P] [US3] 创建携程账号导入页 `src/ui/pages/ctrip_accounts_page.py`
- [ ] T037 [P] [US3] 创建劳保账号导入页 `src/ui/pages/labor_accounts_page.py`
- [ ] T038 [US3] 实现 CSV 解析逻辑 (pandas 读取)
- [ ] T039 [US3] 实现并发数量配置
- [ ] T040 [US3] 实现接码平台配置 (URL/Key/Type)

**检查点**: US3 完成，可导入账号和配置系统

---

## 阶段 6: 收尾与优化

**目的**: 跨故事改进和收尾工作

- [ ] T041 [P] 创建程序入口 `src/main.py`
- [ ] T042 [P] 更新 README.md 文档
- [ ] T043 代码清理和重构
- [ ] T044 运行 quickstart.md 验证
- [ ] T045 [P] 异常情况处理优化 (号码池耗尽、浏览器崩溃)
- [ ] T046 使用 `uv build` 打包发布

---

## 依赖关系与执行顺序

### 阶段依赖

- **阶段 1 (初始化)**: 无依赖，立即开始
- **阶段 2 (基础设施)**: 依赖阶段 1 完成 - **阻塞所有用户故事**
- **用户故事 (阶段 3-5)**: 全部依赖阶段 2 完成，之后可并行
- **阶段 6 (收尾)**: 依赖所有用户故事完成

### 用户故事依赖

- **US1 (P1)**: 阶段 2 完成后可开始 - 无其他故事依赖
- **US2 (P2)**: 阶段 2 完成后可开始 - 可与 US1 并行
- **US3 (P3)**: 阶段 2 完成后可开始 - 可与 US1/US2 并行

### 并行机会

- T003, T004 可并行 (不同工具配置)
- T007, T008, T009 可并行 (不同模型文件)
- T011, T012 可并行 (不同工具模块)
- T027, T028, T029 可并行 (不同 UI 控件)
- T034, T035, T036 可并行 (不同 UI 页面)

---

## 实施策略

### MVP 优先 (仅 US1)

1. 完成阶段 1: 初始化
2. 完成阶段 2: 基础设施 (**关键阻塞点**)
3. 完成阶段 3: US1 自动化流程
4. **停止并验证**: 使用命令行测试自动化流程
5. 可部署/演示

### 增量交付

1. 初始化 + 基础设施 → 基础就绪
2. 添加 US1 → 独立测试 → 演示 (MVP!)
3. 添加 US2 → 独立测试 → 演示 (支持 GUI 监控)
4. 添加 US3 → 独立测试 → 演示 (完整配置功能)

---

## 统计摘要

| 指标 | 数值 |
|------|------|
| 总任务数 | 46 |
| 阶段 1 (初始化 - uv) | 6 |
| 阶段 2 (基础设施) | 8 |
| US1 任务数 | 12 |
| US2 任务数 | 7 |
| US3 任务数 | 7 |
| 阶段 6 (收尾 - uv build) | 6 |
| 可并行任务 | 17 |
