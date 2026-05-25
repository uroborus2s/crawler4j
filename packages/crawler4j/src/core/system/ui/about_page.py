"""Top-level about page with host update controls."""

from __future__ import annotations

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.core.system.config_center import get_config_center
from src.core.system.update_service import get_update_service
from src.core.system.version_service import get_version_service
from src.ui.app_icon import load_app_icon_pixmap
from src.ui.components.button import StyledButton
from src.ui.components.check_box import ToggleSwitch


class UpdateFlowThread(QThread):
    """Run the packaged-app update flow away from the Qt UI thread."""

    completed = pyqtSignal(bool, str)
    failed = pyqtSignal(str)

    def run(self) -> None:
        try:
            service = get_update_service()
            started = bool(service.check_for_updates())
            if started:
                message = str(getattr(service, "last_action_message", "") or "已开始检查更新。")
            else:
                message = str(
                    getattr(service, "last_action_message", "")
                    or getattr(service, "availability_reason", "")
                    or "当前无法检查更新。"
                )
        except Exception as exc:
            self.failed.emit(str(exc) or "更新检查失败。")
            return

        self.completed.emit(started, message)


class AboutPage(QWidget):
    """First-level about page shown in the main sidebar."""

    AUTO_UPDATE_KEY = "system.auto_update"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._config = get_config_center()
        self._update_worker: UpdateFlowThread | None = None
        self._setup_ui()
        self.load_data()
        self._config.config_changed.connect(self._on_config_changed)

    def _setup_ui(self) -> None:
        self.setObjectName("aboutPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            """
            #aboutPage, QWidget#aboutPageContent, QWidget#aboutCanvas, QWidget#aboutUpdateSection, QWidget#aboutRow {
                background: #1a1a24;
            }
            QLabel {
                color: rgba(255, 255, 255, 0.82);
            }
            QLabel#aboutHeroTitle {
                color: white;
                font-size: 30px;
                font-weight: 700;
            }
            QLabel#aboutHeroMeta {
                color: rgba(255, 255, 255, 0.72);
                font-size: 13px;
                font-weight: 500;
            }
            QLabel#aboutHeroBuild {
                color: rgba(255, 255, 255, 0.58);
                font-size: 13px;
                font-weight: 500;
            }
            QLabel#aboutSectionTitle, QLabel#aboutRowTitle {
                color: white;
                font-size: 17px;
                font-weight: 700;
            }
            QLabel#aboutHint, QLabel#aboutStatusLabel {
                color: rgba(255, 255, 255, 0.48);
                font-size: 12px;
            }
            QWidget#aboutSummaryDivider, QWidget#aboutRowDivider {
                background: rgba(255, 255, 255, 0.08);
                min-height: 1px;
                max-height: 1px;
            }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        content = QWidget()
        content.setObjectName("aboutPageContent")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(0)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        canvas_row = QHBoxLayout()
        canvas_row.setContentsMargins(0, 0, 0, 0)
        canvas_row.addStretch()

        canvas = QWidget()
        canvas.setObjectName("aboutCanvas")
        canvas.setMaximumWidth(820)
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(0, 40, 0, 24)
        canvas_layout.setSpacing(28)
        canvas_layout.addWidget(self._create_summary_section())
        canvas_layout.addWidget(self._create_update_section())
        canvas_layout.addStretch()
        canvas_row.addWidget(canvas)
        canvas_row.addStretch()
        content_layout.addLayout(canvas_row)
        content_layout.addStretch()

        root_layout.addWidget(content)

    def _create_summary_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(26)

        hero = QWidget()
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_layout.setSpacing(28)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(120, 120)
        hero_layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text_block = QWidget()
        text_layout = QVBoxLayout(text_block)
        text_layout.setContentsMargins(0, 10, 0, 0)
        text_layout.setSpacing(10)

        self.title_label = QLabel("蛛行演略 · crawler4j")
        self.title_label.setObjectName("aboutHeroTitle")
        text_layout.addWidget(self.title_label)

        self.version_label = QLabel("v0.0.0")
        self.version_label.setObjectName("aboutHeroMeta")
        text_layout.addWidget(self.version_label)

        self.build_label = QLabel("Development Build")
        self.build_label.setObjectName("aboutHeroBuild")
        text_layout.addWidget(self.build_label)
        text_layout.addStretch()

        hero_layout.addWidget(text_block, 1)
        layout.addWidget(hero)
        layout.addWidget(self._create_summary_divider())
        return section

    def _create_update_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("aboutUpdateSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        title = QLabel("更新")
        title.setObjectName("aboutSectionTitle")
        layout.addWidget(title)

        layout.addWidget(self._create_auto_update_row())
        layout.addWidget(self._create_row_divider())
        layout.addWidget(self._create_update_action_row())
        return section

    def _create_auto_update_row(self) -> QWidget:
        row = QWidget()
        row.setObjectName("aboutRow")
        row.setMinimumHeight(56)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 14, 0, 14)
        layout.setSpacing(24)

        label_block = QWidget()
        label_block.setMinimumWidth(280)
        label_block.setMaximumWidth(360)
        label_layout = QVBoxLayout(label_block)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(4)
        title = QLabel("自动检查更新")
        title.setObjectName("aboutRowTitle")
        label_layout.addWidget(title)
        hint = QLabel("控制 Sparkle 或 Velopack 的自动检查行为。")
        hint.setObjectName("aboutHint")
        hint.setWordWrap(True)
        label_layout.addWidget(hint)
        layout.addWidget(label_block, 1)

        toggle_container = QWidget()
        toggle_layout = QHBoxLayout(toggle_container)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.addStretch()
        self.auto_update_toggle = ToggleSwitch()
        self.auto_update_toggle.toggled.connect(self._on_auto_update_toggled)
        toggle_layout.addWidget(self.auto_update_toggle, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(toggle_container)

        return row

    def _create_update_action_row(self) -> QWidget:
        row = QWidget()
        row.setObjectName("aboutRow")
        row.setMinimumHeight(56)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 14, 0, 14)
        layout.setSpacing(24)

        label_block = QWidget()
        label_block.setMinimumWidth(280)
        label_block.setMaximumWidth(360)
        label_layout = QVBoxLayout(label_block)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(4)
        title = QLabel("更新操作")
        title.setObjectName("aboutRowTitle")
        label_layout.addWidget(title)
        self.update_status_label = QLabel("")
        self.update_status_label.setObjectName("aboutStatusLabel")
        self.update_status_label.setWordWrap(True)
        label_layout.addWidget(self.update_status_label)
        layout.addWidget(label_block, 1)

        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        self.check_update_btn = StyledButton("检查更新", variant="secondary", min_height=34, min_width=104)
        self.check_update_btn.clicked.connect(self._on_check_update)
        actions_layout.addWidget(self.check_update_btn)

        self.upgrade_btn = StyledButton("升级", variant="primary", min_height=34, min_width=96)
        self.upgrade_btn.clicked.connect(self._on_upgrade)
        actions_layout.addWidget(self.upgrade_btn)
        layout.addWidget(actions)

        return row

    @staticmethod
    def _create_row_divider() -> QWidget:
        divider = QWidget()
        divider.setObjectName("aboutRowDivider")
        divider.setFixedHeight(1)
        return divider

    @staticmethod
    def _create_summary_divider() -> QWidget:
        divider = QWidget()
        divider.setObjectName("aboutSummaryDivider")
        divider.setFixedHeight(1)
        return divider

    def load_data(self) -> None:
        self._load_build_info()
        self._sync_toggle_from_config()
        self._refresh_update_controls()

    def _load_build_info(self) -> None:
        build_info = get_version_service().get_build_info()
        self.version_label.setText(f"v{build_info.version}")
        if build_info.commit_hash:
            self.build_label.setText(f"Build {build_info.commit_hash[:7]}")
        else:
            self.build_label.setText("Development Build")

        pixmap = load_app_icon_pixmap(120)
        if not pixmap.isNull():
            self.icon_label.setPixmap(pixmap)

    def _sync_toggle_from_config(self) -> None:
        self.auto_update_toggle.blockSignals(True)
        try:
            self.auto_update_toggle.setChecked(bool(self._config.get(self.AUTO_UPDATE_KEY)))
        finally:
            self.auto_update_toggle.blockSignals(False)

    def _on_auto_update_toggled(self, checked: bool) -> None:
        try:
            self._config.set(self.AUTO_UPDATE_KEY, checked)
            get_update_service().configure(auto_check=checked)
        except Exception:
            self._sync_toggle_from_config()
            self._show_update_status("保存自动检查更新设置失败。", tone="error")

    def _on_config_changed(self, key: str, value: object, effect: str) -> None:
        del value, effect
        if key == self.AUTO_UPDATE_KEY:
            self._sync_toggle_from_config()

    def _on_check_update(self) -> None:
        self._trigger_update_flow()

    def _on_upgrade(self) -> None:
        self._trigger_update_flow()

    def _trigger_update_flow(self) -> None:
        if self._is_update_flow_running():
            self._show_update_status("更新检查正在进行中，请稍候。", tone="muted")
            return

        service = get_update_service()
        if not bool(getattr(service, "is_supported", False)):
            message = getattr(service, "availability_reason", "") or "当前无法检查更新。"
            self._show_update_status(message, tone="error")
            return

        self._set_update_controls_busy(True)
        self._show_update_status("正在检查并下载更新，请不要关闭客户端。", tone="muted")

        worker = UpdateFlowThread()
        worker.completed.connect(self._on_update_flow_completed)
        worker.failed.connect(self._on_update_flow_failed)
        worker.finished.connect(self._on_update_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._update_worker = worker
        worker.start()

    def _refresh_update_controls(self) -> None:
        if self._is_update_flow_running():
            self._set_update_controls_busy(True)
            return

        service = get_update_service()
        supported = bool(getattr(service, "is_supported", False))
        reason = str(getattr(service, "availability_reason", "") or "").strip()
        for button in (self.check_update_btn, self.upgrade_btn):
            button.setEnabled(supported)
            button.setToolTip("" if supported else reason)
        if supported:
            self._show_update_status("打包版将使用宿主内置更新器处理检查与升级。", tone="muted")
            return
        self._show_update_status(reason or "当前更新器不可用。", tone="muted")

    def _is_update_flow_running(self) -> bool:
        return self._update_worker is not None and self._update_worker.isRunning()

    def _set_update_controls_busy(self, busy: bool) -> None:
        if busy:
            for button in (self.check_update_btn, self.upgrade_btn):
                button.setEnabled(False)
            return

        service = get_update_service()
        supported = bool(getattr(service, "is_supported", False))
        reason = str(getattr(service, "availability_reason", "") or "").strip()
        for button in (self.check_update_btn, self.upgrade_btn):
            button.setEnabled(supported)
            button.setToolTip("" if supported else reason)

    def _on_update_flow_completed(self, started: bool, message: str) -> None:
        self._set_update_controls_busy(False)
        self._show_update_status(message, tone="success" if started else "error")

    def _on_update_flow_failed(self, message: str) -> None:
        self._set_update_controls_busy(False)
        self._show_update_status(message or "更新检查失败。", tone="error")

    def _on_update_worker_finished(self) -> None:
        worker = self.sender()
        if worker is self._update_worker:
            self._update_worker = None

    def _show_update_status(self, message: str, *, tone: str) -> None:
        color = {
            "success": "#34d399",
            "error": "#f87171",
            "muted": "rgba(255, 255, 255, 0.48)",
        }.get(tone, "rgba(255, 255, 255, 0.48)")
        self.update_status_label.setStyleSheet(f"font-size: 12px; color: {color};")
        self.update_status_label.setText(message)
