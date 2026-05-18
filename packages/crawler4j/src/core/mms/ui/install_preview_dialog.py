"""模块安装预览对话框。

在安装模块前展示模块信息供用户确认。
"""

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.ui.components.button import StyledButton
from src.ui.components.dialog_window import configure_titled_dialog


class InstallPreviewDialog(QDialog):
    """模块安装预览对话框。
    
    展示待安装模块的元信息供用户确认。
    """
    
    def __init__(
        self,
        manifest,
        warnings: list[str],
        parent=None,
        *,
        title: str = "确认安装模块",
        confirm_text: str = "确认安装",
        source_details: list[tuple[str, str]] | None = None,
    ):
        """初始化对话框。
        
        Args:
            manifest: ModuleManifest 实例
            warnings: 警告信息列表
            parent: 父组件
        """
        super().__init__(parent)
        self._manifest = manifest
        self._warnings = warnings
        self._title = title
        self._confirm_text = confirm_text
        self._source_details = source_details or []
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle(self._title)
        configure_titled_dialog(self)
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

        if self._source_details:
            source_title = QLabel("来源信息")
            source_title.setStyleSheet("color: rgba(255,255,255,0.8); margin-top: 8px;")
            layout.addWidget(source_title)

            source_layout = QVBoxLayout()
            source_layout.setSpacing(8)
            for label, value in self._source_details:
                row = QHBoxLayout()
                key_label = QLabel(f"{label}:")
                key_label.setStyleSheet("color: rgba(255,255,255,0.6); min-width: 80px;")
                value_label = QLabel(value or "-")
                value_label.setWordWrap(True)
                row.addWidget(key_label)
                row.addWidget(value_label, 1)
                source_layout.addLayout(row)
            layout.addLayout(source_layout)
        
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
        
        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.addStretch()

        cancel_btn = StyledButton(
            "取消",
            variant="secondary",
            min_height=40,
            min_width=92,
            horizontal_padding=20,
        )
        cancel_btn.setObjectName("installPreviewCancelButton")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)

        ok_btn = StyledButton(
            self._confirm_text,
            variant="success",
            min_height=40,
            min_width=112,
            horizontal_padding=20,
        )
        ok_btn.setObjectName("installPreviewConfirmButton")
        ok_btn.clicked.connect(self.accept)
        button_row.addWidget(ok_btn)

        layout.addLayout(button_row)
