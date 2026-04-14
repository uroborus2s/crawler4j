"""模块安装预览对话框。

在安装模块前展示模块信息供用户确认。
"""

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class InstallPreviewDialog(QDialog):
    """模块安装预览对话框。
    
    展示待安装模块的元信息供用户确认。
    """
    
    def __init__(self, manifest, warnings: list[str], parent=None):
        """初始化对话框。
        
        Args:
            manifest: ModuleManifest 实例
            warnings: 警告信息列表
            parent: 父组件
        """
        super().__init__(parent)
        self._manifest = manifest
        self._warnings = warnings
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("确认安装模块")
        self.setMinimumWidth(450)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e28;
            }
            QLabel {
                color: white;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel(f"📦 {self._manifest.display_name or self._manifest.name}")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # 元信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)
        
        info = [
            ("模块名称", self._manifest.name),
            ("版本", self._manifest.version),
            ("作者", self._manifest.author or "未知"),
            ("描述", self._manifest.description or "无"),
            ("SDK 要求", self._manifest.sdk_version_range),
        ]
        
        for label, value in info:
            row = QHBoxLayout()
            key_label = QLabel(f"{label}:")
            key_label.setStyleSheet("color: rgba(255,255,255,0.6); min-width: 80px;")
            value_label = QLabel(value)
            value_label.setWordWrap(True)
            row.addWidget(key_label)
            row.addWidget(value_label, 1)
            info_layout.addLayout(row)
        
        layout.addLayout(info_layout)
        
        # 工作流列表
        if self._manifest.workflows:
            wf_title = QLabel(f"📋 包含 {len(self._manifest.workflows)} 个工作流:")
            wf_title.setStyleSheet("color: rgba(255,255,255,0.8); margin-top: 8px;")
            layout.addWidget(wf_title)
            
            for wf in self._manifest.workflows:
                wf_label = QLabel(f"  • {wf.display_name or wf.name}")
                wf_label.setStyleSheet("color: rgba(255,255,255,0.6);")
                layout.addWidget(wf_label)
        
        # 警告信息
        if self._warnings:
            warning_container = QWidget()
            warning_container.setStyleSheet("""
                QWidget {
                    background-color: rgba(250, 204, 21, 0.15);
                    border: 1px solid rgba(250, 204, 21, 0.4);
                    border-radius: 4px;
                    padding: 8px;
                }
            """)
            warning_layout = QVBoxLayout(warning_container)
            warning_layout.setContentsMargins(8, 8, 8, 8)
            
            warning_title = QLabel("⚠️ 警告")
            warning_title.setStyleSheet("color: #facc15; font-weight: bold;")
            warning_layout.addWidget(warning_title)
            
            for warning in self._warnings:
                w_label = QLabel(f"• {warning}")
                w_label.setStyleSheet("color: #facc15;")
                w_label.setWordWrap(True)
                warning_layout.addWidget(w_label)
            
            layout.addWidget(warning_container)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_btn:
            ok_btn.setText("确认安装")
        if cancel_btn:
            cancel_btn.setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        buttons.setStyleSheet("""
            QPushButton {
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton[text="确认安装"] {
                background-color: #4ade80;
                color: black;
            }
            QPushButton[text="取消"] {
                background-color: rgba(255,255,255,0.1);
                color: white;
            }
        """)
        
        layout.addWidget(buttons)
