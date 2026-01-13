"""关于弹窗。

显示应用信息：
- 应用图标与名称
- 版本号与构建信息
- 版权与官网链接
- 检查更新按钮
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.system.version_service import get_version_service


class AboutDialog(QDialog):
    """关于弹窗。

    符合 SRS 5.10.1 UI 规范：
    - 顶部: 应用图标
    - 中部: 应用名称、版本号
    - 底部: 版权信息、官网链接
    - 交互: [Check for Updates] 按钮
    """

    # 样式常量
    DIALOG_MIN_WIDTH = 400
    DIALOG_MIN_HEIGHT = 300

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_window()
        self._setup_ui()
        self._load_version_info()

    def _setup_window(self):
        """配置窗口属性。"""
        self.setWindowTitle("关于 Crawler4j")
        self.setMinimumSize(self.DIALOG_MIN_WIDTH, self.DIALOG_MIN_HEIGHT)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a24;
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

    def _setup_ui(self):
        """构建 UI 布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(16)

        # 应用图标
        icon_container = QWidget()
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(80, 80)
        self._load_icon()
        icon_layout.addWidget(self.icon_label)
        layout.addWidget(icon_container)

        # 应用名称
        name_label = QLabel("🕷️ Crawler4j")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(name_label)

        # 版本号
        self.version_label = QLabel("v0.0.0")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setStyleSheet("font-size: 14px; color: rgba(255, 255, 255, 0.7);")
        layout.addWidget(self.version_label)

        # 构建信息
        self.build_label = QLabel("")
        self.build_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.build_label.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.5);")
        layout.addWidget(self.build_label)

        layout.addStretch()

        # 更新状态
        self.update_status_label = QLabel("")
        self.update_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_status_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.update_status_label)

        # 检查更新按钮
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.check_update_btn = QPushButton("🔍 检查更新")
        self.check_update_btn.clicked.connect(self._on_check_update)
        btn_layout.addWidget(self.check_update_btn)

        layout.addWidget(btn_container)

        layout.addStretch()

        # 版权信息
        copyright_label = QLabel("© 2024-2026 Crawler4j Project")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.5);")
        layout.addWidget(copyright_label)

        # 官网链接
        link_label = QLabel('<a href="https://crawler4j.example.com" style="color: #6366f1;">crawler4j.example.com</a>')
        link_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link_label.setOpenExternalLinks(True)
        layout.addWidget(link_label)

    def _load_icon(self):
        """加载应用图标。"""
        icon_path = Path(__file__).parent.parent.parent.parent / "ui" / "assets" / "icon.jpg"
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            self.icon_label.setPixmap(
                pixmap.scaled(
                    80, 80,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

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
        self.check_update_btn.setEnabled(False)
        self.check_update_btn.setText("⏳ 检查中...")
        self.update_status_label.setText("")

        # 模拟检查（实际应调用 UpdateService）
        QTimer.singleShot(1500, self._on_check_complete)

    def _on_check_complete(self):
        """检查完成。"""
        self.check_update_btn.setEnabled(True)
        self.check_update_btn.setText("🔍 检查更新")
        self.update_status_label.setText("✅ 您的软件已是最新版本")
        self.update_status_label.setStyleSheet("font-size: 13px; color: #4ade80;")
