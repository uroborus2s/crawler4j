# 测试设计文档：[Module-06] UI 宿主程序 (UI Host)

## 1. 测试范围与目标

本测试文档覆盖《需求规格说明书 5.5》及《详细设计文档 Module-06》中定义的所有功能需求 (FR)。
目标是验证 UI Host (基于 PyQt6) 能正确加载并显示 Core 状态，同时安全地承载 Module 提供的扩展 UI。

**测试对象**: `src.ui` 包
**核心类**: `MainWindow`, `SchemaFormWidget`, `ModuleUILoader`, `ContextBridge`

## 2. 功能需求测试 (FR Testing)

### FR-UIHOST-001 Shell 与路由 (Shell & Routing)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_UI_001 | **启动与布局** | Core 正常启动 | 启动 App | 显示侧边栏、顶部工具栏、主区域 | P0 |
| TC_UI_002 | **模块菜单生成** | 已安装 Module A, B | 启动 App | 侧边栏 Modules 分组下出现 A 和 B 的链接 | P0 |
| TC_UI_003 | **页面切换** | 在 Dashboard | 点击侧边栏 Module A | 主区域无缝切换至 Module A 页面，无闪烁 | P0 |

### FR-UIHOST-002/003 通信通道 (Command & Event)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_UI_004 | **发送命令 (Async)** | 无 | 点击“刷新”按钮 (invoke cmd) | 1. 界面显示 Loading<br>2. 收到 Core 响应后 Loading 消失<br>3. 界面不卡死 | P0 |
| TC_UI_005 | **接收事件更新** | 在任务列表页 | 后台任务状态变更 | 列表该行状态图标自动更新，无需手动刷新 | P0 |
| TC_UI_006 | **连接断开处理** | Core 进程崩溃 | 保持 UI 开启 | 弹出全屏遮罩或 Toast 提示“后端连接断开” | P1 |

### FR-UIHOST-004 声明式 UI 渲染 (Schema Form)

| 用例ID | 场景描述 | 前置条件 | 输入数据 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_UI_007 | **基础控件渲染** | 加载配置页 | `schema={str, int, bool}` | 对应显示 QLineEdit, QSpinBox, QCheckBox | P0 |
| TC_UI_008 | **枚举渲染** | 加载配置页 | `schema={enum: ["A", "B"]}` | 显示 QComboBox，选项正确 | P1 |
| TC_UI_009 | **表单验证与提交** | 必填项为空 | 点击保存 | 显示校验错误提示，不发送 Save 命令 | P1 |

### FR-UIHOST-005 Micro-app 加载与隔离 (Micro-app)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_UI_010 | **受信 Widget 加载** | 模块受信 | 点击模块菜单 | 成功加载并显示模块自定义的 QWidget | P0 |
| TC_UI_011 | **非受信降级** | 模块未签名 | 点击模块菜单 | 显示“安全拦截”提示页，回退到通用配置页 | P0 |
| TC_UI_012 | **Widget 内部崩溃隔离** | Widget 代码含 bug | 触发 bug 代码 | 仅 Widget 区域显示报错信息，主程序不崩溃 (Crash Boundary) | P0 |

## 3. 非功能需求测试 (NFR Testing)

### NFR-UIHOST-001 响应性 (Responsiveness)

*   **TC_UI_PERF_001**: 在加载包含 1000 条日志的任务详情页时，界面是否依然流畅（FPS >= 30）。
*   **TC_UI_PERF_002**: 快速在不同模块间切换，验证内存（RAM）占用是否持续飙升（检查 Widget 销毁/泄漏）。

### NFR-UIHOST-002 兼容性 (Compatibility)

*   **TC_UI_COMPAT_001**: 验证在高 DPI 屏幕（Retina）下的显示缩放是否正常。
