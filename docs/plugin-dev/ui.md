# UI 开发指南 (UI Development)

Crawler4j 允许插件开发者通过 **PyQt6** 扩展主程序界面。您可以创建自定义的配置页、详情监控页，甚至嵌入新的功能模块。

## 🖼️ UI 扩展机制

插件的 UI 扩展基于 Python 的动态加载机制。您需要编写一个继承自 `QWidget` 的类，并在插件元数据中注册它。

### 1. 编写 UI 组件

```python
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal

class MyConfigPage(QWidget):
    # 定义信号与宿主通信
    config_changed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        self.label = QLabel("自定义配置页面")
        self.btn = QPushButton("保存配置")
        
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.btn)
        
        self.btn.clicked.connect(self.on_save)
        
    def on_save(self):
        # 发送信号
        self.config_changed.emit({"custom_option": True})
```

### 2. 挂载点

Crawler4j 提供了以下标准挂载点：

*   **配置页 (Config Page)**: 替换默认生成的 JSON 配置表单。
*   **侧边栏 (Sidebar)**: 作为一个顶级模块入口（如 "我的仪表盘"）。
*   **任务详情页 (Detail Tab)**: 在任务详情下方添加自定义 Tab 页（如 "实时数据预览"）。

### 3. IPC 通信

虽然 UI 运行在主进程，但任务脚本运行在独立的 Worker 进程/线程。UI 不能直接访问 `TaskContext`。

**推荐通信方式**:
1.  **数据库**: 任务脚本将数据写入 `data.db` 或 `state.db`，UI 通过查询数据库展示。
2.  **事件总线 (EventBus)**: (高级) 如果内核暴露了跨进程事件总线，可通过发布/订阅模式通信。

## 📋 注册 UI

在 `module.yaml` 或清单中声明 UI 入口：

```yaml
ui_extension:
  type: "micro_app"   # 代码型 UI
  entry: "ui.my_page:MyConfigPage"  # 格式: 包名.模块名:类名
  nav_item:
    icon: "🎨"
    label: "我的插件"
```
