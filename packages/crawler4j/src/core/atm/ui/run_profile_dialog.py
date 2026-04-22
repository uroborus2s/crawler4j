"""运行模板编辑弹窗。"""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.mms import get_module_registry
from src.core.mms.service import get_module_service
from src.core.rem.ip_pool import get_ip_pool_manager
from src.core.rem.provider import (
    VIRTUALBROWSER_DEFAULT_CHROME_VERSION,
    VIRTUALBROWSER_SUPPORTED_CHROME_VERSIONS,
)
from src.core.rem.virtualbrowser_fingerprint import (
    VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY,
    generate_device_name,
    generate_mac_address,
    generate_random_user_agent,
)
from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    CreationConfig,
    CreationLifecycle,
    EnvType,
    ExecutionContext,
    RunProfile,
    ResourceConfig,
)
from src.core.atm.controller import selector_returns_none
from src.ui.components.combo_box import StyledComboBox as QComboBox
from src.ui.components.spin_box import StyledSpinBox as QSpinBox


class WorkflowSelector(QWidget):
    """工作流选择组合控件 (Module + Workflow)。"""

    def __init__(self, parent=None, show_module=True, show_none_option=False):
        super().__init__(parent)
        self._show_module = show_module
        self._show_none_option = show_none_option
        self._setup_ui()
        if show_module:
            self._load_modules()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0) # Remove spacing to behave like a single control when module is hidden

        # 模块下拉框
        self.module_combo = QComboBox()
        self.module_combo.setPlaceholderText("选择模块")
        # Module combo should not take too much space if visible alongside workflow
        self.module_combo.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.module_combo.setMinimumWidth(120)
        self.module_combo.currentTextChanged.connect(self._on_module_changed)
        layout.addWidget(self.module_combo)
        
        # Spacer if both are visible
        self.spacer = QWidget()
        self.spacer.setFixedWidth(8)
        self.spacer.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.spacer)

        # 工作流下拉框
        self.workflow_combo = QComboBox()
        self.workflow_combo.setPlaceholderText("选择工作流")
        # Match "Scaling Mode" combo box behavior (Preferred instead of Expanding)
        self.workflow_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.workflow_combo)
        
        if not self._show_module:
            self.module_combo.hide()
            self.spacer.hide()

    def set_module_filter(self, module_name: str | None):
        """设置模块过滤器。"""
        current_wf = self._current_workflow_value()
        
        self._filter_module = module_name
        
        if self._show_module:
            has_filter = bool(module_name)
            self.module_combo.setVisible(not has_filter)
            self.spacer.setVisible(not has_filter)
            
            if module_name:
                # Force module selection
                index = self.module_combo.findText(module_name)
                if index >= 0:
                    self.module_combo.setCurrentIndex(index)
                self._on_module_changed(module_name)
            else:
                self.module_combo.setCurrentIndex(-1)
        else:
            # Pure workflow mode: just load workflows for this module
             self._on_module_changed(module_name)

        if current_wf:
            idx = self._find_workflow_index(current_wf)
            if idx >= 0:
                self.workflow_combo.setCurrentIndex(idx)

    def _load_modules(self):
        try:
            registry = get_module_registry()
            # Force refresh might be needed if registry is empty
            if not registry.list_modules():
                registry.refresh() 
            
            modules = registry.list_modules()
            self.module_combo.clear()
            for m in modules:
                self.module_combo.addItem(m.name, m)
            self.module_combo.setCurrentIndex(-1)
        except Exception:
            pass  # MMS might not be ready

    def _on_module_changed(self, module_name):
        self.workflow_combo.clear()
        
        if self._show_none_option:
            self.workflow_combo.addItem("不执行 (None)", "")

        if not module_name:
            return
            
        try:
            registry = get_module_registry()
            module = registry.get_module(module_name)
            if module and module.manifest.workflows:
                for wf in module.manifest.workflows:
                    self.workflow_combo.addItem(wf.display_name or wf.name, wf.name)
            elif not module:
                # Try refresh ?
                registry.refresh()
                module = registry.get_module(module_name)
                if module and module.manifest.workflows:
                    for wf in module.manifest.workflows:
                        self.workflow_combo.addItem(wf.display_name or wf.name, wf.name)
        except Exception:
            pass

    def _current_workflow_value(self) -> str:
        current_data = self.workflow_combo.currentData()
        if isinstance(current_data, str):
            return current_data
        return self.workflow_combo.currentText()

    def _find_workflow_index(self, workflow_name: str) -> int:
        for index in range(self.workflow_combo.count()):
            item_data = self.workflow_combo.itemData(index)
            if item_data == workflow_name or self.workflow_combo.itemText(index) == workflow_name:
                return index
        return -1

    def get_value(self) -> tuple[str, str]:
        """返回 (module, workflow)"""
        current_data = self.workflow_combo.currentData()
        if current_data == "":
            wf = ""
        elif isinstance(current_data, str):
            wf = current_data
        else:
            wf = self.workflow_combo.currentText()
        
        if not self._show_module:
            return getattr(self, "_filter_module", "") or "", wf
            
        return self.module_combo.currentText(), wf

    def set_value(self, module: str, workflow: str):
        if self._show_module:
            index = self.module_combo.findText(module)
            if index >= 0:
                self.module_combo.setCurrentIndex(index)
            
        wf_index = self._find_workflow_index(workflow)
        if wf_index >= 0:
            self.workflow_combo.setCurrentIndex(wf_index)
        else:
            if workflow:
                self.workflow_combo.addItem(workflow, workflow)
                self.workflow_combo.setCurrentIndex(self.workflow_combo.count() - 1)


VIRTUALBROWSER_LANGUAGE_OPTIONS = (
    {"label": "英语", "language": "en-US", "value": "en-US,en"},
    {"label": "简体中文", "language": "zh-CN", "value": "zh-CN,zh"},
    {"label": "繁体中文", "language": "zh-TW", "value": "zh-TW,zh"},
    {"label": "日语", "language": "ja-JP", "value": "ja-JP,ja"},
    {"label": "韩语", "language": "ko-KR", "value": "ko-KR,ko"},
    {"label": "法语", "language": "fr-FR", "value": "fr-FR,fr"},
    {"label": "德语", "language": "de-DE", "value": "de-DE,de"},
    {"label": "西班牙语", "language": "es-AR", "value": "es-AR,es"},
    {"label": "西班牙语", "language": "es-ES", "value": "es-ES,es"},
    {"label": "葡萄牙语", "language": "pt-BR", "value": "pt-BR,pt"},
    {"label": "葡萄牙语", "language": "pt-PT", "value": "pt-PT,pt"},
    {"label": "俄语", "language": "ru-RU", "value": "ru-RU,ru"},
    {"label": "越南语", "language": "vi-VN", "value": "vi-VN,vi"},
    {"label": "泰语", "language": "th-TH", "value": "th-TH,th"},
    {"label": "印度尼西亚语", "language": "id-ID", "value": "id-ID,id"},
    {"label": "马来语", "language": "ms-MY", "value": "ms-MY,ms"},
    {"label": "意大利语", "language": "it-IT", "value": "it-IT,it"},
    {"label": "土耳其语", "language": "tr-TR", "value": "tr-TR,tr"},
    {"label": "阿拉伯语", "language": "ar-SA", "value": "ar-SA,ar"},
    {"label": "印地语", "language": "hi-IN", "value": "hi-IN,hi"},
    {"label": "孟加拉语", "language": "bn-BD", "value": "bn-BD,bn"},
    {"label": "波斯语", "language": "fa-IR", "value": "fa-IR,fa"},
    {"label": "达里语", "language": "prs-AF", "value": "prs-AF,fa"},
    {"label": "普什图语", "language": "ps-AF", "value": "ps-AF,ps"},
    {"label": "阿尔巴尼亚语", "language": "sq-AL", "value": "sq-AL,sq"},
    {"label": "亚美尼亚语", "language": "hy-AM", "value": "hy-AM,hy"},
    {"label": "加泰罗尼亚语", "language": "ca-ES", "value": "ca-ES,ca"},
)

VIRTUALBROWSER_SCREEN_RESOLUTIONS = (
    ("1280 x 960", (1280, 960)),
    ("1280 x 1024", (1280, 1024)),
    ("1360 x 768", (1360, 768)),
    ("1400 x 900", (1400, 900)),
    ("1400 x 1050", (1400, 1050)),
    ("1440 x 900", (1440, 900)),
    ("1600 x 900", (1600, 900)),
    ("1600 x 1200", (1600, 1200)),
    ("1680 x 1050", (1680, 1050)),
    ("1920 x 1080", (1920, 1080)),
    ("1920 x 1200", (1920, 1200)),
    ("2048 x 1152", (2048, 1152)),
    ("2560 x 1440", (2560, 1440)),
)

SEC_CH_UA_VALUE_PATTERN = re.compile(r'"(?P<brand>[^"]+)"\s*;\s*v="(?P<version>[^"]+)"')


def _format_utc_offset(offset: timedelta) -> tuple[str, int | float]:
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    abs_minutes = abs(total_minutes)
    hours, minutes = divmod(abs_minutes, 60)
    value = total_minutes / 60
    if total_minutes % 60 == 0:
        value = total_minutes // 60
    return f"(UTC{sign}{hours:02d}:{minutes:02d})", value


def _build_virtualbrowser_timezone_options() -> tuple[dict[str, object], ...]:
    try:
        timezone_names = sorted(
            name
            for name in available_timezones()
            if "/" in name or name.startswith("Etc/")
        )
    except Exception:
        timezone_names = [
            "Etc/UTC",
            "Asia/Hong_Kong",
            "Asia/Shanghai",
            "Asia/Tokyo",
            "Europe/London",
            "America/Los_Angeles",
        ]

    options: list[dict[str, object]] = []
    for timezone_name in timezone_names:
        try:
            offset = datetime.now(ZoneInfo(timezone_name)).utcoffset() or timedelta(0)
        except Exception:
            continue
        offset_label, offset_value = _format_utc_offset(offset)
        options.append(
            {
                "label": f"{offset_label} {timezone_name}",
                "zone": f"{offset_label} {timezone_name}",
                "utc": timezone_name,
                "locale": "",
                "value": offset_value,
                "_sort_minutes": int(offset.total_seconds() // 60),
            }
        )

    options.sort(key=lambda item: (item["_sort_minutes"], str(item["utc"])))
    for option in options:
        option.pop("_sort_minutes", None)
    return tuple(options)


VIRTUALBROWSER_TIMEZONE_OPTIONS = _build_virtualbrowser_timezone_options()
VIRTUALBROWSER_WEBGL_RENDERER_OPTIONS: dict[str, tuple[str, ...]] = {
    "Google Inc. (Intel Inc.)": (
        "ANGLE (Intel Inc., Intel(R) UHD Graphics 630, OpenGL 4.1)",
        "ANGLE (Intel Inc., Intel(R) Iris(TM) Plus Graphics OpenGL Engine, OpenGL 4.1)",
        "ANGLE (Intel Inc., SKL Graphics, OpenGL 4.1)",
        "ANGLE (Intel Inc., Intel HD Graphics 5000 OpenGL Engine, OpenGL 4.1)",
        "ANGLE (Intel Inc., Intel(R) Iris(TM) Plus Graphics OpenGL Engine (1x6x8 (fused) LP, OpenGL 4.1)",
        "ANGLE (Intel Inc., Intel Iris Pro OpenGL Engine, OpenGL 4.1)",
        "ANGLE (Intel Inc., Intel(R) HD Graphics 530, OpenGL 4.1)",
        "ANGLE (Intel Inc., Intel(R) Iris(TM) Graphics 6100, OpenGL 4.1)",
    ),
    "Google Inc. (NVIDIA Corporation)": (
        "ANGLE (NVIDIA Corporation, NVIDIA GeForce GTX 1060/PCIe/SSE2, OpenGL 4.1)",
        "ANGLE (NVIDIA Corporation, NVIDIA GeForce GTX 1650/PCIe/SSE2, OpenGL 4.1)",
        "ANGLE (NVIDIA Corporation, NVIDIA GeForce RTX 3060/PCIe/SSE2, OpenGL 4.1)",
    ),
    "Google Inc. (AMD)": (
        "ANGLE (AMD, AMD Radeon Pro 5300M OpenGL Engine, OpenGL 4.1)",
        "ANGLE (AMD, AMD Radeon RX 580 OpenGL Engine, OpenGL 4.1)",
        "ANGLE (AMD, AMD Radeon(TM) Graphics, OpenGL 4.1)",
    ),
    "Google Inc. (Apple)": (
        "ANGLE (Apple, Apple M1, OpenGL 4.1)",
        "ANGLE (Apple, Apple M2, OpenGL 4.1)",
    ),
}


class SegmentedOptionControl(QWidget):
    """轻量分段按钮选择器，用于替代简单模式下拉框。"""

    def __init__(self, options: list[tuple[str, object]], on_change=None, parent=None):
        super().__init__(parent)
        self._options = list(options)
        self._on_change = on_change
        self._current_value = self._options[0][1] if self._options else None
        self._buttons: dict[object, QPushButton] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        total = len(self._options)
        for index, (text, value) in enumerate(self._options):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            radius_left = "6px" if index == 0 else "0"
            radius_right = "6px" if index == total - 1 else "0"
            border_left = "1px" if index == 0 else "0"
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background: rgba(255, 255, 255, 0.05);
                    color: rgba(255, 255, 255, 0.88);
                    border-top: 1px solid rgba(255, 255, 255, 0.1);
                    border-right: 1px solid rgba(255, 255, 255, 0.1);
                    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                    border-left: {border_left} solid rgba(255, 255, 255, 0.1);
                    border-top-left-radius: {radius_left};
                    border-bottom-left-radius: {radius_left};
                    border-top-right-radius: {radius_right};
                    border-bottom-right-radius: {radius_right};
                    min-height: 32px;
                    padding: 0 18px;
                }}
                QPushButton:checked {{
                    background: #6366f1;
                    border-color: #6366f1;
                    color: white;
                    font-weight: bold;
                }}
                QPushButton:disabled {{
                    color: rgba(255, 255, 255, 0.35);
                }}
                """
            )
            button.clicked.connect(
                lambda checked, current=value: self.set_current_data(current, emit_change=True)
            )
            self._buttons[value] = button
            layout.addWidget(button)

        layout.addStretch()
        if self._options:
            self.set_current_data(self._options[0][1], emit_change=False)

    def currentData(self):
        return self._current_value

    def set_current_data(self, value, emit_change: bool = False) -> None:
        if value not in self._buttons:
            return
        self._current_value = value
        for option_value, button in self._buttons.items():
            button.setChecked(option_value == value)
        if emit_change and callable(self._on_change):
            self._on_change()

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 - Qt API
        super().setEnabled(enabled)
        for button in self._buttons.values():
            button.setEnabled(enabled)


class ToggleSwitch(QCheckBox):
    """自绘滑动开关，避免纯样式化 QCheckBox 在深色主题下显示异常。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText("")
        self.setFixedSize(54, 30)

    def sizeHint(self) -> QSize:
        return QSize(54, 30)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        knob_diameter = rect.height() - 6.0
        knob_y = rect.top() + (rect.height() - knob_diameter) / 2
        knob_x = rect.right() - knob_diameter - 3.0 if self.isChecked() else rect.left() + 3.0

        if self.isEnabled():
            track_color = QColor("#6366f1") if self.isChecked() else QColor(60, 60, 72)
            border_color = QColor("#6366f1") if self.isChecked() else QColor(255, 255, 255, 36)
            knob_color = QColor(255, 255, 255)
        else:
            track_color = QColor(255, 255, 255, 18)
            border_color = QColor(255, 255, 255, 24)
            knob_color = QColor(255, 255, 255, 120)

        painter.setPen(QPen(border_color, 1.0))
        painter.setBrush(track_color)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        knob_rect = QRectF(knob_x, knob_y, knob_diameter, knob_diameter)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(knob_color)
        painter.drawEllipse(knob_rect)


class RunProfileDialog(QDialog):
    """运行模板编辑弹窗。"""

    def __init__(self, run_profile: RunProfile | None = None, parent=None, read_only: bool = False):
        super().__init__(parent)
        self._run_profile = run_profile or self._default_run_profile()
        self._is_new = run_profile is None
        self._read_only = read_only
        self._setup_ui()
        self._load_run_profile()
        
        if self._read_only:
             self._set_read_only()

    def _setup_ui(self):
        self.setWindowTitle("配置运行模板")
        
        # Responsive sizing (60% width, 95% height of screen)
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            w = int(screen_geo.width() * 0.6)
            h = int(screen_geo.height() * 0.95)
        else:
            # Fallback for headless or special cases
            w, h = 960, 700
            
        self.resize(w, h)
        
        self.setStyleSheet("""
            QDialog { background: rgb(30, 30, 40); }
            QLabel { color: rgba(255, 255, 255, 0.9); font-size: 13px; }
            QLineEdit, QSpinBox, QPlainTextEdit {
                background: rgba(40, 40, 50, 0.9);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 5px 8px;
                min-height: 25px;
                min-width: 280px;
            }
            QLineEdit:focus, QSpinBox:focus, QPlainTextEdit:focus {
                border-color: #6366f1;
                background: rgba(50, 50, 60, 1);
            }
            QGroupBox {
                color: #a5b4fc;
                font-weight: bold;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                margin-top: 20px;
                padding: 20px 10px 10px 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                background: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.7);
                padding: 8px 24px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected { background: #6366f1; color: white; font-weight: bold; }
            QTabBar::tab:hover { background: rgba(255, 255, 255, 0.1); }
            
            /* StyledComboBox handles its own styling, removed duplicated QComboBox CSS here */
            /* StyledSpinBox handles its own styling, removed duplicated QSpinBox CSS here */
        """)


        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 模式切换
        mode_layout = QHBoxLayout()
        self.form_btn = QPushButton("📝 表单配置")
        self.yaml_btn = QPushButton("📄 YAML 源码")
        
        for btn in [self.form_btn, self.yaml_btn]:
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.05);
                    color: white;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    padding: 6px 16px;
                    border-radius: 4px;
                }
                QPushButton:checked { background: #4f46e5; border-color: #4f46e5; }
            """)
        
        self.form_btn.setChecked(True)
        self.form_btn.clicked.connect(lambda: self._switch_mode("form"))
        self.yaml_btn.clicked.connect(lambda: self._switch_mode("yaml"))

        mode_layout.addWidget(self.form_btn)
        mode_layout.addWidget(self.yaml_btn)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # 堆叠挂件
        self.stack = QStackedWidget()
        
        # 1. 表单模式
        self.form_tabs = QTabWidget()
        self._setup_form_tabs()
        self.stack.addWidget(self.form_tabs)

        # 2. YAML 模式
        self.yaml_widget = self._create_yaml_widget()
        self.stack.addWidget(self.yaml_widget)

        layout.addWidget(self.stack, 1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setStyleSheet("background: rgba(255,255,255,0.1); border:none; color:white; border-radius:4px;")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("保存运行模板")
        save_btn.setFixedSize(100, 32)
        save_btn.setStyleSheet("background: #10b981; border:none; color:white; font-weight:bold; border-radius:4px;")
        save_btn.clicked.connect(self._on_save)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        
        if self._read_only:
             save_btn.hide()
             cancel_btn.setText("关闭")

        layout.addLayout(btn_layout)

    def _set_read_only(self):
        """设置只读模式。"""
        # Disable all input widgets
        for widget in self.findChildren(
            (QLineEdit, QPlainTextEdit, QSpinBox, QCheckBox, QComboBox, SegmentedOptionControl)
        ):
             # QComboBox and QCheckBox use setEnabled
             if isinstance(widget, (QComboBox, QCheckBox, SegmentedOptionControl)):
                 widget.setEnabled(False)
             elif isinstance(widget, (QLineEdit, QPlainTextEdit, QSpinBox)):
                 widget.setReadOnly(True)
        
        # Helper to disable WorkflowSelectors
        # We need to explicitly call setEnabled on them because they are complex widgets
        # Or better, let's implement set_read_only on WorkflowSelector if they are custom
        # But for now, let's just find them by type if we can, or manually access them.
        # findChildren might not find them if they are wrapped.
        
        self.script_selector.setEnabled(False)
        for button_name in (
            "ua_default_btn",
            "ua_custom_btn",
            "ua_random_btn",
            "sec_ch_ua_default_btn",
            "sec_ch_ua_custom_btn",
            "sec_ch_ua_add_btn",
            "device_name_regen_btn",
            "mac_regen_btn",
        ):
            button = getattr(self, button_name, None)
            if button is not None:
                button.setEnabled(False)
        for row_widget in getattr(self, "_sec_ch_ua_rows", []):
            row_widget.remove_btn.setEnabled(False)
        
    def _default_run_profile(self) -> RunProfile:
        return RunProfile(
            resource=ResourceConfig(
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.CREATE,
                    provider="virtualbrowser",
                    env_type=EnvType.VIRTUAL_BROWSER,
                    creation=CreationConfig(lifecycle=CreationLifecycle.PERSISTENT),
                ),
            )
        )

    def _setup_form_tabs(self):
        self.tab_basic = QWidget()
        self._setup_basic_tab(self.tab_basic)
        self.form_tabs.addTab(self.tab_basic, "运行配置")
        self.form_tabs.tabBar().hide()

    def _create_form_layout(self, parent):
        form = QFormLayout(parent)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(20)
        return form

    def _add_combo_row(
        self,
        form: QFormLayout,
        label: str,
        items: list[tuple[str, object]],
    ) -> QComboBox:
        combo = QComboBox()
        for text, value in items:
            combo.addItem(text, value)
        form.addRow(label, combo)
        return combo

    def _add_segmented_row(
        self,
        form: QFormLayout,
        label: str,
        items: list[tuple[str, object]],
        *,
        on_change=None,
    ) -> SegmentedOptionControl:
        control = SegmentedOptionControl(items, on_change=on_change)
        form.addRow(label, control)
        return control

    def _create_editable_combo(self, placeholder: str, options: tuple[str, ...]) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(list(options))
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if combo.lineEdit() is not None:
            combo.lineEdit().setPlaceholderText(placeholder)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.setMaxVisibleItems(min(max(len(options), 8), 12))
        self._fit_combo_to_texts(combo, texts=[placeholder, *options], min_field_width=360)
        return combo

    def _generate_device_name(self) -> str:
        return generate_device_name()

    def _generate_mac_address(self) -> str:
        return generate_mac_address()

    def _create_mode_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setCheckable(True)
        button.setFixedHeight(32)
        button.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 0 16px;
            }
            QPushButton:checked {
                background: #6366f1;
                border-color: #6366f1;
                font-weight: bold;
            }
        """)
        return button

    def _create_round_action_button(self, text: str, background: str) -> QPushButton:
        button = QPushButton(text)
        button.setFixedSize(48, 48)
        button.setStyleSheet(f"""
            QPushButton {{
                background: {background};
                color: white;
                border: none;
                border-radius: 24px;
                font-size: 24px;
            }}
            QPushButton:hover {{
                background: rgba(99, 102, 241, 0.85);
            }}
            QPushButton:disabled {{
                background: rgba(255, 255, 255, 0.12);
                color: rgba(255, 255, 255, 0.45);
            }}
        """)
        return button

    def _create_link_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #7c3aed;
                border: none;
                padding: 0 4px;
                min-height: 24px;
            }
            QPushButton:hover {
                color: #a78bfa;
            }
            QPushButton:disabled {
                color: rgba(255, 255, 255, 0.35);
            }
        """)
        return button

    def _create_toggle_switch(self) -> QCheckBox:
        return ToggleSwitch()

    def _wrap_widget_with_suffix(self, field: QWidget, suffix: str) -> QWidget:
        suffix_label = QLabel(suffix)
        suffix_label.setStyleSheet("color: rgba(255, 255, 255, 0.35);")
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(field)
        layout.addWidget(suffix_label)
        layout.addStretch()
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _format_language_label(self, option: dict[str, object]) -> str:
        return f'{option["label"]}    {option["language"]}'

    def _find_combo_index(self, combo: QComboBox, predicate) -> int:
        for index in range(combo.count()):
            if predicate(combo.itemData(index)):
                return index
        return -1

    def _fit_combo_to_texts(
        self,
        combo: QComboBox,
        texts: list[str],
        *,
        min_field_width: int = 280,
        min_popup_width: int = 420,
        max_popup_width: int = 1200,
    ) -> None:
        normalized_texts = [text for text in texts if text]
        metrics = combo.fontMetrics()
        content_width = max(
            (metrics.horizontalAdvance(text) for text in normalized_texts),
            default=min_field_width,
        )
        field_width = max(min_field_width, min(content_width + 64, 760))
        popup_width = max(min_popup_width, min(content_width + 96, max_popup_width))
        combo.setMinimumWidth(field_width)
        view = combo.view()
        if view is not None:
            view.setMinimumWidth(popup_width)
            view.setTextElideMode(Qt.TextElideMode.ElideNone)

    def _refresh_webgl_renderer_options(self, preferred_renderer: str | None = None) -> None:
        vendor = self.webgl_vendor_combo.currentText().strip()
        current_renderer = preferred_renderer if preferred_renderer is not None else self.webgl_renderer_combo.currentText().strip()
        renderers = VIRTUALBROWSER_WEBGL_RENDERER_OPTIONS.get(vendor, ())

        self.webgl_renderer_combo.blockSignals(True)
        self.webgl_renderer_combo.clear()
        if renderers:
            self.webgl_renderer_combo.addItems(list(renderers))
        if current_renderer:
            self.webgl_renderer_combo.setCurrentText(current_renderer)
        elif renderers:
            self.webgl_renderer_combo.setCurrentIndex(0)
        self.webgl_renderer_combo.blockSignals(False)
        self._fit_combo_to_texts(
            self.webgl_renderer_combo,
            texts=[vendor, current_renderer, *renderers],
            min_field_width=420,
            min_popup_width=760,
        )

    def _set_default_language_selection(self) -> None:
        index = self._find_combo_index(
            self.language_combo,
            lambda data: isinstance(data, dict) and data.get("language") == "en-US",
        )
        if index >= 0:
            self.language_combo.setCurrentIndex(index)

    def _set_default_timezone_selection(self) -> None:
        index = self._find_combo_index(
            self.timezone_combo,
            lambda data: isinstance(data, dict) and data.get("utc") == "Asia/Hong_Kong",
        )
        if index >= 0:
            self.timezone_combo.setCurrentIndex(index)

    def _current_language_code(self) -> str:
        option = self.language_combo.currentData()
        if isinstance(option, dict):
            return str(option.get("language") or "en-US")
        return "en-US"

    def _set_default_screen_resolution(self) -> None:
        self._set_screen_resolution((1440, 900))

    def _set_screen_resolution(self, resolution: tuple[int, int]) -> None:
        width, height = resolution
        index = self._find_combo_index(
            self.screen_resolution_combo,
            lambda data: isinstance(data, tuple) and data == (width, height),
        )
        if index < 0:
            label = f"{width} x {height}"
            self.screen_resolution_combo.addItem(label, (width, height))
            index = self.screen_resolution_combo.count() - 1
        self.screen_resolution_combo.setCurrentIndex(index)

    def _current_screen_resolution(self) -> tuple[int, int]:
        resolution = self.screen_resolution_combo.currentData()
        if (
            isinstance(resolution, tuple)
            and len(resolution) == 2
            and all(isinstance(item, int) for item in resolution)
        ):
            return resolution
        return (1440, 900)

    def _current_browser_version(self) -> int:
        version = self.browser_version_combo.currentData()
        try:
            return int(version)
        except (TypeError, ValueError):
            return VIRTUALBROWSER_DEFAULT_CHROME_VERSION

    def _generate_default_user_agent(self, version: int | None = None) -> str:
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{version or self._current_browser_version()}.0.0.0 Safari/537.36"
        )

    def _generate_random_user_agent(self, version: int | None = None) -> str:
        return generate_random_user_agent(version or self._current_browser_version())

    def _set_ua_mode(self, mode: str) -> None:
        self._ua_mode = mode
        self.ua_default_btn.setChecked(mode == "default")
        self.ua_custom_btn.setChecked(mode == "custom")
        self.ua_value_edit.setReadOnly(mode == "default" or self._read_only)
        if mode == "default":
            self.ua_value_edit.setPlainText(self._generate_default_user_agent())

    def _refresh_ua_preview(self) -> None:
        if getattr(self, "_ua_mode", "default") == "default":
            self.ua_value_edit.setPlainText(self._generate_default_user_agent())

    def _on_browser_version_changed(self, _index: int) -> None:
        self._refresh_ua_preview()

    def _randomize_user_agent(self) -> None:
        self._set_ua_mode("custom")
        self.ua_value_edit.setPlainText(self._generate_random_user_agent())
        self.ua_value_edit.setFocus()

    def _refresh_randomized_identity_preview(self, *, force_regenerate: bool) -> None:
        if force_regenerate or getattr(self, "_ua_mode", "default") != "custom" or not self.ua_value_edit.toPlainText().strip():
            self._randomize_user_agent()

        self._set_combo_value(self.device_name_mode_combo, "custom")
        if force_regenerate or not self.device_name_edit.text().strip():
            self.device_name_edit.setText(self._generate_device_name())

        self._set_combo_value(self.mac_mode_combo, "custom")
        if force_regenerate or not self.mac_value_edit.text().strip():
            self.mac_value_edit.setText(self._generate_mac_address())

    def _apply_randomize_fingerprint_defaults(self, *, force_regenerate: bool) -> None:
        for control in (
            self.fonts_mode_combo,
            self.canvas_mode_combo,
            self.webgl_image_mode_combo,
            self.audio_context_mode_combo,
            self.client_rects_mode_combo,
            self.speech_voices_mode_combo,
        ):
            self._set_combo_value(control, "random")
        self._refresh_randomized_identity_preview(force_regenerate=force_regenerate)
        self._sync_virtualbrowser_field_visibility()

    def _on_randomize_fingerprint_toggled(self, checked: bool) -> None:
        if not checked:
            return
        self._apply_randomize_fingerprint_defaults(force_regenerate=True)

    def _apply_new_virtualbrowser_defaults(self) -> None:
        if not self._is_new:
            return
        if self.resource_mode_combo.currentData() != AcquisitionMode.CREATE:
            return
        if self.resource_provider_combo.currentText() != "virtualbrowser":
            return
        self.randomize_fingerprint_check.blockSignals(True)
        self.randomize_fingerprint_check.setChecked(True)
        self.randomize_fingerprint_check.blockSignals(False)
        self.cpu_value_spin.setValue(4)
        self.memory_value_spin.setValue(8)
        self.dnt_check.setChecked(False)
        self._set_combo_value(self.ssl_mode_combo, "disabled")
        self._set_combo_value(self.port_scan_protect_mode_combo, "disabled")
        self.hardware_accel_check.setChecked(True)
        self._set_combo_value(self.launch_args_mode_combo, "default")
        self._apply_randomize_fingerprint_defaults(force_regenerate=True)
        self._sync_virtualbrowser_field_visibility()

    def _set_sec_ch_ua_mode(self, mode: str, *, ensure_entries: bool = True) -> None:
        self._sec_ch_ua_mode = mode
        self.sec_ch_ua_default_btn.setChecked(mode == "default")
        self.sec_ch_ua_custom_btn.setChecked(mode == "custom")
        if mode == "custom" and ensure_entries and not getattr(self, "_sec_ch_ua_rows", []):
            self._ensure_default_sec_ch_ua_entries()
        self._sync_virtualbrowser_field_visibility()

    def _clear_sec_ch_ua_entries(self) -> None:
        for row_widget in getattr(self, "_sec_ch_ua_rows", []):
            self.sec_ch_ua_entries_layout.removeWidget(row_widget)
            row_widget.deleteLater()
        self._sec_ch_ua_rows = []

    def _ensure_default_sec_ch_ua_entries(self) -> None:
        if getattr(self, "_sec_ch_ua_rows", []):
            return
        for brand, version in (
            ("Chromium", str(self._current_browser_version())),
            ("Not=A?Brand", "99"),
        ):
            self._add_sec_ch_ua_entry(brand=brand, version=version)

    def _add_sec_ch_ua_entry(self, brand: str = "", version: str = "") -> None:
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(12)

        brand_label = QLabel("brand:")
        brand_edit = QLineEdit()
        brand_edit.setPlaceholderText("Chromium")
        brand_edit.setText(brand)

        version_label = QLabel("version:")
        version_edit = QLineEdit()
        version_edit.setPlaceholderText("145")
        version_edit.setMaximumWidth(120)
        version_edit.setText(version)

        remove_btn = self._create_round_action_button("−", "#ff4d4f")
        remove_btn.clicked.connect(lambda: self._remove_sec_ch_ua_entry(row_widget))

        row_layout.addWidget(brand_label)
        row_layout.addWidget(brand_edit, 1)
        row_layout.addWidget(version_label)
        row_layout.addWidget(version_edit)
        row_layout.addWidget(remove_btn)

        row_widget.brand_edit = brand_edit
        row_widget.version_edit = version_edit
        row_widget.remove_btn = remove_btn

        if not hasattr(self, "_sec_ch_ua_rows"):
            self._sec_ch_ua_rows = []
        self._sec_ch_ua_rows.append(row_widget)
        self.sec_ch_ua_entries_layout.addWidget(row_widget)

        if self._read_only:
            remove_btn.setEnabled(False)

    def _remove_sec_ch_ua_entry(self, row_widget: QWidget) -> None:
        if row_widget not in getattr(self, "_sec_ch_ua_rows", []):
            return
        self._sec_ch_ua_rows.remove(row_widget)
        self.sec_ch_ua_entries_layout.removeWidget(row_widget)
        row_widget.deleteLater()

    def _parse_sec_ch_ua_entries(self, raw_value: str) -> list[tuple[str, str]]:
        return [
            (match.group("brand"), match.group("version"))
            for match in SEC_CH_UA_VALUE_PATTERN.finditer(raw_value or "")
        ]

    def _build_sec_ch_ua_value(self) -> str:
        entries: list[str] = []
        for row_widget in getattr(self, "_sec_ch_ua_rows", []):
            brand = row_widget.brand_edit.text().strip()
            version = row_widget.version_edit.text().strip()
            if brand and version:
                entries.append(f'"{brand}";v="{version}"')
        return ", ".join(entries)

    def _set_language_selection(self, language_code: str, value: str) -> None:
        if not language_code and not value:
            self._set_default_language_selection()
            return
        index = self._find_combo_index(
            self.language_combo,
            lambda data: isinstance(data, dict)
            and data.get("language") == language_code
            and data.get("value") == value,
        )
        if index < 0 and language_code:
            index = self._find_combo_index(
                self.language_combo,
                lambda data: isinstance(data, dict) and data.get("language") == language_code,
            )
        if index < 0:
            option = {
                "label": "自定义语言",
                "language": language_code or value or "custom",
                "value": value or language_code,
            }
            self.language_combo.addItem(self._format_language_label(option), option)
            index = self.language_combo.count() - 1
        self.language_combo.setCurrentIndex(index)

    def _set_timezone_selection(self, timezone: dict) -> None:
        timezone_utc = str(timezone.get("utc", "") or "")
        timezone_zone = str(timezone.get("zone", "") or "")
        if not timezone_utc and not timezone_zone:
            self._set_default_timezone_selection()
            return
        index = self._find_combo_index(
            self.timezone_combo,
            lambda data: isinstance(data, dict)
            and (
                data.get("utc") == timezone_utc
                or data.get("zone") == timezone_zone
            ),
        )
        if index >= 0:
            option = dict(self.timezone_combo.itemData(index) or {})
            if timezone.get("locale"):
                option["locale"] = timezone.get("locale")
            if timezone.get("value") not in (None, ""):
                option["value"] = timezone.get("value")
            if timezone_zone:
                option["zone"] = timezone_zone
            self.timezone_combo.setItemData(index, option)
            self.timezone_combo.setCurrentIndex(index)
            return

        option = {
            "label": timezone_zone or timezone_utc,
            "zone": timezone_zone or timezone_utc,
            "utc": timezone_utc or timezone_zone,
            "locale": str(timezone.get("locale", "") or ""),
            "value": timezone.get("value", 0),
        }
        self.timezone_combo.addItem(str(option["label"]), option)
        self.timezone_combo.setCurrentIndex(self.timezone_combo.count() - 1)

    def _setup_virtualbrowser_form(self, parent):
        form = self._create_form_layout(parent)

        ua_mode_widget = QWidget()
        ua_mode_layout = QHBoxLayout(ua_mode_widget)
        ua_mode_layout.setContentsMargins(0, 0, 0, 0)
        ua_mode_layout.setSpacing(8)
        self.ua_default_btn = self._create_mode_button("默认")
        self.ua_custom_btn = self._create_mode_button("自定义")
        self.ua_default_btn.clicked.connect(lambda: self._set_ua_mode("default"))
        self.ua_custom_btn.clicked.connect(lambda: self._set_ua_mode("custom"))
        ua_mode_layout.addWidget(self.ua_default_btn)
        ua_mode_layout.addWidget(self.ua_custom_btn)
        ua_mode_layout.addStretch()
        form.addRow("User Agent:", ua_mode_widget)

        ua_value_widget = QWidget()
        ua_value_widget.setMinimumHeight(156)
        ua_value_widget.setFixedHeight(156)
        ua_value_layout = QHBoxLayout(ua_value_widget)
        ua_value_layout.setContentsMargins(0, 0, 0, 0)
        ua_value_layout.setSpacing(8)
        self.ua_value_edit = QPlainTextEdit()
        self.ua_value_edit.setPlaceholderText("Mozilla/5.0 ...")
        self.ua_value_edit.setMinimumHeight(156)
        self.ua_value_edit.setFixedHeight(156)
        self.ua_random_btn = QPushButton("随机")
        self.ua_random_btn.setFixedSize(80, 36)
        self.ua_random_btn.setStyleSheet("""
            QPushButton {
                background: #6366f1;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        self.ua_random_btn.clicked.connect(self._randomize_user_agent)
        ua_value_layout.addWidget(self.ua_value_edit, 1)
        ua_value_layout.addWidget(self.ua_random_btn)
        form.addRow("UA 值:", ua_value_widget)

        sec_ch_mode_widget = QWidget()
        sec_ch_mode_layout = QHBoxLayout(sec_ch_mode_widget)
        sec_ch_mode_layout.setContentsMargins(0, 0, 0, 0)
        sec_ch_mode_layout.setSpacing(8)
        self.sec_ch_ua_default_btn = self._create_mode_button("默认")
        self.sec_ch_ua_custom_btn = self._create_mode_button("自定义")
        self.sec_ch_ua_default_btn.clicked.connect(lambda: self._set_sec_ch_ua_mode("default"))
        self.sec_ch_ua_custom_btn.clicked.connect(lambda: self._set_sec_ch_ua_mode("custom"))
        sec_ch_mode_layout.addWidget(self.sec_ch_ua_default_btn)
        sec_ch_mode_layout.addWidget(self.sec_ch_ua_custom_btn)
        sec_ch_mode_layout.addStretch()
        form.addRow("Sec-CH-UA:", sec_ch_mode_widget)

        self.sec_ch_ua_editor_widget = QWidget()
        sec_ch_editor_layout = QVBoxLayout(self.sec_ch_ua_editor_widget)
        sec_ch_editor_layout.setContentsMargins(0, 0, 0, 0)
        sec_ch_editor_layout.setSpacing(12)

        self.sec_ch_ua_entries_container = QWidget()
        self.sec_ch_ua_entries_layout = QVBoxLayout(self.sec_ch_ua_entries_container)
        self.sec_ch_ua_entries_layout.setContentsMargins(0, 0, 0, 0)
        self.sec_ch_ua_entries_layout.setSpacing(12)
        self._sec_ch_ua_rows: list[QWidget] = []
        sec_ch_editor_layout.addWidget(self.sec_ch_ua_entries_container)

        sec_ch_action_layout = QHBoxLayout()
        sec_ch_action_layout.setContentsMargins(0, 0, 0, 0)
        sec_ch_action_layout.addStretch()
        self.sec_ch_ua_add_btn = self._create_round_action_button("+", "#2f2f35")
        self.sec_ch_ua_add_btn.clicked.connect(self._add_sec_ch_ua_entry)
        sec_ch_action_layout.addWidget(self.sec_ch_ua_add_btn)
        sec_ch_editor_layout.addLayout(sec_ch_action_layout)
        form.addRow("", self.sec_ch_ua_editor_widget)

        self.language_follow_ip_check = QCheckBox("语言跟随 IP")
        self.language_follow_ip_check.setStyleSheet("color: white;")
        self.language_follow_ip_check.setChecked(True)
        self.language_follow_ip_check.stateChanged.connect(self._sync_virtualbrowser_field_visibility)
        form.addRow("", self.language_follow_ip_check)
        self.language_combo = QComboBox()
        for option in VIRTUALBROWSER_LANGUAGE_OPTIONS:
            self.language_combo.addItem(self._format_language_label(option), dict(option))
        self.language_combo.setMaxVisibleItems(12)
        form.addRow("语言:", self.language_combo)

        self.timezone_follow_ip_check = QCheckBox("时区跟随 IP")
        self.timezone_follow_ip_check.setStyleSheet("color: white;")
        self.timezone_follow_ip_check.setChecked(True)
        self.timezone_follow_ip_check.stateChanged.connect(self._sync_virtualbrowser_field_visibility)
        form.addRow("", self.timezone_follow_ip_check)
        self.timezone_combo = QComboBox()
        for option in VIRTUALBROWSER_TIMEZONE_OPTIONS:
            self.timezone_combo.addItem(str(option["label"]), dict(option))
        self.timezone_combo.setMaxVisibleItems(18)
        form.addRow("时区:", self.timezone_combo)

        self.webrtc_mode_combo = self._add_segmented_row(
            form,
            "WebRTC:",
            [("替换", 0), ("允许", 1), ("禁止", 2)],
        )

        self.location_permission_combo = self._add_segmented_row(
            form,
            "地理位置权限:",
            [("询问", 0), ("允许", 1), ("禁止", 2)],
        )
        self.location_follow_ip_check = QCheckBox("地理位置跟随 IP")
        self.location_follow_ip_check.setStyleSheet("color: white;")
        self.location_follow_ip_check.setChecked(True)
        self.location_follow_ip_check.stateChanged.connect(self._sync_virtualbrowser_field_visibility)
        form.addRow("", self.location_follow_ip_check)
        self.location_longitude_edit = QLineEdit()
        self.location_longitude_edit.setPlaceholderText("例如 121.4737")
        form.addRow("经度:", self.location_longitude_edit)
        self.location_latitude_edit = QLineEdit()
        self.location_latitude_edit.setPlaceholderText("例如 31.2304")
        form.addRow("纬度:", self.location_latitude_edit)
        self.location_precision_spin = QSpinBox()
        self.location_precision_spin.setRange(0, 1000)
        self.location_precision_spin.setValue(10)
        form.addRow("偏移量:", self.location_precision_spin)

        self.screen_mode_combo = self._add_segmented_row(
            form,
            "分辨率:",
            [("跟随电脑", "default"), ("自定义", "custom")],
            on_change=self._sync_virtualbrowser_field_visibility,
        )
        self.screen_resolution_combo = QComboBox()
        for label, resolution in VIRTUALBROWSER_SCREEN_RESOLUTIONS:
            self.screen_resolution_combo.addItem(label, resolution)
        self.screen_resolution_combo.setMaxVisibleItems(10)
        form.addRow("分辨率值:", self.screen_resolution_combo)

        self.fonts_mode_combo = self._add_segmented_row(
            form,
            "字体:",
            [("系统默认", "default"), ("随机匹配", "random")],
        )
        self.canvas_mode_combo = self._add_segmented_row(
            form,
            "Canvas:",
            [("默认", "default"), ("随机", "random")],
        )
        self.webgl_image_mode_combo = self._add_segmented_row(
            form,
            "WebGL 图像:",
            [("默认", "default"), ("随机", "random")],
        )

        self.webgl_mode_combo = self._add_segmented_row(
            form,
            "WebGL 元数据:",
            [("默认", "default"), ("自定义", "custom")],
            on_change=self._sync_virtualbrowser_field_visibility,
        )
        self.webgl_vendor_combo = self._create_editable_combo(
            "例如 Google Inc. (Intel Inc.)",
            tuple(VIRTUALBROWSER_WEBGL_RENDERER_OPTIONS.keys()),
        )
        self.webgl_vendor_combo.currentTextChanged.connect(self._refresh_webgl_renderer_options)
        form.addRow("WebGL 厂商:", self.webgl_vendor_combo)
        self.webgl_renderer_combo = self._create_editable_combo("例如 ANGLE (...)", ())
        form.addRow("WebGL 渲染:", self.webgl_renderer_combo)
        self._refresh_webgl_renderer_options()

        self.webgpu_mode_combo = self._add_segmented_row(
            form,
            "WebGPU:",
            [("默认", "default"), ("基于WebGL", "based_on_webgl")],
        )
        self.audio_context_mode_combo = self._add_segmented_row(
            form,
            "AudioContext:",
            [("默认", "default"), ("随机", "random")],
        )
        self.client_rects_mode_combo = self._add_segmented_row(
            form,
            "ClientRects:",
            [("默认", "default"), ("随机", "random")],
        )
        self.speech_voices_mode_combo = self._add_segmented_row(
            form,
            "Speech Voices:",
            [("默认", "default"), ("随机", "random")],
        )

        self.cpu_value_spin = QSpinBox()
        self.cpu_value_spin.setRange(1, 64)
        self.cpu_value_spin.setValue(4)
        self.cpu_value_spin.setMaximumWidth(88)
        form.addRow("CPU:", self._wrap_widget_with_suffix(self.cpu_value_spin, "核"))
        self.memory_value_spin = QSpinBox()
        self.memory_value_spin.setRange(1, 256)
        self.memory_value_spin.setValue(8)
        self.memory_value_spin.setMaximumWidth(88)
        form.addRow("内存:", self._wrap_widget_with_suffix(self.memory_value_spin, "GB"))

        self.device_name_mode_combo = SegmentedOptionControl(
            [("默认", "default"), ("自定义", "custom")],
            on_change=self._sync_virtualbrowser_field_visibility,
        )
        device_input_row = QHBoxLayout()
        device_input_row.setContentsMargins(0, 0, 0, 0)
        device_input_row.setSpacing(8)
        self.device_name_edit = QLineEdit()
        self.device_name_edit.setPlaceholderText("例如 T8VQ1N4M7K9A3F2C1")
        self.device_name_regen_btn = self._create_link_button("换一换")
        self.device_name_regen_btn.clicked.connect(
            lambda: self.device_name_edit.setText(self._generate_device_name())
        )
        device_input_row.addWidget(self.device_name_edit)
        device_input_row.addWidget(self.device_name_regen_btn)
        self.device_name_input_widget = QWidget()
        self.device_name_input_widget.setLayout(device_input_row)
        device_row = QHBoxLayout()
        device_row.setContentsMargins(0, 0, 0, 0)
        device_row.setSpacing(12)
        device_row.addWidget(self.device_name_mode_combo)
        device_row.addWidget(self.device_name_input_widget, 1)
        self.device_name_row_widget = QWidget()
        self.device_name_row_widget.setLayout(device_row)
        form.addRow("设备名称:", self.device_name_row_widget)

        self.mac_mode_combo = SegmentedOptionControl(
            [("默认", "default"), ("自定义", "custom")],
            on_change=self._sync_virtualbrowser_field_visibility,
        )
        mac_input_row = QHBoxLayout()
        mac_input_row.setContentsMargins(0, 0, 0, 0)
        mac_input_row.setSpacing(8)
        self.mac_value_edit = QLineEdit()
        self.mac_value_edit.setPlaceholderText("例如 02-76-66-51-39-C9")
        self.mac_regen_btn = self._create_link_button("换一换")
        self.mac_regen_btn.clicked.connect(
            lambda: self.mac_value_edit.setText(self._generate_mac_address())
        )
        mac_input_row.addWidget(self.mac_value_edit)
        mac_input_row.addWidget(self.mac_regen_btn)
        self.mac_input_widget = QWidget()
        self.mac_input_widget.setLayout(mac_input_row)
        mac_row = QHBoxLayout()
        mac_row.setContentsMargins(0, 0, 0, 0)
        mac_row.setSpacing(12)
        mac_row.addWidget(self.mac_mode_combo)
        mac_row.addWidget(self.mac_input_widget, 1)
        self.mac_row_widget = QWidget()
        self.mac_row_widget.setLayout(mac_row)
        form.addRow("MAC地址:", self.mac_row_widget)

        self.dnt_check = self._create_toggle_switch()
        form.addRow("Do Not Track", self.dnt_check)

        self.ssl_mode_combo = self._add_segmented_row(
            form,
            "SSL:",
            [("开启", "enabled"), ("关闭", "disabled")],
        )
        self._set_combo_value(self.ssl_mode_combo, "disabled")

        self.port_scan_protect_mode_combo = self._add_segmented_row(
            form,
            "端口扫描保护:",
            [("开启", "enabled"), ("关闭", "disabled")],
            on_change=self._sync_virtualbrowser_field_visibility,
        )
        self._set_combo_value(self.port_scan_protect_mode_combo, "disabled")
        self.port_scan_whitelist_edit = QLineEdit()
        self.port_scan_whitelist_edit.setPlaceholderText("输入端口，多个用英文逗号分隔")
        form.addRow("扫描白名单:", self.port_scan_whitelist_edit)

        self.hardware_accel_check = self._create_toggle_switch()
        self.hardware_accel_check.setChecked(True)
        form.addRow("硬件加速", self.hardware_accel_check)

        self.launch_args_mode_combo = self._add_segmented_row(
            form,
            "启动参数:",
            [("默认", "default"), ("自定义", "custom")],
            on_change=self._sync_virtualbrowser_field_visibility,
        )
        self.launch_args_edit = QPlainTextEdit()
        self.launch_args_edit.setPlaceholderText("--no-sandbox\n--start-maximized")
        self.launch_args_edit.setMinimumHeight(70)
        form.addRow("启动参数值:", self.launch_args_edit)

        self._set_ua_mode("default")
        self._set_default_language_selection()
        self._set_default_timezone_selection()
        self._set_default_screen_resolution()
        self._set_sec_ch_ua_mode("default")
        self._sync_virtualbrowser_field_visibility()

    def _setup_basic_tab(self, parent):
        main_layout = QVBoxLayout(parent)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        basic_group = QGroupBox("基础信息")
        form = self._create_form_layout(basic_group)

        self.script_selector = WorkflowSelector(show_module=True)
        self.script_selector.workflow_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        form.addRow("执行脚本:", self.script_selector)

        layout.addWidget(basic_group)

        sel_group = QGroupBox("资源定义")
        self.resource_form = self._create_form_layout(sel_group)

        self.resource_mode_combo = QComboBox()
        self.resource_mode_combo.addItem("创建环境", AcquisitionMode.CREATE)
        self.resource_mode_combo.addItem("选择环境", AcquisitionMode.SELECT)
        self.resource_mode_combo.currentIndexChanged.connect(self._on_resource_mode_changed)
        self.resource_form.addRow("运行方式:", self.resource_mode_combo)

        self.resource_provider_combo = QComboBox()
        self.resource_provider_combo.currentIndexChanged.connect(self._sync_create_fields)
        self.resource_form.addRow("Provider:", self.resource_provider_combo)

        self.create_env_type_combo = QComboBox()
        self.create_env_type_combo.addItem("标准浏览器", EnvType.CHROME)
        self.create_env_type_combo.addItem("指纹浏览器", EnvType.VIRTUAL_BROWSER)
        self.create_env_type_combo.currentIndexChanged.connect(self._on_create_env_type_changed)
        self.resource_form.addRow("环境类型:", self.create_env_type_combo)

        self.wait_timeout_spin = QSpinBox()
        self.wait_timeout_spin.setRange(0, 3600)
        self.wait_timeout_spin.setValue(60)

        self.resource_mode_stack = QStackedWidget()

        create_widget = QWidget()
        create_layout = QVBoxLayout(create_widget)
        create_layout.setContentsMargins(0, 0, 0, 0)
        create_layout.setSpacing(12)

        create_form_widget = QWidget()
        self.create_form = self._create_form_layout(create_form_widget)

        self.browser_version_combo = QComboBox()
        for version in VIRTUALBROWSER_SUPPORTED_CHROME_VERSIONS:
            self.browser_version_combo.addItem(str(version), version)
        default_version_index = self.browser_version_combo.findData(VIRTUALBROWSER_DEFAULT_CHROME_VERSION)
        if default_version_index >= 0:
            self.browser_version_combo.setCurrentIndex(default_version_index)
        self.browser_version_combo.currentIndexChanged.connect(self._on_browser_version_changed)
        self.create_form.addRow("浏览器版本:", self.browser_version_combo)

        self.kernel_version_combo = QComboBox()
        self.kernel_version_combo.addItem("自动匹配", "auto")
        self.kernel_version_combo.setEnabled(False)
        self.create_form.addRow("内核版本:", self.kernel_version_combo)

        self.randomize_fingerprint_check = QCheckBox("随机化指纹")
        self.randomize_fingerprint_check.setStyleSheet("color: white;")
        self.randomize_fingerprint_check.toggled.connect(self._on_randomize_fingerprint_toggled)
        self.create_form.addRow("", self.randomize_fingerprint_check)

        self.ip_binding_combo = QComboBox()
        self.ip_binding_combo.addItem("不绑定 IP", "none")
        self.ip_binding_combo.addItem("使用系统代理", "system")
        self.ip_binding_combo.addItem("从 IP 池绑定", "pool")
        self.ip_binding_combo.addItem("手动代理地址", "static")
        self.ip_binding_combo.currentIndexChanged.connect(self._on_ip_binding_changed)
        self.create_form.addRow("IP 策略:", self.ip_binding_combo)

        self.ip_pool_combo = QComboBox()
        self.create_form.addRow("IP 池:", self.ip_pool_combo)

        self.ip_pool_strategy_combo = QComboBox()
        self.ip_pool_strategy_combo.addItem("最少绑定数", "least_bound")
        self.ip_pool_strategy_combo.addItem("最高安全度", "highest_safety")
        self.ip_pool_strategy_combo.addItem("最长有效期", "longest_ttl")
        self.create_form.addRow("绑定策略:", self.ip_pool_strategy_combo)

        self.manual_proxy_edit = QLineEdit()
        self.manual_proxy_edit.setPlaceholderText("socks5://user:pass@host:port")
        self.create_form.addRow("代理地址:", self.manual_proxy_edit)

        create_layout.addWidget(create_form_widget)

        self.virtualbrowser_group = QGroupBox("指纹参数")
        self._setup_virtualbrowser_form(self.virtualbrowser_group)
        create_layout.addWidget(self.virtualbrowser_group)
        create_layout.addStretch()

        self.resource_mode_stack.addWidget(create_widget)

        select_widget = QWidget()
        select_layout = QVBoxLayout(select_widget)
        select_layout.setContentsMargins(0, 0, 0, 0)
        select_layout.setSpacing(12)

        select_form_widget = QWidget()
        self.select_form = self._create_form_layout(select_form_widget)

        self.selector_name_combo = QComboBox()
        self.selector_name_combo.setPlaceholderText("选择环境回调函数")
        self.selector_name_combo.currentIndexChanged.connect(self._on_selector_name_changed)
        self.select_form.addRow("回调函数:", self.selector_name_combo)
        self.resource_pool_edit = QLineEdit()
        self.resource_pool_edit.setPlaceholderText("例如：bound_account_ready")
        self.select_form.addRow("资源池:", self.resource_pool_edit)
        self.select_form.addRow(
            "等待超时:",
            self._wrap_widget_with_suffix(self.wait_timeout_spin, "秒"),
        )
        select_layout.addWidget(select_form_widget)

        self.selector_none_hint = QLabel("当前环境选择回调函数返回了 none。普通选择模式会直接失败；固定资源池 Service Job 会继续等待。")
        self.selector_none_hint.setWordWrap(True)
        self.selector_none_hint.setStyleSheet("color: #f59e0b;")
        self.selector_none_hint.hide()
        select_layout.addWidget(self.selector_none_hint)

        self.selector_empty_hint = QLabel("当前模块未声明可用的环境选择回调函数。")
        self.selector_empty_hint.setWordWrap(True)
        self.selector_empty_hint.setStyleSheet("color: rgba(255, 255, 255, 0.6);")
        self.selector_empty_hint.hide()
        select_layout.addWidget(self.selector_empty_hint)

        select_desc = QLabel("可选先按资源池做宿主级粗筛，再把当前池内候选交给模块回调做细粒度选择。")
        select_desc.setWordWrap(True)
        select_desc.setStyleSheet("color: rgba(255, 255, 255, 0.72);")
        select_layout.addWidget(select_desc)
        select_layout.addStretch()

        self.resource_mode_stack.addWidget(select_widget)
        self.resource_form.addRow("模式配置:", self.resource_mode_stack)

        layout.addWidget(sel_group)
        layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        self._load_ip_pools()
        self._load_provider_options("virtualbrowser")
        self.script_selector.module_combo.currentTextChanged.connect(self._on_script_module_changed)
        self._selector_infos: dict[str, object] = {}
        self._load_selector_options()
        self._on_resource_mode_changed(self.resource_mode_combo.currentIndex())

    def _set_row_visible(self, widget: QWidget, visible: bool):
        parent = widget.parentWidget()
        if parent is None:
            widget.setVisible(visible)
            return

        layout = parent.layout()
        if isinstance(layout, QFormLayout):
            label = layout.labelForField(widget)
            if label:
                label.setVisible(visible)
        widget.setVisible(visible)

    def _set_combo_value(self, combo, value) -> None:
        if isinstance(combo, SegmentedOptionControl):
            combo.set_current_data(value)
            return
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _sync_virtualbrowser_field_visibility(self, *_args):
        self._set_row_visible(
            self.sec_ch_ua_editor_widget,
            getattr(self, "_sec_ch_ua_mode", "default") == "custom",
        )

        language_custom = not self.language_follow_ip_check.isChecked()
        self._set_row_visible(self.language_combo, language_custom)

        timezone_custom = not self.timezone_follow_ip_check.isChecked()
        self._set_row_visible(self.timezone_combo, timezone_custom)

        location_custom = not self.location_follow_ip_check.isChecked()
        self._set_row_visible(self.location_longitude_edit, location_custom)
        self._set_row_visible(self.location_latitude_edit, location_custom)
        self._set_row_visible(self.location_precision_spin, location_custom)

        screen_custom = self.screen_mode_combo.currentData() == "custom"
        self._set_row_visible(self.screen_resolution_combo, screen_custom)

        webgl_custom = self.webgl_mode_combo.currentData() == "custom"
        self._set_row_visible(self.webgl_vendor_combo, webgl_custom)
        self._set_row_visible(self.webgl_renderer_combo, webgl_custom)

        device_custom = self.device_name_mode_combo.currentData() == "custom"
        self.device_name_input_widget.setVisible(device_custom)

        mac_custom = self.mac_mode_combo.currentData() == "custom"
        self.mac_input_widget.setVisible(mac_custom)

        self._set_row_visible(
            self.port_scan_whitelist_edit,
            self.port_scan_protect_mode_combo.currentData() == "enabled",
        )
        self._set_row_visible(
            self.launch_args_edit,
            self.launch_args_mode_combo.currentData() == "custom",
        )

    def _build_virtualbrowser_params(self) -> dict:
        randomize_fingerprint = self.randomize_fingerprint_check.isChecked()
        params: dict[str, object] = {
            "chrome_version": self._current_browser_version(),
        }

        if not randomize_fingerprint and getattr(self, "_ua_mode", "default") == "custom":
            ua_value = self.ua_value_edit.toPlainText().strip()
            if ua_value:
                params["ua"] = {"mode": 1, "value": ua_value}

        if getattr(self, "_sec_ch_ua_mode", "default") == "custom":
            sec_ch_value = self._build_sec_ch_ua_value()
            if sec_ch_value:
                params["sec-ch-ua"] = {"mode": 1, "value": sec_ch_value}

        if not self.language_follow_ip_check.isChecked():
            language_option = self.language_combo.currentData()
            if not isinstance(language_option, dict):
                language_option = {}
            params["ua-language"] = {
                "mode": 1,
                "language": str(language_option.get("language", "")).strip(),
                "value": str(language_option.get("value", "")).strip(),
            }

        if not self.timezone_follow_ip_check.isChecked():
            timezone_option = self.timezone_combo.currentData()
            if not isinstance(timezone_option, dict):
                timezone_option = {}
            params["time-zone"] = {
                "mode": 1,
                "zone": str(timezone_option.get("zone", "")).strip(),
                "utc": str(timezone_option.get("utc", "")).strip(),
                "locale": str(timezone_option.get("locale") or self._current_language_code()).strip(),
                "value": timezone_option.get("value", 0),
            }

        if self.webrtc_mode_combo.currentData() != 0:
            params["webrtc"] = {"mode": self.webrtc_mode_combo.currentData()}

        location_permission = self.location_permission_combo.currentData()
        if not self.location_follow_ip_check.isChecked():
            params["location"] = {
                "mode": 1,
                "enable": location_permission,
                "longitude": self.location_longitude_edit.text().strip(),
                "latitude": self.location_latitude_edit.text().strip(),
                "precision": self.location_precision_spin.value(),
            }
        elif location_permission != 1:
            params["location"] = {"mode": 2, "enable": location_permission}

        if self.screen_mode_combo.currentData() == "custom":
            width, height = self._current_screen_resolution()
            params["screen"] = {
                "mode": 1,
                "width": width,
                "height": height,
                "_value": f"{width} x {height}",
            }

        if self.fonts_mode_combo.currentData() == "random":
            params["fonts"] = {"mode": 1}
        if self.canvas_mode_combo.currentData() == "random":
            params["canvas"] = {"mode": 1}
        if self.webgl_image_mode_combo.currentData() == "random":
            params["webgl-img"] = {"mode": 1}

        if self.webgl_mode_combo.currentData() == "custom":
            vendor = self.webgl_vendor_combo.currentText().strip()
            renderer = self.webgl_renderer_combo.currentText().strip()
            if vendor or renderer:
                params["webgl"] = {
                    "mode": 1,
                    "vendor": vendor,
                    "render": renderer,
                }

        if self.webgpu_mode_combo.currentData() == "based_on_webgl":
            params["media"] = {"mode": 1}

        if self.audio_context_mode_combo.currentData() == "random":
            params["audio-context"] = {"mode": 1}
        if self.client_rects_mode_combo.currentData() == "random":
            params["client-rects"] = {"mode": 1}
        if self.speech_voices_mode_combo.currentData() == "random":
            params["speech_voices"] = {"mode": 1}

        if self.cpu_value_spin.value() != 4:
            params["cpu"] = {"mode": 1, "value": self.cpu_value_spin.value()}
        if self.memory_value_spin.value() != 64:
            params["memory"] = {"mode": 1, "value": self.memory_value_spin.value()}

        if not randomize_fingerprint and self.device_name_mode_combo.currentData() == "custom":
            device_name = self.device_name_edit.text().strip()
            if device_name:
                params["device-name"] = {"mode": 1, "value": device_name}

        if not randomize_fingerprint and self.mac_mode_combo.currentData() == "custom":
            mac_value = self.mac_value_edit.text().strip()
            if mac_value:
                params["mac"] = {"mode": 1, "value": mac_value}

        if self.dnt_check.isChecked():
            params["dnt"] = {"mode": 1, "value": 1}

        if self.ssl_mode_combo.currentData() == "enabled":
            params["ssl"] = {"mode": 1}

        if self.port_scan_protect_mode_combo.currentData() == "enabled":
            whitelist = [
                item.strip()
                for item in self.port_scan_whitelist_edit.text().split(",")
                if item.strip()
            ]
            params["port-scan"] = {"mode": 1, "value": whitelist}

        if not self.hardware_accel_check.isChecked():
            params["gpu"] = {"mode": 1, "value": 0}

        if self.launch_args_mode_combo.currentData() == "custom":
            launch_args = self.launch_args_edit.toPlainText().strip()
            if launch_args:
                params["launchArgs"] = {"mode": 1, "value": launch_args}

        if randomize_fingerprint:
            params[VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY] = True

        return params

    def _load_virtualbrowser_params(self, params: dict) -> None:
        params = dict(params or {})
        randomize_fingerprint = bool(params.pop(VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY, False))
        self.randomize_fingerprint_check.blockSignals(True)
        self.randomize_fingerprint_check.setChecked(randomize_fingerprint)
        self.randomize_fingerprint_check.blockSignals(False)

        chrome_version = params.get("chrome_version", VIRTUALBROWSER_DEFAULT_CHROME_VERSION)
        try:
            chrome_version = int(chrome_version)
        except (TypeError, ValueError):
            chrome_version = VIRTUALBROWSER_DEFAULT_CHROME_VERSION
        self._set_combo_value(self.browser_version_combo, chrome_version)

        ua = params.get("ua") if isinstance(params.get("ua"), dict) else {}
        self.ua_value_edit.setPlainText(str(ua.get("value", "")))
        self._set_ua_mode("custom" if ua else "default")

        sec_ch = params.get("sec-ch-ua") if isinstance(params.get("sec-ch-ua"), dict) else {}
        self._clear_sec_ch_ua_entries()
        if sec_ch:
            self._set_sec_ch_ua_mode("custom", ensure_entries=False)
            entries = self._parse_sec_ch_ua_entries(str(sec_ch.get("value", "")))
            if entries:
                for brand, version in entries:
                    self._add_sec_ch_ua_entry(brand=brand, version=version)
            else:
                self._add_sec_ch_ua_entry()
        else:
            self._set_sec_ch_ua_mode("default", ensure_entries=False)

        language = params.get("ua-language") if isinstance(params.get("ua-language"), dict) else {}
        self.language_follow_ip_check.setChecked(not language or language.get("mode", 2) == 2)
        self._set_language_selection(
            str(language.get("language", "")),
            str(language.get("value", "")),
        )

        timezone = params.get("time-zone") if isinstance(params.get("time-zone"), dict) else {}
        self.timezone_follow_ip_check.setChecked(not timezone or timezone.get("mode", 2) == 2)
        self._set_timezone_selection(timezone)

        webrtc = params.get("webrtc")
        if isinstance(webrtc, dict):
            self._set_combo_value(self.webrtc_mode_combo, webrtc.get("mode", 0))
        else:
            self._set_combo_value(self.webrtc_mode_combo, 0)

        location = params.get("location") if isinstance(params.get("location"), dict) else {}
        self._set_combo_value(self.location_permission_combo, location.get("enable", 1))
        self.location_follow_ip_check.setChecked(not location or location.get("mode", 2) == 2)
        self.location_longitude_edit.setText(str(location.get("longitude", "")))
        self.location_latitude_edit.setText(str(location.get("latitude", "")))
        self.location_precision_spin.setValue(int(location.get("precision", 10) or 10))

        screen = params.get("screen") if isinstance(params.get("screen"), dict) else {}
        self._set_combo_value(
            self.screen_mode_combo,
            "custom" if screen.get("mode") == 1 else "default",
        )
        self._set_screen_resolution(
            (
                int(screen.get("width", 1440) or 1440),
                int(screen.get("height", 900) or 900),
            )
        )

        self._set_combo_value(
            self.fonts_mode_combo,
            "random" if isinstance(params.get("fonts"), dict) and params["fonts"].get("mode") == 1 else "default",
        )
        self._set_combo_value(
            self.canvas_mode_combo,
            "random" if isinstance(params.get("canvas"), dict) and params["canvas"].get("mode") == 1 else "default",
        )
        self._set_combo_value(
            self.webgl_image_mode_combo,
            "random" if isinstance(params.get("webgl-img"), dict) and params["webgl-img"].get("mode") == 1 else "default",
        )

        webgl = params.get("webgl") if isinstance(params.get("webgl"), dict) else {}
        if webgl.get("vendor") or webgl.get("render"):
            self._set_combo_value(self.webgl_mode_combo, "custom")
        else:
            self._set_combo_value(self.webgl_mode_combo, "default")
        self.webgl_vendor_combo.setCurrentText(str(webgl.get("vendor", "")))
        self._refresh_webgl_renderer_options(str(webgl.get("render", "")))
        media = params.get("media") if isinstance(params.get("media"), dict) else {}
        if not media and isinstance(params.get("webgpu"), dict):
            media = params.get("webgpu")
        self._set_combo_value(
            self.webgpu_mode_combo,
            "based_on_webgl" if media.get("mode") == 1 else "default",
        )

        self._set_combo_value(
            self.audio_context_mode_combo,
            "random" if isinstance(params.get("audio-context"), dict) and params["audio-context"].get("mode") == 1 else "default",
        )
        self._set_combo_value(
            self.client_rects_mode_combo,
            "random" if isinstance(params.get("client-rects"), dict) and params["client-rects"].get("mode") == 1 else "default",
        )
        self._set_combo_value(
            self.speech_voices_mode_combo,
            "random" if isinstance(params.get("speech_voices"), dict) and params["speech_voices"].get("mode") == 1 else "default",
        )

        cpu = params.get("cpu") if isinstance(params.get("cpu"), dict) else {}
        memory = params.get("memory") if isinstance(params.get("memory"), dict) else {}
        self.cpu_value_spin.setValue(int(cpu.get("value", 4) or 4))
        self.memory_value_spin.setValue(int(memory.get("value", 64) or 64))

        device_name = params.get("device-name") if isinstance(params.get("device-name"), dict) else {}
        self._set_combo_value(
            self.device_name_mode_combo,
            "custom" if device_name else "default",
        )
        self.device_name_edit.setText(str(device_name.get("value", "")))

        mac_value = params.get("mac") if isinstance(params.get("mac"), dict) else {}
        self._set_combo_value(self.mac_mode_combo, "custom" if mac_value else "default")
        self.mac_value_edit.setText(str(mac_value.get("value", "")))

        dnt = params.get("dnt") if isinstance(params.get("dnt"), dict) else {}
        self.dnt_check.setChecked(bool(dnt.get("value", 0)))

        ssl = params.get("ssl") if isinstance(params.get("ssl"), dict) else {}
        self._set_combo_value(self.ssl_mode_combo, "enabled" if ssl.get("mode", 0) else "disabled")

        port_scan = params.get("port-scan") if isinstance(params.get("port-scan"), dict) else {}
        self._set_combo_value(
            self.port_scan_protect_mode_combo,
            "enabled" if port_scan.get("mode", 0) else "disabled",
        )
        self.port_scan_whitelist_edit.setText(
            ",".join(str(item) for item in (port_scan.get("value") or []))
        )

        gpu = params.get("gpu") if isinstance(params.get("gpu"), dict) else {}
        self.hardware_accel_check.setChecked(gpu.get("value", 1) != 0)

        launch_args = params.get("launchArgs") if isinstance(params.get("launchArgs"), dict) else {}
        self._set_combo_value(
            self.launch_args_mode_combo,
            "custom" if launch_args else "default",
        )
        self.launch_args_edit.setPlainText(str(launch_args.get("value", "")))

        if randomize_fingerprint:
            self._refresh_randomized_identity_preview(force_regenerate=False)
        self._sync_virtualbrowser_field_visibility()

    def _load_provider_options(self, preferred: str | None = None):
        current = preferred or self.resource_provider_combo.currentText() or "virtualbrowser"
        create_env_type = self.create_env_type_combo.currentData()

        options: list[str]
        if create_env_type == EnvType.CHROME:
            options = ["playwright_local"]
        else:
            options = ["virtualbrowser", "bitbrowser"]

        self.resource_provider_combo.blockSignals(True)
        self.resource_provider_combo.clear()
        for option in options:
            self.resource_provider_combo.addItem(option, option)
        index = self.resource_provider_combo.findText(current)
        self.resource_provider_combo.setCurrentIndex(index if index >= 0 else 0)
        self.resource_provider_combo.blockSignals(False)

    def _load_ip_pools(self, preferred_pool_id: str | None = None):
        self.ip_pool_combo.clear()
        pool_manager = get_ip_pool_manager()
        pools = pool_manager.list_pools()
        for pool in pools:
            self.ip_pool_combo.addItem(pool.name, pool.id)

        if not pools:
            self.ip_pool_combo.addItem("无可用 IP 池", "")
            self.ip_pool_combo.setEnabled(False)
            return

        self.ip_pool_combo.setEnabled(True)
        if preferred_pool_id:
            idx = self.ip_pool_combo.findData(preferred_pool_id)
            if idx >= 0:
                self.ip_pool_combo.setCurrentIndex(idx)

    def _on_resource_mode_changed(self, index):
        del index
        create_mode = self.resource_mode_combo.currentData() == AcquisitionMode.CREATE
        self.resource_mode_stack.setCurrentIndex(0 if create_mode else 1)
        self._set_row_visible(self.resource_provider_combo, create_mode)
        self._set_row_visible(self.create_env_type_combo, create_mode)
        self._load_provider_options()
        self._sync_create_fields()

    def _on_create_env_type_changed(self, index):
        del index
        self._load_provider_options()
        self._sync_create_fields()

    def _sync_create_fields(self, *_args):
        create_mode = self.resource_mode_combo.currentData() == AcquisitionMode.CREATE
        create_env_type = self.create_env_type_combo.currentData()
        is_fingerprint = create_mode and create_env_type == EnvType.VIRTUAL_BROWSER
        is_virtualbrowser = is_fingerprint and self.resource_provider_combo.currentText() == "virtualbrowser"

        self._set_row_visible(self.ip_binding_combo, is_fingerprint)
        self._set_row_visible(self.browser_version_combo, is_virtualbrowser)
        self._set_row_visible(self.kernel_version_combo, is_virtualbrowser)
        self._set_row_visible(self.randomize_fingerprint_check, is_virtualbrowser)
        self.virtualbrowser_group.setVisible(is_virtualbrowser)

        if not is_fingerprint:
            self._set_row_visible(self.ip_pool_combo, False)
            self._set_row_visible(self.ip_pool_strategy_combo, False)
            self._set_row_visible(self.manual_proxy_edit, False)
            return

        self._on_ip_binding_changed(self.ip_binding_combo.currentIndex())

    def _on_ip_binding_changed(self, index: int):
        del index
        show_proxy = self.resource_mode_combo.currentData() == AcquisitionMode.CREATE and (
            self.create_env_type_combo.currentData() == EnvType.VIRTUAL_BROWSER
        )
        if not show_proxy:
            self._set_row_visible(self.ip_pool_combo, False)
            self._set_row_visible(self.ip_pool_strategy_combo, False)
            self._set_row_visible(self.manual_proxy_edit, False)
            return

        strategy = self.ip_binding_combo.currentData()
        self._set_row_visible(self.ip_pool_combo, strategy == "pool")
        self._set_row_visible(self.ip_pool_strategy_combo, strategy == "pool")
        self._set_row_visible(self.manual_proxy_edit, strategy == "static")

    def _current_script_module_name(self) -> str:
        module_name, _workflow_name = self.script_selector.get_value()
        if module_name:
            return module_name
        return self.script_selector.module_combo.currentText().strip()

    def _load_selector_options(self, preferred: str | None = None) -> None:
        module_name = self._current_script_module_name()
        selectors = []
        if module_name:
            try:
                selectors = list(get_module_service().list_env_selectors(module_name))
            except Exception:
                selectors = []

        self._selector_infos = {selector.name: selector for selector in selectors}

        self.selector_name_combo.blockSignals(True)
        self.selector_name_combo.clear()
        for selector in selectors:
            label = selector.display_name or selector.name
            self.selector_name_combo.addItem(label, selector.name)

        if preferred:
            index = self.selector_name_combo.findData(preferred)
            self.selector_name_combo.setCurrentIndex(index if index >= 0 else -1)
        else:
            self.selector_name_combo.setCurrentIndex(-1)
        self.selector_name_combo.blockSignals(False)

        has_selectors = bool(selectors)
        self.selector_empty_hint.setVisible(bool(module_name) and not has_selectors)
        self._update_selector_none_hint()

    def _update_selector_none_hint(self) -> None:
        selector_name = self.selector_name_combo.currentData()
        normalized_selector = selector_name if isinstance(selector_name, str) else ""
        self.selector_none_hint.setVisible(
            selector_returns_none(self._selector_infos, normalized_selector)
        )

    def _on_script_module_changed(self, _module_name: str) -> None:
        previous = self.selector_name_combo.currentData()
        preferred = previous if isinstance(previous, str) else None
        self._load_selector_options(preferred=preferred)

    def _on_selector_name_changed(self, _index: int) -> None:
        self._update_selector_none_hint()

    def _create_yaml_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.yaml_editor = QPlainTextEdit()
        self.yaml_editor.setStyleSheet("font-family: monospace; background: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.yaml_editor)
        return widget

    def _switch_mode(self, mode):
        if mode == "form":
            if not self._yaml_to_form(show_error=True):
                self.stack.setCurrentIndex(1)
                self.form_btn.setChecked(False)
                self.yaml_btn.setChecked(True)
                return
            self.stack.setCurrentIndex(0)
            self.form_btn.setChecked(True)
            self.yaml_btn.setChecked(False)
        else:
            self._form_to_yaml()
            self.stack.setCurrentIndex(1)
            self.form_btn.setChecked(False)
            self.yaml_btn.setChecked(True)

    def _provider_to_env_type(self, provider: str) -> EnvType:
        if provider == "bitbrowser":
            return EnvType.BIT_BROWSER
        if provider == "virtualbrowser":
            return EnvType.VIRTUAL_BROWSER
        return EnvType.CHROME

    def _build_proxy_config_from_form(self) -> dict | None:
        strategy = self.ip_binding_combo.currentData()
        if strategy == "none":
            return None
        if strategy == "system":
            return {"mode": "system"}
        if strategy == "pool":
            pool_id = self.ip_pool_combo.currentData()
            if not pool_id:
                raise ValueError("请选择可用的 IP 池")
            return {
                "mode": "pool",
                "pool_id": pool_id,
                "bind_strategy": self.ip_pool_strategy_combo.currentData(),
            }
        if strategy == "static":
            raw_proxy = self.manual_proxy_edit.text().strip()
            if not raw_proxy:
                raise ValueError("手动代理地址不能为空")
            return {"mode": "static", "static_value": raw_proxy}
        return None

    def _load_run_profile(self):
        s = self._run_profile
        acquisition = s.resource.acquisition

        mode_index = self.resource_mode_combo.findData(acquisition.mode)
        if mode_index >= 0:
            self.resource_mode_combo.setCurrentIndex(mode_index)

        if acquisition.provider == "playwright_local" or acquisition.env_type == EnvType.CHROME:
            create_env_type = EnvType.CHROME
        else:
            create_env_type = EnvType.VIRTUAL_BROWSER
        type_index = self.create_env_type_combo.findData(create_env_type)
        if type_index >= 0:
            self.create_env_type_combo.setCurrentIndex(type_index)
        self._load_provider_options(acquisition.provider or "virtualbrowser")

        provider_index = self.resource_provider_combo.findText(acquisition.provider)
        if provider_index >= 0:
            self.resource_provider_combo.setCurrentIndex(provider_index)

        self.wait_timeout_spin.setValue(acquisition.wait_timeout)
        self.resource_pool_edit.setText(acquisition.resource_pool or "")

        creation_params = acquisition.creation.params
        provider = acquisition.provider
        provider_params = creation_params.get("virtualbrowser") if provider == "virtualbrowser" else {}
        if not isinstance(provider_params, dict):
            provider_params = {}
        self._load_virtualbrowser_params(provider_params)
        if acquisition.mode == AcquisitionMode.CREATE and not provider_params:
            self._apply_new_virtualbrowser_defaults()

        proxy_params = creation_params.get("proxy", {}) if isinstance(creation_params.get("proxy"), dict) else {}
        self._load_ip_pools(proxy_params.get("pool_id"))
        proxy_mode = str(proxy_params.get("mode", "none"))
        strategy_index = self.ip_binding_combo.findData(proxy_mode)
        self.ip_binding_combo.setCurrentIndex(strategy_index if strategy_index >= 0 else 0)
        bind_strategy_index = self.ip_pool_strategy_combo.findData(proxy_params.get("bind_strategy"))
        if bind_strategy_index >= 0:
            self.ip_pool_strategy_combo.setCurrentIndex(bind_strategy_index)
        self.manual_proxy_edit.setText(str(proxy_params.get("static_value", "")))

        if s.execution and s.execution.module:
            self.script_selector.set_value(s.execution.module, s.execution.workflow)
        self._load_selector_options(acquisition.selector_name or None)

        selector_index = self.selector_name_combo.findData(acquisition.selector_name)
        if selector_index >= 0:
            self.selector_name_combo.setCurrentIndex(selector_index)
        elif acquisition.mode == AcquisitionMode.SELECT:
            self.selector_name_combo.setCurrentIndex(-1)

        self._on_resource_mode_changed(self.resource_mode_combo.currentIndex())


    def _build_run_profile_from_form(self) -> RunProfile:
        acquisition_mode = self.resource_mode_combo.currentData()
        provider = self.resource_provider_combo.currentText().strip() or "virtualbrowser"
        env_type = self._provider_to_env_type(provider)
        creation_params: dict = {}
        selector_name = ""
        resource_pool = ""

        if acquisition_mode == AcquisitionMode.CREATE and env_type in {EnvType.BIT_BROWSER, EnvType.VIRTUAL_BROWSER}:
            provider_params = self._build_virtualbrowser_params() if provider == "virtualbrowser" else {}
            if provider_params:
                if provider == "virtualbrowser":
                    creation_params["virtualbrowser"] = provider_params
                else:
                    creation_params["fingerprint"] = provider_params

            proxy_config = self._build_proxy_config_from_form()
            if proxy_config:
                creation_params["proxy"] = proxy_config

        if acquisition_mode == AcquisitionMode.SELECT:
            selector_data = self.selector_name_combo.currentData()
            selector_name = selector_data.strip() if isinstance(selector_data, str) else ""
            resource_pool = self.resource_pool_edit.text().strip()
            if not selector_name and not resource_pool:
                raise ValueError("请选择环境选择回调函数或填写资源池")
            provider = ""
            env_type = EnvType.VIRTUAL_BROWSER

        resource = ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=acquisition_mode,
                provider=provider,
                env_type=env_type,
                selector_name=selector_name,
                resource_pool=resource_pool,
                wait_timeout=self.wait_timeout_spin.value(),
                creation=CreationConfig(
                    lifecycle=CreationLifecycle.PERSISTENT,
                    params=creation_params,
                ),
            ),
        )
        
        module_name, workflow_name = self.script_selector.get_value()
        if not module_name or not workflow_name:
            raise ValueError("请选择执行脚本")
        previous_execution = self._run_profile.execution
        execution = ExecutionContext(
            module=module_name,
            workflow=workflow_name,
            hooks_module=previous_execution.hooks_module if previous_execution else "",
            params=dict(previous_execution.params) if previous_execution else {},
            timeout=previous_execution.timeout if previous_execution else 600,
        )
        
        return RunProfile(
            resource=resource,
            execution=execution,
        )

    def _form_to_yaml(self):
        try:
            s = self._build_run_profile_from_form()
            self.yaml_editor.setPlainText(s.to_yaml())
        except Exception as e:
            self.yaml_editor.setPlainText(f"# Error building YAML: {e}")

    def _yaml_to_form(self, *, show_error: bool = False) -> bool:
        yaml_str = self.yaml_editor.toPlainText()
        if not yaml_str.strip():
            return True

        try:
            parsed_profile = RunProfile.from_yaml(yaml_str)
        except Exception as exc:
            if show_error:
                QMessageBox.warning(self, "YAML 无效", f"运行模板 YAML 保存失败：{exc}")
            return False

        self._run_profile = parsed_profile
        try:
            self._load_run_profile()
        except Exception as exc:
            if show_error:
                QMessageBox.warning(self, "YAML 无效", f"运行模板 YAML 保存失败：{exc}")
            return False

        return True

    def _on_save(self):
        if self.stack.currentIndex() == 1:
            if not self._yaml_to_form(show_error=True):
                return
        else:
            self._run_profile = self._build_run_profile_from_form()
            
        self.accept()

    def get_run_profile(self) -> RunProfile:
        return self._run_profile
