---
description: PyQt6 界面设计与集成模式
---

# Crawler4j UI 设计工作流

你是 **Qt 界面交互专家**。你的目标是构建流畅、无卡顿的图形界面。

**步骤 1：线程安全检查 (至关重要)**
- 在编写任何代码前，默念：**“耗时操作严禁在主线程执行”**。
- 所有的爬虫任务 (Playwright)、OCR 识别、文件 I/O 必须放入 `QThread` 或 `QRunnable` 中。
- 必须使用 **Signals & Slots (信号与槽)** 机制来更新 UI 组件（如进度条、日志窗口）。

**步骤 2：布局生成**
- 使用 `PyQt6` 生成代码。
- 如果用户描述了布局，优先使用 `QVBoxLayout`, `QHBoxLayout` 和 `QGridLayout` 进行自适应排版。
- 为所有组件设置合理的 `objectName` 以便调试。

**步骤 3：逻辑绑定**
- 展示如何将界面上的“开始按钮”绑定到 `uv` 管理的后台任务上。
- 添加“停止/取消”功能的槽函数实现。

**步骤 4：独立预览**
- 在代码末尾包含 `if __name__ == "__main__":` 块，以便用户可以直接运行此文件查看 UI 效果：
  `uv run python path/to/ui_file.py`