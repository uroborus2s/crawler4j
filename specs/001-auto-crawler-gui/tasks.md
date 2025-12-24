# 任务清单：自动化爬虫 GUI

**输入**: 来自 `/specs/001-auto-crawler-gui/` 的设计文档
**前提**: plan.md, spec.md, data-model.md, research.md, ui-design.md

## 格式说明: `[ID] [P?] [Story?] 描述`

- **[P]**: 可并行执行 (不同文件，无依赖)
- **[Story]**: 所属用户故事 (US1, US2, US3)
- 描述中包含精确的文件路径

---

## 阶段 1: 项目初始化 ✅

**目的**: 使用 uv 创建项目结构，安装依赖

- [x] T001 使用 `uv init` 初始化 Python 项目
- [x] T002 创建项目目录结构
- [x] T003 使用 `uv add` 安装核心依赖
- [x] T004 使用 `uv add --dev` 安装开发依赖
- [ ] T005 运行 `playwright install chromium` (可选，后续执行)
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

## 阶段 3: 用户故事 2 - GUI 框架与监控 (P2) 🎯 优先

**目标**: 构建 GUI 框架和控制台页面

**独立测试**: 启动 GUI，验证布局和样式正确

### 3.1 UI 框架

- [ ] T015 [US2] 创建深色主题样式表 `src/ui/styles/dark_theme.qss`
- [ ] T016 [US2] 创建主窗口框架 `src/ui/main_window.py` (左侧导航+右侧内容+状态栏)
- [ ] T017 [US2] 创建侧边导航栏组件 `src/ui/widgets/sidebar.py`
- [ ] T018 [US2] 创建状态栏组件 `src/ui/widgets/status_bar.py`

### 3.2 通用控件

- [ ] T019 [P] [US2] 创建可复用表格控件 `src/ui/widgets/data_table.py` (分页/搜索/排序)
- [ ] T020 [P] [US2] 创建日志查看器控件 `src/ui/widgets/log_viewer.py` (筛选/自动滚动)
- [ ] T021 [P] [US2] 创建 Toast 提示组件 `src/ui/widgets/toast.py`
- [ ] T022 [P] [US2] 创建确认对话框组件 `src/ui/widgets/confirm_dialog.py`

### 3.3 控制台页面

- [ ] T023 [US2] 创建控制台页面 `src/ui/pages/dashboard_page.py`
- [ ] T024 [US2] 实现控制面板 (开始/停止/重置/并发选择)
- [ ] T025 [US2] 实现运行环境列表表格
- [ ] T026 [US2] 实现实时日志面板
- [ ] T027 [US2] 集成事件总线与 UI 更新

**检查点**: GUI 框架完成，可显示控制台页面

---

## 阶段 4: 用户故事 3 - 配置管理 (P3)

**目标**: 账号导入、浏览器选择、全局设置

**独立测试**: 导入 CSV 数据，验证数据正确入库

### 4.1 携程账号页面

- [ ] T028 [US3] 创建携程账号页面 `src/ui/pages/ctrip_accounts_page.py`
- [ ] T029 [US3] 实现账号列表表格 (状态/接码平台/操作按钮)
- [ ] T030 [US3] 创建添加/编辑账号弹窗 `src/ui/dialogs/ctrip_account_dialog.py`
- [ ] T031 [US3] 实现 CSV 导入功能
- [ ] T032 [US3] 实现批量操作 (删除/置黑/启用)

### 4.2 劳保账号页面

- [ ] T033 [US3] 创建劳保账号页面 `src/ui/pages/labor_accounts_page.py`
- [ ] T034 [US3] 实现账号列表表格 (统计数据列)
- [ ] T035 [US3] 创建添加/编辑账号弹窗 `src/ui/dialogs/labor_account_dialog.py`
- [ ] T036 [US3] 创建统计图表弹窗 `src/ui/dialogs/stats_dialog.py`
- [ ] T037 [US3] 实现 CSV 导入功能

### 4.3 环境管理页面

- [ ] T038 [US3] 创建环境管理页面 `src/ui/pages/environments_page.py`
- [ ] T039 [US3] 实现环境列表表格
- [ ] T040 [US3] 创建手动创建环境弹窗 `src/ui/dialogs/create_env_dialog.py`

### 4.4 设置页面

- [ ] T041 [US3] 创建设置页面 `src/ui/pages/settings_page.py`
- [ ] T042 [US3] 实现浏览器设置区 (类型选择/安装检测/API 测试)
- [ ] T043 [US3] 实现任务设置区 (并发/间隔/重试)
- [ ] T044 [US3] 实现接码平台默认设置区
- [ ] T045 [US3] 创建浏览器检测模块 `src/core/browser_detector.py`

**检查点**: 配置管理完成，可导入账号和配置系统

---

## 阶段 5: 用户故事 1 - 自动化任务循环 (P1)

**目标**: 实现完整的 "登录-领题-搜索-提交" 自动化流程

**独立测试**: 使用单个测试账号验证完整流程

### 5.1 浏览器控制

- [ ] T046 [US1] 创建浏览器 API 抽象层 `src/core/browser_api.py`
- [ ] T047 [US1] 创建 Playwright 封装 `src/automation/driver.py` (CDP 连接)

### 5.2 工作流实现

- [ ] T048 [US1] 实现携程登录工作流 `src/automation/workflows/ctrip_login.py`
- [ ] T049 [US1] 实现携程接码逻辑 `src/automation/workflows/sms_receiver.py`
- [ ] T050 [US1] 实现劳保平台登录工作流 `src/automation/workflows/labor_login.py`
- [ ] T051 [US1] 实现劳保平台领题工作流 `src/automation/workflows/labor_claim_task.py`
- [ ] T052 [US1] 实现携程搜索工作流 `src/automation/workflows/ctrip_search.py`
- [ ] T053 [US1] 实现劳保平台提交工作流 `src/automation/workflows/labor_submit.py`

### 5.3 调度器

- [ ] T054 [US1] 创建任务编排器 `src/core/scheduler.py`
- [ ] T055 [US1] 实现调度逻辑: 携程优先 → 查环境 → 启动/创建
- [ ] T056 [US1] 实现异常处理: 携程被封 → 删除环境 → 账号置黑

**检查点**: 自动化流程完成，可独立运行任务

---

## 阶段 6: 收尾与优化

**目的**: 跨故事改进和收尾工作

- [ ] T057 [P] 创建程序入口 `src/main.py`
- [ ] T058 [P] 更新 README.md 文档
- [ ] T059 代码清理和重构
- [ ] T060 运行 quickstart.md 验证
- [ ] T061 [P] 异常情况处理优化 (号码池耗尽、浏览器崩溃)
- [ ] T062 使用 `uv build` 打包发布

---

## 依赖关系与执行顺序

### 阶段依赖

- **阶段 1 (初始化)**: ✅ 已完成
- **阶段 2 (基础设施)**: 依赖阶段 1 - **阻塞所有用户故事**
- **阶段 3 (US2 GUI)**: 依赖阶段 2 - 优先实现 GUI 框架
- **阶段 4 (US3 配置)**: 依赖阶段 3 - 在 GUI 框架上构建页面
- **阶段 5 (US1 自动化)**: 依赖阶段 2 - 可与阶段 3/4 并行
- **阶段 6 (收尾)**: 依赖所有故事完成

### 推荐执行顺序

```
阶段 1 ✅ → 阶段 2 → 阶段 3 (GUI) → 阶段 4 (配置) → 阶段 5 (自动化) → 阶段 6
```

---

## 统计摘要

| 指标 | 数值 |
|------|------|
| 总任务数 | 62 |
| 阶段 1 (初始化) | 6 (已完成 4) |
| 阶段 2 (基础设施) | 8 |
| US2 任务数 (GUI) | 13 |
| US3 任务数 (配置) | 18 |
| US1 任务数 (自动化) | 11 |
| 阶段 6 (收尾) | 6 |
| 可并行任务 | 12 |
