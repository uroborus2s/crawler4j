# 5.5 UI Host & 微前端承载（UI Framework & Micro-frontend Host）

## 5.5.1 需求说明

UI Host 是框架对用户的统一交互入口，负责承载：

- Core 管理页（模块、运行、日志、运维等）
- 模块提供的 UI 扩展（声明式 UI / micro-app）
- UI 与 Core 的命令/事件通道

UI Host MUST：

- 以“模块命名空间”为边界进行路由与资源隔离，避免模块 UI 相互污染
- 对不受信 micro-app 严格禁用，并提供降级页面
- 对任意模块 UI 的加载失败提供一致的错误呈现与兜底交互

## 5.5.2 需求分析分解

### 5.5.2.1 功能性需求（FR）

- FR-UIHOST-001 Shell 与路由：提供统一 Shell（导航/布局）与模块命名空间路由（`/modules/{module_name}/...`）。
- FR-UIHOST-002 命令通道（UI → Core）：以 RPC/HTTP/WebSocket 等形式向 Core 发起命令（安装、刷新、运行、读写 settings 等）。
- FR-UIHOST-003 事件总线（Core → UI）：订阅任务运行事件、模块变更事件与运维事件，并将其分发到 UI 组件。
- FR-UIHOST-004 模块 UI（声明式）：支持基于 JSON/YAML 的 UI 描述渲染（零代码执行）。
- FR-UIHOST-005 模块 UI（micro-app）：支持加载受信的微前端应用，并提供能力边界与最小 API。
- FR-UIHOST-006 降级与兜底：模块 UI 不可用时必须回落到通用模块页（展示模块信息、工作流、可运行入口与错误原因）。
- FR-UIHOST-007 卸载与资源回收：模块卸载/刷新后，相关路由、缓存与事件订阅必须被解除。

### 5.5.2.2 非功能性需求（NFR）

- NFR-UIHOST-001 安全性：micro-app 必须受信（签名/白名单/内置来源之一），并且不得拥有超出声明的能力。
- NFR-UIHOST-002 可观测性：记录 micro-app 加载、路由切换、命令调用与错误堆栈（可关联 module_name）。
- NFR-UIHOST-003 可用性：UI Host 自身失败不得阻断 Core 继续运行任务（UI 与执行解耦）。

## 5.5.3 系统整体设计（结构/路由/安全/降级）

### 5.5.3.1 Shell 与路由

- 顶层 Shell：提供统一导航、用户态操作入口与全局状态（任务运行中、告警等）。
- 模块命名空间路由：
  - `/modules`：模块列表
  - `/modules/{module_name}`：通用模块页（默认兜底）
  - `/modules/{module_name}/ui/*`：模块 UI 扩展（声明式或 micro-app）

### 5.5.3.2 UI → Core 命令通道

UI Host 对 Core 的交互应通过“命令通道”完成，建议特征：

- 幂等与可重试：列表/读取类请求可重试
- 统一错误结构：至少包含 `code / message / hint / correlation_id`
- 对写操作进行权限门控（若系统有鉴权能力）

### 5.5.3.3 Core → UI 事件总线

事件总线用于承载：

- task_run 生命周期事件（started/progress/log/finished/failed/cancelled）
- module_registry 变更事件（installed/uninstalled/upgraded/refreshed/enabled/disabled）
- env 事件（pool saturation/unhealthy instances）

事件应支持按 module_name / task_run_id 过滤订阅。

### 5.5.3.4 模块 UI 扩展类型与装载策略 (Module UI Loading)

在 PyQt 桌面环境架构下，UI Host 支持两种不同安全等级的加载机制。

#### 机制 A：声明式 UI (Schema-driven) —— **[推荐]**

- **原理**: 模块仅提供数据描述文件 (`config_schema.json` / `ui_schema.json`)，不包含 UI 代码。
- **加载流程**:
    1. Core 读取模块目录下的 Schema 文件。
    2. UI Host 使用内置的表单引擎 (SchemaFormWidget) 解析 JSON。
    3. 动态生成对应的 Qt 控件 (QLineEdit, QSpinBox, QComboBox)。
- **优点**: 
    - **绝对安全**: 不执行模块侧 Python 代码，由 Host 渲染。
    - **一致性**: 所有模块配置页风格统一。
- **适用场景**: 任务配置、参数输入、简单状态展示。

#### 机制 B：编程式 UI (Code-driven Micro-app) —— **[高级]**

- **原理**: 模块提供遵循接口的 Python 类 (`class ModuleWidget(BaseModuleWidget)`)。
- **加载流程** (Dynamic Import):
    1. UI Host 扫描模块目录，寻找入口点 (e.g., `ui.py` 中的 `entry_point`)。
    2. 使用 `importlib` 动态加载该 Python 模块。
    3. 实例化 widget 对象：`widget = ModuleClass(context_bridge)`。
    4. 将 widget 嵌入主界面的 `QTabWidget` 或 `QStackedWidget`。
- **安全约束 (MUST)**:
    - **接口隔离**: Widget 必须只接受 `ContextBridge` 注入，**禁止**直接导入 Core 单例。
    - **主线程保护**: Widget 内部若有耗时操作，**必须**使用 QThread/QRunnable，禁止阻塞 UI 线程。
    - **异常隔离**: UI Host 需包裹 try-catch，若 Widget 初始化或绘制崩溃，也就是显示“模块 UI 加载失败”的占位页，不得导致整个 App 崩溃。

#### 降级规则 (Fallback)

1. 若模块未提供任何 UI -> 使用 **默认通用页** (Generic Module Page)，仅展示基本信息及 RAW 配置编辑器。
2. 若 `importlib` 加载失败 -> 回落到默认通用页，并显示 traceback 供以调试。

### 5.5.3.5 安全与隔离

- 命名空间隔离：模块静态资源不得污染全局；建议按模块前缀进行资源命名。
- 能力边界：micro-app 只能通过 UI Host 提供的最小 API 与 Core 交互（不得直接访问 Core 内部服务）。
- 信任门控：受信策略由 5.1 的模块管理系统给出，UI Host 只执行“是否允许装载”的判定与记录审计信息。

## 5.5.4 功能清单

- Shell & Routing（命名空间隔离）
- 命令通道（UI→Core）
- 事件总线（Core→UI）
- Module UI：代码 micro-app（受信）
- Module UI：声明式 UI（零代码执行）
- 卸载与资源回收
