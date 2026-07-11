"""运行模板编辑弹窗。"""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones

import yaml
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.mms import get_module_registry
from src.core.mms.service import get_module_service
from src.core.rem.env_claims import ENV_CLAIM_NAMESPACE, ENV_CLAIM_OWNER_MODULE
from src.core.rem.fingerprint_validation import (
    FINGERPRINT_VALIDATION_NAMESPACE,
    is_fingerprint_validation_risk,
)
from src.core.rem.ip_pool import get_ip_pool_manager
from src.core.rem.manager import get_environment_manager
from src.core.rem.models import EnvKind, EnvStatus
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
from src.core.foundation.logging import logger
from src.core.system.config_center import get_config_center
from src.ui.components.button import StyledButton
from src.ui.components.check_box import StyledCheckBox as QCheckBox
from src.ui.components.check_box import ToggleSwitch
from src.ui.components.combo_box import StyledComboBox as QComboBox
from src.ui.components.dialog_window import configure_titled_dialog
from src.ui.components.line_edit import StyledLineEdit as QLineEdit
from src.ui.components.message_dialog import MessageDialog
from src.ui.components.object_graph_tree import ObjectGraphTree
from src.ui.components.segmented_control import SegmentedOptionControl
from src.ui.components.spin_box import StyledDoubleSpinBox as QDoubleSpinBox
from src.ui.components.spin_box import StyledSpinBox as QSpinBox
from src.ui.components.text_edit import StyledPlainTextEdit as QPlainTextEdit
from src.ui.components.yaml_code_editor import YamlCodeEditor


class CandidateParamsDialog(QDialog):
    """候选函数参数编辑弹窗。"""

    def __init__(self, params: dict[str, object] | None = None, parent=None, read_only: bool = False):
        super().__init__(parent)
        self._params = dict(params or {})
        self._read_only = read_only
        self._setup_ui()
        self.editor.setPlainText(self._params_to_yaml(self._params))

    def _setup_ui(self) -> None:
        self.setWindowTitle("配置候选参数")
        configure_titled_dialog(self)
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.editor = YamlCodeEditor()
        self.editor.setReadOnly(self._read_only)
        layout.addWidget(self.editor, 1)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_btn = StyledButton(
            "关闭" if self._read_only else "取消",
            variant="secondary",
            min_height=32,
            min_width=80,
            border_radius=4,
        )
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        if not self._read_only:
            save_btn = StyledButton("保存参数", variant="success", min_height=32, min_width=92, border_radius=4)
            save_btn.clicked.connect(self._on_save)
            button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    @staticmethod
    def _params_to_yaml(params: dict[str, object]) -> str:
        if not params:
            return ""
        return yaml.safe_dump(params, allow_unicode=True, sort_keys=False)

    def _parse_candidate_params(self) -> dict[str, object]:
        raw_text = self.editor.toPlainText()
        if not raw_text.strip():
            return {}
        parsed = yaml.safe_load(raw_text)
        if parsed is None:
            return {}
        if not isinstance(parsed, dict):
            raise ValueError("候选参数必须是 YAML 对象")
        return dict(parsed)

    def _on_save(self) -> None:
        try:
            self._params = self._parse_candidate_params()
        except Exception as exc:
            MessageDialog.warning(self, "候选参数无效", str(exc))
            return
        self.accept()

    def get_params(self) -> dict[str, object]:
        return dict(self._params)


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
        layout.setSpacing(0)  # Remove spacing to behave like a single control when module is hidden

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
            workflows = registry.get_workflows(module_name)
            if workflows:
                for wf in workflows:
                    self.workflow_combo.addItem(wf.display_name or wf.name, wf.name)
            else:
                # Try refresh ?
                registry.refresh()
                for wf in registry.get_workflows(module_name):
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
    {"label": "英语", "language": "en-US", "value": "en"},
    {"label": "简体中文", "language": "zh-CN", "value": "zh"},
    {"label": "繁体中文", "language": "zh-TW", "value": "zh"},
    {"label": "日语", "language": "ja-JP", "value": "ja"},
    {"label": "韩语", "language": "ko-KR", "value": "ko"},
    {"label": "法语", "language": "fr-FR", "value": "fr"},
    {"label": "德语", "language": "de-DE", "value": "de"},
    {"label": "西班牙语", "language": "es-AR", "value": "es"},
    {"label": "西班牙语", "language": "es-ES", "value": "es"},
    {"label": "葡萄牙语", "language": "pt-BR", "value": "pt"},
    {"label": "葡萄牙语", "language": "pt-PT", "value": "pt"},
    {"label": "俄语", "language": "ru-RU", "value": "ru"},
    {"label": "越南语", "language": "vi-VN", "value": "vi"},
    {"label": "泰语", "language": "th-TH", "value": "th"},
    {"label": "印度尼西亚语", "language": "id-ID", "value": "id"},
    {"label": "马来语", "language": "ms-MY", "value": "ms"},
    {"label": "意大利语", "language": "it-IT", "value": "it"},
    {"label": "土耳其语", "language": "tr-TR", "value": "tr"},
    {"label": "阿拉伯语", "language": "ar-SA", "value": "ar"},
    {"label": "印地语", "language": "hi-IN", "value": "hi"},
    {"label": "孟加拉语", "language": "bn-BD", "value": "bn"},
    {"label": "波斯语", "language": "fa-IR", "value": "fa"},
    {"label": "达里语", "language": "prs-AF", "value": "fa"},
    {"label": "普什图语", "language": "ps-AF", "value": "ps"},
    {"label": "阿尔巴尼亚语", "language": "sq-AL", "value": "sq"},
    {"label": "亚美尼亚语", "language": "hy-AM", "value": "hy"},
    {"label": "加泰罗尼亚语", "language": "ca-ES", "value": "ca"},
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


class RunProfileDialog(QDialog):
    """运行模板编辑弹窗。"""

    def __init__(self, run_profile: RunProfile | None = None, parent=None, read_only: bool = False):
        super().__init__(parent)
        self._run_profile = run_profile or self._default_run_profile()
        self._candidate_params: dict[str, object] = dict(
            self._run_profile.resource.acquisition.candidate_params or {}
        )
        self._is_new = run_profile is None
        self._read_only = read_only
        self._setup_ui()
        self._load_run_profile()

        if self._read_only:
            self._set_read_only()

    def _setup_ui(self):
        self.setWindowTitle("配置运行模板")
        configure_titled_dialog(self)

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
        self.form_btn = self._create_mode_button("📝 表单配置")
        self.yaml_btn = self._create_mode_button("📄 YAML 源码")
        self.form_btn.clicked.connect(lambda: self._switch_mode("form"))
        self.yaml_btn.clicked.connect(lambda: self._switch_mode("yaml"))
        self._set_mode_button_active(self.form_btn, True)
        self._set_mode_button_active(self.yaml_btn, False)

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

        validate_btn = StyledButton("验证模板", variant="secondary", min_height=32, min_width=92, border_radius=4)
        validate_btn.clicked.connect(self._on_validate)
        cancel_btn = StyledButton("取消", variant="secondary", min_height=32, min_width=80, border_radius=4)
        cancel_btn.clicked.connect(self.reject)

        save_btn = StyledButton("保存运行模板", variant="success", min_height=32, min_width=116, border_radius=4)
        save_btn.clicked.connect(self._on_save)

        btn_layout.addWidget(validate_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)

        if self._read_only:
            validate_btn.hide()
            save_btn.hide()
            cancel_btn.setText("关闭")

        layout.addLayout(btn_layout)

    def _set_read_only(self):
        """设置只读模式。"""
        # Disable all input widgets
        for widget in self.findChildren(
            (
                QLineEdit,
                QPlainTextEdit,
                QSpinBox,
                QDoubleSpinBox,
                QCheckBox,
                ToggleSwitch,
                QComboBox,
                SegmentedOptionControl,
                YamlCodeEditor,
            )
        ):
            # QComboBox and QCheckBox use setEnabled
            if isinstance(widget, (QComboBox, QCheckBox, ToggleSwitch, SegmentedOptionControl)):
                widget.setEnabled(False)
            elif isinstance(widget, (QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, YamlCodeEditor)):
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
            "candidate_params_btn",
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

    def _set_mode_button_active(self, button: StyledButton, active: bool) -> None:
        button.setChecked(active)
        button.set_variant("primary" if active else "secondary")

    def _create_mode_button(self, text: str) -> StyledButton:
        button = StyledButton(
            text,
            variant="secondary",
            min_height=32,
            border_radius=4,
            horizontal_padding=16,
        )
        button.setCheckable(True)
        return button

    def _create_round_action_button(self, text: str, variant: str = "secondary") -> StyledButton:
        button = StyledButton(
            text,
            variant=variant,
            min_height=48,
            min_width=48,
            border_radius=24,
            horizontal_padding=0,
        )
        button.setFixedSize(48, 48)
        button.setStyleSheet(
            button.styleSheet()
            + """
            QPushButton {
                font-size: 24px;
            }
            """
        )
        return button

    def _create_link_button(self, text: str) -> StyledButton:
        button = StyledButton(
            text,
            variant="text",
            min_height=24,
            horizontal_padding=4,
            border_radius=4,
        )
        button.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self._set_mode_button_active(self.ua_default_btn, mode == "default")
        self._set_mode_button_active(self.ua_custom_btn, mode == "custom")
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
        del force_regenerate
        for control in (
            self.fonts_mode_combo,
            self.canvas_mode_combo,
            self.webgl_image_mode_combo,
            self.audio_context_mode_combo,
            self.client_rects_mode_combo,
            self.speech_voices_mode_combo,
        ):
            self._set_combo_value(control, "random")
        self._set_ua_mode("default")
        self._set_sec_ch_ua_mode("default")
        self.language_follow_ip_check.setChecked(True)
        self.timezone_follow_ip_check.setChecked(True)
        self.location_follow_ip_check.setChecked(True)
        self._set_combo_value(self.screen_mode_combo, "default")
        self._set_combo_value(self.webgl_mode_combo, "default")
        self._set_combo_value(self.webgpu_mode_combo, "default")
        self._set_combo_value(self.device_name_mode_combo, "default")
        self._set_combo_value(self.mac_mode_combo, "default")
        self._sync_virtualbrowser_field_visibility()

    def _on_randomize_fingerprint_toggled(self, checked: bool) -> None:
        if checked:
            self._apply_randomize_fingerprint_defaults(force_regenerate=True)
        self._sync_create_fields()

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
        self._set_mode_button_active(self.sec_ch_ua_default_btn, mode == "default")
        self._set_mode_button_active(self.sec_ch_ua_custom_btn, mode == "custom")
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

        remove_btn = self._create_round_action_button("−", "danger")
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
        self.ua_random_btn = StyledButton("随机", variant="primary", min_height=36, min_width=80, border_radius=4)
        self.ua_random_btn.setFixedSize(80, 36)
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
        self.sec_ch_ua_add_btn = self._create_round_action_button("+")
        self.sec_ch_ua_add_btn.clicked.connect(self._add_sec_ch_ua_entry)
        sec_ch_action_layout.addWidget(self.sec_ch_ua_add_btn)
        sec_ch_editor_layout.addLayout(sec_ch_action_layout)
        form.addRow("", self.sec_ch_ua_editor_widget)

        self.language_follow_ip_check = QCheckBox("语言跟随 IP")
        self.language_follow_ip_check.setChecked(True)
        self.language_follow_ip_check.stateChanged.connect(self._sync_virtualbrowser_field_visibility)
        form.addRow("", self.language_follow_ip_check)
        self.language_combo = QComboBox()
        for option in VIRTUALBROWSER_LANGUAGE_OPTIONS:
            self.language_combo.addItem(self._format_language_label(option), dict(option))
        self.language_combo.setMaxVisibleItems(12)
        form.addRow("语言:", self.language_combo)

        self.timezone_follow_ip_check = QCheckBox("时区跟随 IP")
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

        self.basic_group = QGroupBox("一、模板信息")
        form = self._create_form_layout(self.basic_group)

        self.script_selector = WorkflowSelector(show_module=True)
        self.script_selector.workflow_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        form.addRow("模块 / 工作流:", self.script_selector)

        self.object_assembly_widget = QWidget()
        object_assembly_layout = QVBoxLayout(self.object_assembly_widget)
        object_assembly_layout.setContentsMargins(0, 0, 0, 0)
        object_assembly_layout.setSpacing(0)
        self.object_assembly_tree = ObjectGraphTree()
        object_assembly_layout.addWidget(self.object_assembly_tree)
        self._object_binding_widgets: dict[str, QComboBox] = {}
        self._object_param_widgets: dict[str, dict[str, QWidget]] = {}
        self._object_param_specs: dict[str, dict[str, object]] = {}
        self._rendered_object_components: set[str] = set()
        self._object_assembly_refresh_pending = False
        self._pending_object_assembly_values: dict | None = None
        form.addRow("对象装配:", self.object_assembly_widget)

        self.execution_timeout_spin = QSpinBox()
        self.execution_timeout_spin.setRange(0, 7 * 24 * 60 * 60)
        self.execution_timeout_spin.setValue(self._default_execution_timeout())
        self.execution_timeout_spin.setToolTip("0 表示不自动中断模块主体；2 天为 172800 秒，3 天为 259200 秒。")
        form.addRow("主体执行超时:", self._wrap_widget_with_suffix(self.execution_timeout_spin, "秒"))

        layout.addWidget(self.basic_group)

        self.resource_group = QGroupBox("二、环境与资源")
        self.resource_form = self._create_form_layout(self.resource_group)

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
        self.ip_pool_strategy_combo.addItem("最久未使用", "least_recently_used")
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

        self.select_strategy_combo = QComboBox()
        self.select_strategy_combo.addItem("指定环境", "fixed")
        self.select_strategy_combo.addItem("候选函数", "candidates")
        self.select_strategy_combo.currentIndexChanged.connect(self._on_select_strategy_changed)
        self.select_form.addRow("选择方式:", self.select_strategy_combo)

        self.fixed_env_combo = QComboBox()
        self.fixed_env_combo.setPlaceholderText("选择当前模块可用环境")
        self._fixed_env_by_id: dict[int, object] = {}
        self.select_form.addRow("指定环境:", self.fixed_env_combo)

        self.candidates_combo = QComboBox()
        self.candidates_combo.setPlaceholderText("选择候选函数")
        self.select_form.addRow("候选函数:", self.candidates_combo)

        self.candidate_params_widget = QWidget()
        candidate_params_layout = QHBoxLayout(self.candidate_params_widget)
        candidate_params_layout.setContentsMargins(0, 0, 0, 0)
        candidate_params_layout.setSpacing(8)
        self.candidate_params_summary = QLabel("未配置")
        self.candidate_params_summary.setStyleSheet("color: rgba(255, 255, 255, 0.72);")
        self.candidate_params_summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        candidate_params_layout.addWidget(self.candidate_params_summary, 1)
        self.candidate_params_btn = StyledButton(
            "配置参数",
            variant="secondary",
            min_height=32,
            min_width=88,
            border_radius=4,
        )
        self.candidate_params_btn.clicked.connect(self._open_candidate_params_dialog)
        candidate_params_layout.addWidget(self.candidate_params_btn)
        self.select_form.addRow("候选参数:", self.candidate_params_widget)

        self.select_form.addRow(
            "等待超时:",
            self._wrap_widget_with_suffix(self.wait_timeout_spin, "秒"),
        )
        select_layout.addWidget(select_form_widget)

        self.select_desc = QLabel()
        self.select_desc.setWordWrap(True)
        self.select_desc.setStyleSheet("color: rgba(255, 255, 255, 0.72);")
        select_layout.addWidget(self.select_desc)
        select_layout.addStretch()

        self.resource_mode_stack.addWidget(select_widget)
        self.resource_form.addRow("模式配置:", self.resource_mode_stack)

        layout.addWidget(self.resource_group)
        layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        self._load_ip_pools()
        self._load_provider_options("virtualbrowser")
        self.script_selector.module_combo.currentTextChanged.connect(self._on_script_module_changed)
        self.script_selector.workflow_combo.currentIndexChanged.connect(self._on_workflow_selection_changed)
        self._sync_fixed_env_options()
        self._sync_candidates_options()
        self._on_select_strategy_changed(self.select_strategy_combo.currentIndex())
        self._sync_object_assembly_form()
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

        if randomize_fingerprint:
            return {VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY: True}

        params: dict[str, object] = {
            "chrome_version": self._current_browser_version(),
        }

        if getattr(self, "_ua_mode", "default") == "custom":
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

        if self.device_name_mode_combo.currentData() == "custom":
            device_name = self.device_name_edit.text().strip()
            if device_name:
                params["device-name"] = {"mode": 1, "value": device_name}

        if self.mac_mode_combo.currentData() == "custom":
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
            self._apply_randomize_fingerprint_defaults(force_regenerate=False)
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
        self.virtualbrowser_group.setVisible(
            is_virtualbrowser and not self.randomize_fingerprint_check.isChecked()
        )

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

    def _on_script_module_changed(self, _module_name: str) -> None:
        previous_candidates = self.candidates_combo.currentData()
        preferred = previous_candidates if isinstance(previous_candidates, str) else None
        current_env_id = self.fixed_env_combo.currentData()
        preferred_env_id = int(current_env_id) if isinstance(current_env_id, int) else None
        self._sync_fixed_env_options(preferred=preferred_env_id)
        self._sync_candidates_options(preferred=preferred)
        self._sync_object_assembly_form()

    def _on_workflow_selection_changed(self, _index: int) -> None:
        self._sync_object_assembly_form()

    def _current_runtime_descriptor(self) -> object | None:
        module_name, _workflow_name = self.script_selector.get_value()
        if not module_name:
            return None
        try:
            return get_module_service().get_runtime_descriptor_v2(module_name)
        except Exception as exc:
            logger.warning(f"[ATM] 加载模块对象装配描述失败: module={module_name} error={exc}")
            return None

    def _current_workflow_entry(self, descriptor: object) -> object | None:
        _module_name, workflow_name = self.script_selector.get_value()
        if not workflow_name:
            return None
        workflows = getattr(descriptor, "workflows", {}) or {}
        if isinstance(workflows, dict):
            return workflows.get(workflow_name)
        return None

    def _clear_object_assembly_form(self) -> None:
        self.object_assembly_tree.clear()
        self._object_binding_widgets = {}
        self._object_param_widgets = {}
        self._object_param_specs = {}
        self._rendered_object_components = set()

    def _sync_object_assembly_form(self, values: dict | None = None) -> None:
        if not hasattr(self, "object_assembly_tree"):
            return
        current_values = values if values is not None else self._initial_object_assembly_values()
        descriptor = self._current_runtime_descriptor()
        workflow_entry = self._current_workflow_entry(descriptor) if descriptor is not None else None

        self._clear_object_assembly_form()
        if workflow_entry is None:
            self._set_row_visible(self.object_assembly_widget, False)
            return

        inject_specs = list(getattr(workflow_entry.meta, "inject", ()) or ())
        if not inject_specs:
            self._set_row_visible(self.object_assembly_widget, False)
            return

        self._set_row_visible(self.object_assembly_widget, True)
        _module_name, workflow_name = self.script_selector.get_value()
        workflow_item = self.object_assembly_tree.add_node(
            f"工作流: {self._entry_label(workflow_entry, workflow_name)}",
            role="workflow",
        )
        self._render_inject_specs(
            descriptor,
            inject_specs,
            parent_path="",
            values=current_values,
            seen_components=set(),
            parent_item=workflow_item,
        )
        self.object_assembly_tree.finalize()

    def _initial_object_assembly_values(self) -> dict[str, dict]:
        execution = self._run_profile.execution
        if execution is None:
            return {"object_bindings": {}, "object_params": {}}
        return {
            "object_bindings": dict(execution.object_bindings),
            "object_params": {
                component_name: dict(params)
                for component_name, params in dict(execution.object_params).items()
                if isinstance(params, dict)
            },
        }

    def _current_object_assembly_values(self) -> dict[str, dict]:
        object_bindings: dict[str, str] = {}
        for inject_path, widget in self._object_binding_widgets.items():
            value = widget.currentData()
            if isinstance(value, str) and value.strip():
                object_bindings[inject_path] = value.strip()

        object_params: dict[str, dict[str, object]] = {}
        for component_name, parameter_specs in self._object_param_specs.items():
            component_params: dict[str, object] = {}
            for parameter_name, parameter in parameter_specs.items():
                widget = self._object_param_widgets.get(component_name, {}).get(parameter_name)
                if widget is None:
                    continue
                value = self._parameter_widget_value(parameter, widget)
                if value is None:
                    continue
                if self._parameter_required(parameter) and self._parameter_type(parameter) in {"string", "text", "enum"}:
                    if str(value).strip() == "":
                        raise ValueError(f"对象参数不能为空: {self._parameter_label(parameter)}")
                component_params[parameter_name] = value
            if component_params:
                object_params[component_name] = component_params
        return {"object_bindings": object_bindings, "object_params": object_params}

    def _on_object_binding_changed(self) -> None:
        try:
            values = self._current_object_assembly_values()
        except Exception:
            values = self._initial_object_assembly_values()
        self._schedule_object_assembly_refresh(values)

    def _schedule_object_assembly_refresh(self, values: dict | None = None) -> None:
        self._pending_object_assembly_values = values
        if self._object_assembly_refresh_pending:
            return
        self._object_assembly_refresh_pending = True
        QTimer.singleShot(0, self._flush_object_assembly_refresh)

    def _flush_object_assembly_refresh(self) -> None:
        self._object_assembly_refresh_pending = False
        values = self._pending_object_assembly_values
        self._pending_object_assembly_values = None
        self._sync_object_assembly_form(values)

    def _render_inject_specs(
        self,
        descriptor: object,
        inject_specs: list[object],
        *,
        parent_path: str,
        values: dict,
        seen_components: set[str],
        parent_item: QTreeWidgetItem,
    ) -> None:
        for inject in inject_specs:
            inject_name = str(getattr(inject, "name", "") or "").strip()
            inject_type = str(getattr(inject, "type", "") or "").strip().lower()
            inject_target = str(getattr(inject, "target", "") or "").strip()
            if not inject_name or not inject_target:
                continue
            inject_path = f"{parent_path}.{inject_name}" if parent_path else inject_name
            if inject_type == "interface":
                selected_component, component_item = self._render_interface_binding(
                    descriptor,
                    inject_path=inject_path,
                    interface_name=inject_target,
                    values=values,
                    parent_item=parent_item,
                )
                if selected_component:
                    self._render_component_body(
                        descriptor,
                        selected_component,
                        parent_path=inject_path,
                        values=values,
                        seen_components=seen_components,
                        component_item=component_item,
                    )
                continue
            if inject_type == "object":
                self._render_component(
                    descriptor,
                    inject_target,
                    parent_path=inject_path,
                    values=values,
                    seen_components=seen_components,
                    parent_item=parent_item,
                    tooltip=f"注入路径: {inject_path}\n固定对象: {inject_target}",
                )

    def _render_interface_binding(
        self,
        descriptor: object,
        *,
        inject_path: str,
        interface_name: str,
        values: dict,
        parent_item: QTreeWidgetItem,
    ) -> tuple[str, QTreeWidgetItem]:
        combo = QComboBox()
        combo.setObjectName(f"objectBinding_{inject_path.replace('.', '__')}")
        combo.setMinimumWidth(220)
        implementations = tuple((getattr(descriptor, "implementations", {}) or {}).get(interface_name, ()) or ())
        components = getattr(descriptor, "components", {}) or {}
        for component_name in implementations:
            component_entry = components.get(component_name) if isinstance(components, dict) else None
            combo.addItem(self._entry_label(component_entry, component_name), component_name)

        object_bindings = dict(values.get("object_bindings") or {})
        selected = str(object_bindings.get(inject_path) or object_bindings.get(interface_name) or "").strip()
        if selected and combo.findData(selected) < 0:
            combo.addItem(f"{selected} (未声明)", selected)
        if not selected and combo.count() == 1:
            selected = str(combo.itemData(0) or "")

        index = combo.findData(selected)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.setEnabled(combo.count() > 1 and not self._read_only)
        combo.currentIndexChanged.connect(lambda _index: self._on_object_binding_changed())
        self._object_binding_widgets[inject_path] = combo

        label = self._interface_label(descriptor, interface_name) or interface_name
        current = combo.currentData()
        component_name = current if isinstance(current, str) else ""
        item = self.object_assembly_tree.add_node(
            label,
            parent=parent_item,
            role="interface",
            tooltip=f"注入路径: {inject_path}\n接口: {interface_name}",
        )
        self.object_assembly_tree.set_config_widget(item, combo)
        return component_name, item

    def _render_component(
        self,
        descriptor: object,
        component_name: str,
        *,
        parent_path: str,
        values: dict,
        seen_components: set[str],
        parent_item: QTreeWidgetItem,
        tooltip: str = "",
    ) -> None:
        components = getattr(descriptor, "components", {}) or {}
        component_entry = components.get(component_name) if isinstance(components, dict) else None
        if component_entry is None or component_name in seen_components:
            return

        component_item = self.object_assembly_tree.add_node(
            self._entry_label(component_entry, component_name),
            parent=parent_item,
            role="component",
            tooltip=tooltip,
        )
        self._render_component_body(
            descriptor,
            component_name,
            parent_path=parent_path,
            values=values,
            seen_components=seen_components,
            component_item=component_item,
        )

    def _render_component_body(
        self,
        descriptor: object,
        component_name: str,
        *,
        parent_path: str,
        values: dict,
        seen_components: set[str],
        component_item: QTreeWidgetItem,
    ) -> None:
        components = getattr(descriptor, "components", {}) or {}
        component_entry = components.get(component_name) if isinstance(components, dict) else None
        if component_entry is None or component_name in seen_components:
            return
        next_seen = {*seen_components, component_name}
        inject_specs = list(getattr(component_entry.meta, "inject", ()) or ())
        if inject_specs:
            self._render_inject_specs(
                descriptor,
                inject_specs,
                parent_path=parent_path,
                values=values,
                seen_components=next_seen,
                parent_item=component_item,
            )
        if component_name not in self._rendered_object_components:
            self._render_component_parameters(component_name, component_entry, values, component_item)
            self._rendered_object_components.add(component_name)

    def _render_component_parameters(
        self,
        component_name: str,
        component_entry: object,
        values: dict,
        parent_item: QTreeWidgetItem,
    ) -> None:
        parameters = list(getattr(component_entry.meta, "parameters", ()) or ())
        if not parameters:
            return

        component_values = dict((values.get("object_params") or {}).get(component_name, {}) or {})
        self._object_param_widgets.setdefault(component_name, {})
        self._object_param_specs.setdefault(component_name, {})
        for parameter in parameters:
            name = self._parameter_name(parameter)
            if not name:
                continue
            value = component_values.get(name, self._parameter_default(parameter))
            widget = self._create_parameter_widget(parameter, value, object_name_prefix=f"objectParam_{component_name}")
            self._object_param_widgets[component_name][name] = widget
            self._object_param_specs[component_name][name] = parameter
            label = self._parameter_label(parameter)
            if self._parameter_required(parameter):
                label = f"{label} *"
            parameter_item = self.object_assembly_tree.add_node(
                f"参数: {label}",
                parent=parent_item,
                role="parameter",
            )
            self.object_assembly_tree.set_config_widget(parameter_item, widget)

    def _entry_label(self, entry: object | None, fallback: str) -> str:
        if entry is None:
            return fallback
        label = str(getattr(entry.meta, "label", "") or "").strip()
        name = str(getattr(entry.meta, "name", "") or fallback).strip()
        return f"{label} ({name})" if label and label != name else name

    def _interface_label(self, descriptor: object, interface_name: str) -> str:
        interfaces = getattr(descriptor, "interfaces", {}) or {}
        entry = interfaces.get(interface_name) if isinstance(interfaces, dict) else None
        return self._entry_label(entry, interface_name)

    def _parameter_name(self, parameter: object) -> str:
        return str(getattr(parameter, "name", "") or "").strip()

    def _parameter_label(self, parameter: object) -> str:
        return str(getattr(parameter, "label", "") or "").strip() or self._parameter_name(parameter)

    def _parameter_type(self, parameter: object) -> str:
        return str(getattr(parameter, "type", "string") or "string").strip().lower()

    def _parameter_default(self, parameter: object) -> object:
        return getattr(parameter, "default", None)

    def _parameter_required(self, parameter: object) -> bool:
        return bool(getattr(parameter, "required", False))

    def _parameter_options(self, parameter: object) -> list[tuple[str, object]]:
        options: list[tuple[str, object]] = []
        for option in getattr(parameter, "options", []) or []:
            if isinstance(option, dict):
                value = option.get("value")
                raw_label = option.get("label")
                label = str(value if raw_label is None else raw_label).strip()
            else:
                value = getattr(option, "value", option)
                raw_label = getattr(option, "label", None)
                label = str(value if raw_label is None else raw_label).strip()
            if label:
                options.append((label, value))
        return options

    def _create_parameter_widget(self, parameter: object, value: object, *, object_name_prefix: str) -> QWidget:
        parameter_type = self._parameter_type(parameter)
        name = self._parameter_name(parameter)
        placeholder = str(getattr(parameter, "placeholder", "") or "").strip()

        if parameter_type == "enum":
            combo = QComboBox()
            combo.setObjectName(f"{object_name_prefix}_{name}")
            if not self._parameter_required(parameter) and value is None:
                combo.addItem("不设置", None)
            for label, option_value in self._parameter_options(parameter):
                combo.addItem(label, option_value)
            index = combo.findData(value)
            if index >= 0:
                combo.setCurrentIndex(index)
            elif combo.count():
                combo.setCurrentIndex(0)
            return combo

        if parameter_type == "integer":
            spin = QSpinBox()
            spin.setObjectName(f"{object_name_prefix}_{name}")
            min_value = getattr(parameter, "min", None)
            max_value = getattr(parameter, "max", None)
            spin.setRange(
                int(min_value) if min_value is not None else -1_000_000_000,
                int(max_value) if max_value is not None else 1_000_000_000,
            )
            step = getattr(parameter, "step", None)
            if step is not None:
                spin.setSingleStep(max(1, int(step)))
            if value is not None:
                spin.setValue(int(value))
            return spin

        if parameter_type == "number":
            spin = QDoubleSpinBox()
            spin.setObjectName(f"{object_name_prefix}_{name}")
            min_value = getattr(parameter, "min", None)
            max_value = getattr(parameter, "max", None)
            spin.setRange(
                float(min_value) if min_value is not None else -1_000_000_000.0,
                float(max_value) if max_value is not None else 1_000_000_000.0,
            )
            spin.setDecimals(6)
            step = getattr(parameter, "step", None)
            if step is not None:
                spin.setSingleStep(float(step))
            if value is not None:
                spin.setValue(float(value))
            return spin

        if parameter_type == "boolean":
            toggle = self._create_toggle_switch()
            toggle.setObjectName(f"{object_name_prefix}_{name}")
            toggle.setChecked(bool(value))
            return toggle

        if parameter_type == "text":
            editor = QPlainTextEdit()
            editor.setObjectName(f"{object_name_prefix}_{name}")
            editor.setMinimumHeight(90)
            editor.setPlainText("" if value is None else str(value))
            if placeholder:
                editor.setPlaceholderText(placeholder)
            return editor

        line_edit = QLineEdit()
        line_edit.setObjectName(f"{object_name_prefix}_{name}")
        line_edit.setText("" if value is None else str(value))
        if placeholder:
            line_edit.setPlaceholderText(placeholder)
        return line_edit

    def _parameter_widget_value(self, parameter: object, widget: QWidget) -> object:
        parameter_type = self._parameter_type(parameter)
        if parameter_type == "enum" and isinstance(widget, QComboBox):
            return widget.currentData()
        if parameter_type == "integer" and isinstance(widget, QSpinBox):
            return widget.value()
        if parameter_type == "number" and isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if parameter_type == "boolean" and isinstance(widget, ToggleSwitch):
            return widget.isChecked()
        if parameter_type == "text" and isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        if isinstance(widget, QLineEdit):
            return widget.text()
        return None

    def _sync_candidate_params_summary(self) -> None:
        if not hasattr(self, "candidate_params_summary"):
            return
        keys = [str(key) for key in self._candidate_params.keys()]
        if not keys:
            self.candidate_params_summary.setText("未配置")
            return
        preview = ", ".join(keys[:3])
        if len(keys) > 3:
            preview = f"{preview} 等 {len(keys)} 项"
        self.candidate_params_summary.setText(preview)

    def _open_candidate_params_dialog(self) -> None:
        dialog = CandidateParamsDialog(self._candidate_params, parent=self, read_only=self._read_only)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._candidate_params = dialog.get_params()
        self._sync_candidate_params_summary()

    @staticmethod
    def _enum_value(value: object) -> str:
        return str(getattr(value, "value", value) or "")

    def _env_claim_owner(self, env: object) -> str:
        try:
            pool = get_environment_manager().pool
            list_metadata = getattr(pool, "list_metadata", None)
            if not callable(list_metadata):
                return ""
            metadata = list_metadata(int(getattr(env, "id")), ENV_CLAIM_NAMESPACE)
        except Exception as exc:
            logger.warning(f"[ATM] 读取环境归属失败: env_id={getattr(env, 'id', '')} error={exc}")
            return ""
        if not isinstance(metadata, dict):
            return ""
        return str(metadata.get(ENV_CLAIM_OWNER_MODULE) or "").strip()

    def _is_fixed_env_available_for_module(self, env: object, module_name: str) -> bool:
        if not module_name:
            return False
        if self._enum_value(getattr(env, "kind", "")) != EnvKind.BROWSER.value:
            return False
        if self._enum_value(getattr(env, "status", "")) != EnvStatus.READY.value:
            return False
        if getattr(env, "lease_id", None):
            return False
        if self._env_fingerprint_validation_risk(env):
            return False
        owner = self._env_claim_owner(env)
        return not owner or owner == module_name

    def _env_fingerprint_validation_risk(self, env: object) -> bool:
        try:
            pool = get_environment_manager().pool
            list_metadata = getattr(pool, "list_metadata", None)
            if not callable(list_metadata):
                return False
            metadata = list_metadata(int(getattr(env, "id")), FINGERPRINT_VALIDATION_NAMESPACE)
        except Exception as exc:
            logger.warning(f"[ATM] 读取环境指纹风险失败: env_id={getattr(env, 'id', '')} error={exc}")
            return False
        return is_fingerprint_validation_risk(metadata)

    def _list_fixed_env_options(self, module_name: str) -> list[object]:
        if not module_name:
            return []
        try:
            pool = get_environment_manager().pool
            raw_envs = getattr(pool, "_environments", {})
            envs = list(raw_envs.values()) if isinstance(raw_envs, dict) else list(raw_envs or [])
        except Exception as exc:
            logger.warning(f"[ATM] 加载可选环境失败: module={module_name} error={exc}")
            return []
        available = [
            env
            for env in envs
            if self._is_fixed_env_available_for_module(env, module_name)
        ]
        return sorted(available, key=lambda env: int(getattr(env, "id", 0) or 0))

    def _fixed_env_label(self, env: object, module_name: str) -> str:
        env_id = int(getattr(env, "id", 0) or 0)
        name = str(getattr(env, "name", "") or "-")
        provider = str(getattr(env, "provider", "") or "-")
        owner = self._env_claim_owner(env)
        owner_label = "当前模块" if owner == module_name else "未归属"
        return f"#{env_id} {name} | {provider} | {owner_label}"

    def _sync_fixed_env_options(self, preferred: int | None = None) -> None:
        if not hasattr(self, "fixed_env_combo"):
            return
        module_name = self._current_script_module_name()
        current_data = self.fixed_env_combo.currentData()
        current = preferred if preferred is not None else current_data if isinstance(current_data, int) else None
        envs = self._list_fixed_env_options(module_name)

        self.fixed_env_combo.blockSignals(True)
        self.fixed_env_combo.clear()
        self._fixed_env_by_id = {}
        if not envs:
            self.fixed_env_combo.addItem("当前模块没有可用环境", None)
            self.fixed_env_combo.setEnabled(False)
            self.fixed_env_combo.blockSignals(False)
            return

        self.fixed_env_combo.setEnabled(True)
        for env in envs:
            env_id = int(getattr(env, "id"))
            self._fixed_env_by_id[env_id] = env
            self.fixed_env_combo.addItem(self._fixed_env_label(env, module_name), env_id)

        index = self.fixed_env_combo.findData(current)
        self.fixed_env_combo.setCurrentIndex(index if index >= 0 else 0)
        self.fixed_env_combo.blockSignals(False)

    def _set_fixed_env_value(self, env_id: int | None) -> None:
        if env_id is None:
            return
        index = self.fixed_env_combo.findData(int(env_id))
        if index >= 0:
            self.fixed_env_combo.setCurrentIndex(index)

    def _set_select_strategy_value(self, value: str) -> None:
        index = self.select_strategy_combo.findData(value)
        if index >= 0:
            self.select_strategy_combo.setCurrentIndex(index)

    def _on_select_strategy_changed(self, _index: int) -> None:
        if not hasattr(self, "select_strategy_combo"):
            return
        fixed_mode = self.select_strategy_combo.currentData() == "fixed"
        self._set_row_visible(self.fixed_env_combo, fixed_mode)
        self._set_row_visible(self.candidates_combo, not fixed_mode)
        self._set_row_visible(self.candidate_params_widget, not fixed_mode)
        if fixed_mode:
            self.select_desc.setText(
                "指定环境只展示当前模块可用的 READY 浏览器环境：未归属环境或已归属当前模块的环境。"
            )
        else:
            self.select_desc.setText(
                "候选函数使用 candidates/ 下的 @env_candidates 纯函数，由宿主实时求值后分配就绪环境。"
            )

    def _declared_env_candidate_options(self) -> list[tuple[str, str]]:
        module_name = self._current_script_module_name()
        if not module_name:
            return []
        try:
            descriptor = get_module_service().get_runtime_descriptor_v2(module_name)
        except Exception as exc:
            logger.warning(f"[ATM] 加载模块环境候选函数失败: module={module_name} error={exc}")
            return []
        options: list[tuple[str, str]] = []
        for name, entry in sorted(descriptor.env_candidates.items()):
            normalized_name = str(name or "").strip()
            if not normalized_name:
                continue
            display_name = str(getattr(entry.meta, "label", "") or "").strip()
            options.append((normalized_name, display_name))
        return options

    def _declared_env_candidate_names(self) -> list[str]:
        return [name for name, _display_name in self._declared_env_candidate_options()]

    def _sync_candidates_options(self, preferred: str | None = None) -> None:
        current_data = self.candidates_combo.currentData()
        current = preferred if preferred is not None else current_data if isinstance(current_data, str) else ""
        candidate_options = self._declared_env_candidate_options()

        self.candidates_combo.blockSignals(True)
        self.candidates_combo.clear()
        if not candidate_options:
            self.candidates_combo.addItem("当前模块未声明候选函数", "")
            self.candidates_combo.setEnabled(False)
            self.candidates_combo.blockSignals(False)
            return

        self.candidates_combo.setEnabled(True)
        for candidates_name, display_name in candidate_options:
            label = f"{display_name} ({candidates_name})" if display_name and display_name != candidates_name else candidates_name
            self.candidates_combo.addItem(label, candidates_name)

        index = self.candidates_combo.findData(current)
        self.candidates_combo.setCurrentIndex(index if index >= 0 else 0)
        self.candidates_combo.blockSignals(False)

    def _set_candidates_value(self, candidates_name: str) -> None:
        index = self.candidates_combo.findData(candidates_name)
        self.candidates_combo.setCurrentIndex(index if index >= 0 else 0)

    def _create_yaml_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.yaml_editor = YamlCodeEditor()
        layout.addWidget(self.yaml_editor)
        return widget

    def _switch_mode(self, mode):
        if mode == "form":
            if not self._yaml_to_form(show_error=True):
                self.stack.setCurrentIndex(1)
                self._set_mode_button_active(self.form_btn, False)
                self._set_mode_button_active(self.yaml_btn, True)
                return
            self.stack.setCurrentIndex(0)
            self._set_mode_button_active(self.form_btn, True)
            self._set_mode_button_active(self.yaml_btn, False)
        else:
            self._form_to_yaml()
            self.stack.setCurrentIndex(1)
            self._set_mode_button_active(self.form_btn, False)
            self._set_mode_button_active(self.yaml_btn, True)

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
        self.execution_timeout_spin.setValue(s.execution.timeout if s.execution else self._default_execution_timeout())
        self._sync_object_assembly_form(
            {
                "object_bindings": dict(s.execution.object_bindings),
                "object_params": dict(s.execution.object_params),
            }
            if s.execution
            else None
        )
        self._sync_fixed_env_options(acquisition.env_id)
        self._sync_candidates_options(acquisition.candidates or "")
        self.wait_timeout_spin.setValue(acquisition.wait_timeout)
        if acquisition.env_id is not None:
            self._set_select_strategy_value("fixed")
        elif acquisition.candidates:
            self._set_select_strategy_value("candidates")
        else:
            self._set_select_strategy_value("fixed")
        self._set_fixed_env_value(acquisition.env_id)
        self._set_candidates_value(acquisition.candidates or "")
        self._candidate_params = dict(acquisition.candidate_params or {})
        self._sync_candidate_params_summary()
        self._on_select_strategy_changed(self.select_strategy_combo.currentIndex())

        self._on_resource_mode_changed(self.resource_mode_combo.currentIndex())


    def _build_run_profile_from_form(self) -> RunProfile:
        acquisition_mode = self.resource_mode_combo.currentData()
        provider = self.resource_provider_combo.currentText().strip() or "virtualbrowser"
        env_type = self._provider_to_env_type(provider)
        creation_params: dict = {}
        candidates_name = ""
        fixed_env_id: int | None = None

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
            select_strategy = self.select_strategy_combo.currentData()
            if select_strategy == "fixed":
                fixed_data = self.fixed_env_combo.currentData()
                if not isinstance(fixed_data, int):
                    raise ValueError("请选择可用环境")
                fixed_env_id = int(fixed_data)
                selected_env = self._fixed_env_by_id.get(fixed_env_id)
                provider = str(getattr(selected_env, "provider", "") or "") if selected_env else ""
                env_type = self._provider_to_env_type(provider)
            else:
                candidates_data = self.candidates_combo.currentData()
                candidates_name = candidates_data.strip() if isinstance(candidates_data, str) else ""
                if not candidates_name:
                    raise ValueError("请选择环境候选函数")
                declared_candidates = self._declared_env_candidate_names()
                if candidates_name:
                    if not declared_candidates:
                        raise ValueError("当前模块未声明 @env_candidates 候选函数")
                    if candidates_name not in declared_candidates:
                        raise ValueError(f"环境候选函数未声明: {candidates_name}")
                provider = ""
                env_type = EnvType.VIRTUAL_BROWSER

        resource = ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=acquisition_mode,
                provider=provider,
                env_type=env_type,
                env_id=fixed_env_id,
                candidates=candidates_name,
                candidate_params=(
                    dict(self._candidate_params)
                    if acquisition_mode == AcquisitionMode.SELECT and candidates_name
                    else {}
                ),
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
        object_assembly = self._current_object_assembly_values()
        execution = ExecutionContext(
            module=module_name,
            workflow=workflow_name,
            object_bindings=object_assembly["object_bindings"],
            object_params=object_assembly["object_params"],
            timeout=self.execution_timeout_spin.value(),
        )

        return RunProfile(
            resource=resource,
            execution=execution,
        )

    def _default_execution_timeout(self) -> int:
        try:
            return int(get_config_center().get("atm.default_execution_timeout_seconds"))
        except Exception as exc:
            logger.warning(f"读取默认任务执行超时失败，使用 600 秒: {exc}")
            return 600

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
                MessageDialog.warning(self, "YAML 无效", f"运行模板 YAML 保存失败：{exc}")
            return False

        self._run_profile = parsed_profile
        try:
            self._load_run_profile()
        except Exception as exc:
            if show_error:
                MessageDialog.warning(self, "YAML 无效", f"运行模板 YAML 保存失败：{exc}")
            return False

        return True

    def _on_validate(self):
        try:
            if self.stack.currentIndex() == 1:
                if not self._yaml_to_form(show_error=True):
                    return
            else:
                self._build_run_profile_from_form()
        except Exception as exc:
            MessageDialog.warning(self, "验证失败", f"运行模板配置无效：{exc}")
            return
        MessageDialog.information(self, "验证通过", "运行模板配置有效。")

    def _on_save(self):
        if self.stack.currentIndex() == 1:
            if not self._yaml_to_form(show_error=True):
                return
        else:
            self._run_profile = self._build_run_profile_from_form()

        self.accept()

    def get_run_profile(self) -> RunProfile:
        return self._run_profile
