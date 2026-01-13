"""更新弹窗。

显示更新信息和下载进度：
- 新版本信息
- Release Notes
- 下载进度条
- 操作按钮
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.system.update_service import UpdateInfo


class UpdateDialog(QDialog):
    """更新弹窗。

    符合 SRS 5.10.2 UI 规范：
    - 标题: 新版本号
    - 摘要: Release Notes
    - 操作: [Update Now] / [Remind Later] / [Skip]
    - 进度: 下载进度条
    """

    DIALOG_MIN_WIDTH = 500
    DIALOG_MIN_HEIGHT = 400

    def __init__(
        self,
        update_info: Optional[UpdateInfo] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._update_info = update_info
        self._is_downloading = False
        self._setup_window()
        self._setup_ui()

        if update_info:
            self._populate_info(update_info)

    def _setup_window(self):
        """配置窗口属性。"""
        self.setWindowTitle("软件更新")
        self.setMinimumSize(self.DIALOG_MIN_WIDTH, self.DIALOG_MIN_HEIGHT)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a24;
            }
            QLabel {
                color: white;
            }
            QScrollArea {
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                background-color: rgba(30, 30, 40, 0.8);
            }
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: rgba(255, 255, 255, 0.1);
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6366f1, stop:1 #818cf8);
                border-radius: 4px;
            }
        """)

    def _setup_ui(self):
        """构建 UI 布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题
        self.title_label = QLabel("🎉 发现新版本")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(self.title_label)

        # 版本号
        self.version_label = QLabel("v0.0.0 → v0.0.0")
        self.version_label.setStyleSheet("font-size: 14px; color: rgba(255, 255, 255, 0.7);")
        layout.addWidget(self.version_label)

        # 关键更新标记
        self.critical_label = QLabel("⚠️ 此更新包含重要安全修复")
        self.critical_label.setStyleSheet("font-size: 13px; color: #facc15;")
        self.critical_label.hide()
        layout.addWidget(self.critical_label)

        # Release Notes
        notes_label = QLabel("更新内容:")
        notes_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(notes_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(150)

        self.notes_content = QLabel()
        self.notes_content.setWordWrap(True)
        self.notes_content.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.notes_content.setStyleSheet("padding: 12px; font-size: 13px;")
        self.notes_content.setText("暂无更新说明")
        scroll_area.setWidget(self.notes_content)

        layout.addWidget(scroll_area)

        # 进度区域
        self.progress_container = QWidget()
        progress_layout = QVBoxLayout(self.progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(24)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("准备下载...")
        self.progress_label.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.6);")
        progress_layout.addWidget(self.progress_label)

        self.progress_container.hide()
        layout.addWidget(self.progress_container)

        layout.addStretch()

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        btn_style_secondary = """
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
            }
        """

        btn_style_primary = """
            QPushButton {
                background: rgba(99, 102, 241, 0.9);
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(99, 102, 241, 1);
            }
            QPushButton:disabled {
                background: rgba(99, 102, 241, 0.4);
            }
        """

        self.skip_btn = QPushButton("跳过此版本")
        self.skip_btn.setStyleSheet(btn_style_secondary)
        self.skip_btn.clicked.connect(self._on_skip)
        btn_layout.addWidget(self.skip_btn)

        self.later_btn = QPushButton("稍后提醒")
        self.later_btn.setStyleSheet(btn_style_secondary)
        self.later_btn.clicked.connect(self._on_remind_later)
        btn_layout.addWidget(self.later_btn)

        btn_layout.addStretch()

        self.update_btn = QPushButton("🚀 立即更新")
        self.update_btn.setStyleSheet(btn_style_primary)
        self.update_btn.clicked.connect(self._on_update_now)
        btn_layout.addWidget(self.update_btn)

        layout.addLayout(btn_layout)

    def _populate_info(self, info: UpdateInfo):
        """填充更新信息。"""
        from src.core.system.version_service import get_version_service

        current = get_version_service().get_current_version()
        self.version_label.setText(f"v{current} → v{info.version}")
        self.notes_content.setText(info.release_notes or "暂无更新说明")

        if info.is_critical:
            self.critical_label.show()

    def _on_update_now(self):
        """立即更新。"""
        self._is_downloading = True
        self.update_btn.setEnabled(False)
        self.update_btn.setText("⏳ 下载中...")
        self.skip_btn.hide()
        self.later_btn.hide()
        self.progress_container.show()

        # TODO: 调用 UpdateService.download_update()

    def _on_remind_later(self):
        """稍后提醒。"""
        self.reject()

    def _on_skip(self):
        """跳过此版本。"""
        # TODO: 将版本加入忽略列表
        self.reject()

    def update_progress(self, downloaded: int, total: int):
        """更新下载进度。

        Args:
            downloaded: 已下载字节数
            total: 总字节数
        """
        if total > 0:
            percent = int(downloaded / total * 100)
            self.progress_bar.setValue(percent)

            # 格式化显示
            downloaded_mb = downloaded / 1024 / 1024
            total_mb = total / 1024 / 1024
            self.progress_label.setText(f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB ({percent}%)")

    def download_complete(self):
        """下载完成。"""
        self._is_downloading = False
        self.update_btn.setText("🔄 重启并安装")
        self.update_btn.setEnabled(True)
        self.progress_label.setText("✅ 下载完成，点击按钮重启安装")
