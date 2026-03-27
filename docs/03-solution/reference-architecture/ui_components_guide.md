# 蛛行演略（crawler4j）UI 架构指南：共享组件与模块化设计

## 1. 概览
蛛行演略（crawler4j）采用 **模块化架构** (概念上类似于微前端 Micro-Frontends)，功能被拆分为独立的模块 (Core, TSM, ATM, REM)。为了确保跨模块的用户体验 (UX) 一致性，我们需要遵循 **共享 UI 库** 的设计规范。

## 2. 桌面 GUI 中的微前端原则

在 Web 微前端架构中，宿主应用 (Host App) 负责组合独立的“远程”应用 (Remote Apps)。在我们的 PyQt 桌面应用中：
- **宿主 (Host)**: `src/ui/app.py` 中的 `Shell` (主窗口)。
- **模块 (Modules/Remotes)**: 业务功能模块，如 `StrategyDetailDialog` (TSM) 或 `EnvListWidget` (REM)。
- **共享库 (Shared Library)**: `src/ui/components` 充当设计系统 (Design System)。

### 核心原则：
1.  **单一事实来源 (Single Source of Truth)**: 所有具有自定义样式的“原子” UI 元素 (按钮、输入框、下拉框) **必须** 来自 `src.ui.components`。
2.  **禁止重复样式 (No Duplicate Styling)**: 模块 **不应** 为通用控件定义自己的 CSS (例如：禁止在模块内写 `QComboBox { padding: 10px }`)。模块应当直接导入预先样式化好的组件。
3.  **单向依赖 (One-Way Dependency)**: 模块依赖 `src.ui.components`。`src.ui.components` **绝不能** 依赖模块。

## 3. 共享组件使用规范

### 下拉框 (StyledComboBox)
我们封装了 `StyledComboBox` 组件，用于修复 macOS 下的样式问题并提供一致的视觉体验。

**❌ 错误用法 (使用了原生控件):**
```python
from PyQt6.QtWidgets import QComboBox

class MyWidget(QWidget):
    def __init__(self):
        self.combo = QComboBox()
        self.combo.setStyleSheet("padding: 10px;") # 👎 错误：重复定义的样式
```

**✅ 正确用法 (使用共享组件):**
```python
# 推荐：使用别名导入，保持代码语义兼容
from src.ui.components.combo_box import StyledComboBox as QComboBox

class MyWidget(QWidget):
    def __init__(self):
        self.combo = QComboBox() # 👍 正确：已包含预设样式和平台兼容性修复
```

## 4. 审计报告 (截至 2026-01-13)

以下组件当前仍在使用原生的 `QComboBox`，需要重构为 `StyledComboBox`：

- **[高优先级] ATM**: `src/core/atm/ui/task_create_dialog.py` (存在重复的内联 CSS) -> **已修复**
- **REM**: `src/core/rem/ui/env_list_widget.py`
- **TSM**: `src/core/tsm/ui/rule_builder.py`
- **TSM**: `src/core/tsm/ui/strategy_editor.py`
- **UI**: `src/ui/components/log_viewer.py`
- **UI**: `src/ui/components/data_table.py`

## 5. 重构策略
重构现有模块的步骤：
1. 引入组件：`from src.ui.components.combo_box import StyledComboBox as QComboBox`
2. 移除原生导入：从 `PyQt6.QtWidgets` 中移除 `QComboBox`。
3. 清理样式：删除本地 CSS (`setStyleSheet`) 中所有关于 `QComboBox` 的定义。
