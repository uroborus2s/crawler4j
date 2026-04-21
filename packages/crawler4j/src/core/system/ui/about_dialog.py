"""关于信息组件与弹窗。"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.system.update_service import get_update_service
from src.core.system.version_service import get_version_service
from src.ui.app_icon import load_app_icon_pixmap

DOCS_URL = "https://github.com/uroborus2s/crawler4j"


class AboutContentWidget(QWidget):
    """可复用的关于信息内容。"""

    CONTENT_MARGIN = 40

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("aboutContentWidget")
        self._setup_ui()
        self._load_version_info()

    def _setup_ui(self):
        """构建完整信息布局。"""
        self.setStyleSheet("""
            #aboutContentWidget {
                background-color: transparent;
            }
            QLabel {
                color: white;
            }
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(99, 102, 241, 1);
            }
            QPushButton:disabled {
                background: rgba(99, 102, 241, 0.4);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
        )
        layout.setSpacing(16)

        icon_container = QWidget()
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(80, 80)
        self._load_icon()
        icon_layout.addWidget(self.icon_label)
        layout.addWidget(icon_container)

        name_label = QLabel("蛛行演略 · crawler4j")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(name_label)

        self.version_label = QLabel("v0.0.0")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setStyleSheet("font-size: 14px; color: rgba(255, 255, 255, 0.7);")
        layout.addWidget(self.version_label)

        self.build_label = QLabel("")
        self.build_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.build_label.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.5);")
        layout.addWidget(self.build_label)

        layout.addStretch()

        self.update_status_label = QLabel("")
        self.update_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_status_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.update_status_label)

        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.check_update_btn = QPushButton("🔍 检查更新")
        self.check_update_btn.clicked.connect(self._on_check_update)
        btn_layout.addWidget(self.check_update_btn)

        layout.addWidget(btn_container)

        layout.addStretch()

        copyright_label = QLabel("© 2024-2026 蛛行演略（crawler4j）项目组")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.5);")
        layout.addWidget(copyright_label)

        link_label = QLabel(f'<a href="{DOCS_URL}" style="color: #6366f1;">{DOCS_URL}</a>')
        link_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link_label.setOpenExternalLinks(True)
        layout.addWidget(link_label)

    def _load_icon(self):
        """加载应用图标。"""
        pixmap = load_app_icon_pixmap(80)
        if not pixmap.isNull():
            self.icon_label.setPixmap(pixmap)

    def _load_version_info(self):
        """加载版本信息。"""
        service = get_version_service()
        build_info = service.get_build_info()

        self.version_label.setText(f"v{build_info.version}")

        if build_info.commit_hash:
            self.build_label.setText(f"Build {build_info.commit_hash[:7]}")
        else:
            self.build_label.setText("Development Build")

    def _on_check_update(self):
        """检查更新按钮点击。"""
        service = get_update_service()
        self.update_status_label.setText("")

        if service.check_for_updates():
            self.update_status_label.setText(getattr(service, "last_action_message", "") or "✅ 已开始检查更新。")
            self.update_status_label.setStyleSheet("font-size: 13px; color: #4ade80;")
            return

        self.update_status_label.setText(
            getattr(service, "last_action_message", "") or service.availability_reason or "❌ 当前无法检查更新。"
        )
        self.update_status_label.setStyleSheet("font-size: 13px; color: #f87171;")


class AboutDialog(QDialog):
    """关于弹窗。"""

    DIALOG_MIN_WIDTH = 400
    DIALOG_MIN_HEIGHT = 300

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        """配置窗口属性。"""
        self.setWindowTitle("关于 蛛行演略")
        self.setMinimumSize(self.DIALOG_MIN_WIDTH, self.DIALOG_MIN_HEIGHT)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a24;
            }
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(AboutContentWidget(self))
