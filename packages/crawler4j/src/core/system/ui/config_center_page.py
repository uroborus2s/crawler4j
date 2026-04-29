"""通用配置中心页面。"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from src.core.foundation.logging import logger
from src.core.system.config_center import ConfigItemSpec, ConfigValidationError, get_config_center
from src.ui.components.button import StyledButton
from src.ui.components.check_box import ToggleSwitch
from src.ui.components.combo_box import StyledComboBox
from src.ui.components.line_edit import StyledLineEdit
from src.ui.components.spin_box import StyledSpinBox


class ConfigCenterPage(QWidget):
    """Schema-driven host configuration center."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._config = get_config_center()
        self._domain_buttons: dict[str, StyledButton] = {}
        self._domain_pages: dict[str, QWidget] = {}
        self._field_widgets: dict[str, QWidget] = {}
        self._field_specs: dict[str, ConfigItemSpec] = {}
        self._current_domain = ""
        self._setup_ui()
        self._config.config_changed.connect(self._on_config_changed)

    def _setup_ui(self) -> None:
        self.setObjectName("configCenterPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            """
            #configCenterPage,
            QWidget#configCenterContent,
            QStackedWidget#configCenterStack,
            QWidget#configDomainViewport,
            QWidget#configDomainPage {
                background: #1a1a24;
            }
            QLabel {
                color: rgba(255, 255, 255, 0.82);
            }
            QLabel#pageTitle {
                color: white;
                font-size: 22px;
                font-weight: 700;
            }
            QLabel#domainHint, QLabel#fieldDescription, QLabel#effectLabel {
                color: rgba(255, 255, 255, 0.48);
                font-size: 12px;
            }
            QLabel#fieldLabel {
                color: white;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#configSectionTitle {
                color: rgba(255, 255, 255, 0.92);
                font-size: 15px;
                font-weight: 700;
            }
            QWidget#configSection, QWidget#configSectionBody, QWidget#configFieldRow {
                background: transparent;
                border: none;
            }
            QWidget#configRowDivider {
                background: rgba(255, 255, 255, 0.08);
                min-height: 1px;
                max-height: 1px;
            }
            QLabel#statusLabel {
                font-size: 12px;
            }
            QScrollArea#configDomainScroll {
                border: none;
                background: #1a1a24;
            }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._create_sidebar())

        content = QWidget()
        content.setObjectName("configCenterContent")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 20)
        content_layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        title_block = QWidget()
        title_layout = QVBoxLayout(title_block)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(4)
        title = QLabel("配置中心")
        title.setObjectName("pageTitle")
        title_layout.addWidget(title)
        hint = QLabel("统一管理宿主级系统配置，模块业务配置仍在模块详情中维护。")
        hint.setObjectName("domainHint")
        title_layout.addWidget(hint)
        header_row.addWidget(title_block)
        header_row.addStretch()
        self.reset_domain_btn = StyledButton("恢复本页默认", variant="secondary", min_height=34, min_width=128)
        self.reset_domain_btn.clicked.connect(self._on_reset_domain)
        header_row.addWidget(self.reset_domain_btn)
        content_layout.addLayout(header_row)

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("configCenterStack")
        self.content_stack.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        for domain in self._config.registry.list_domains():
            page = self._create_domain_page(domain.id)
            self._domain_pages[domain.id] = page
            self.content_stack.addWidget(page)
        content_layout.addWidget(self.content_stack, 1)

        self.restart_label = QLabel("部分配置只对新任务或重启后的运行时生效。")
        self.restart_label.setObjectName("effectLabel")
        self.restart_label.hide()
        content_layout.addWidget(self.restart_label)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.hide()
        content_layout.addWidget(self.status_label)

        layout.addWidget(content, 1)

        first_domain = self._config.registry.list_domains()[0]
        self._select_domain(first_domain.id)

    def _create_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(192)
        sidebar.setStyleSheet(
            """
            QWidget {
                background: rgba(30, 30, 40, 0.92);
                border-right: 1px solid rgba(255, 255, 255, 0.08);
            }
            """
        )
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 18, 12, 18)
        layout.setSpacing(8)

        for domain in self._config.registry.list_domains():
            button = StyledButton(domain.title, variant="ghost", min_height=38, horizontal_padding=12)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, domain_id=domain.id: self._select_domain(domain_id))
            self._domain_buttons[domain.id] = button
            layout.addWidget(button)

        layout.addStretch()
        return sidebar

    def _create_domain_page(self, domain_id: str) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("configDomainScroll")
        scroll.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.viewport().setObjectName("configDomainViewport")
        scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        page = QWidget()
        page.setObjectName("configDomainPage")
        page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(28)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        domain = next(item for item in self._config.registry.list_domains() if item.id == domain_id)
        sections = sorted(domain.sections, key=lambda section: (section.order, section.title))
        for section in sections:
            items = self._config.registry.list_items(domain=domain_id, section=section.id)
            if not items:
                continue
            section_widget = self._create_section_block(section.title)
            body = section_widget.findChild(QWidget, "configSectionBody")
            assert body is not None
            body_layout = body.layout()
            assert isinstance(body_layout, QVBoxLayout)
            for index, spec in enumerate(items):
                body_layout.addWidget(self._create_field_row(spec))
                if index < len(items) - 1:
                    body_layout.addWidget(self._create_row_divider())
            layout.addWidget(section_widget)

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _create_section_block(self, title: str) -> QWidget:
        section = QWidget()
        section.setObjectName("configSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("configSectionTitle")
        layout.addWidget(title_label)

        body = QWidget()
        body.setObjectName("configSectionBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        layout.addWidget(body)

        return section

    def _create_row_divider(self) -> QWidget:
        divider = QWidget()
        divider.setObjectName("configRowDivider")
        divider.setFixedHeight(1)
        return divider

    def _create_field_row(self, spec: ConfigItemSpec) -> QWidget:
        row = QWidget()
        row.setObjectName("configFieldRow")
        row.setMinimumHeight(56)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 14, 0, 14)
        row_layout.setSpacing(24)

        label_block = QWidget()
        label_block.setMinimumWidth(280)
        label_block.setMaximumWidth(360)
        label_layout = QVBoxLayout(label_block)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(4)
        label = QLabel(spec.label)
        label.setObjectName("fieldLabel")
        label_layout.addWidget(label)
        detail_parts = [part for part in (spec.description, self._effect_hint(spec)) if part]
        if detail_parts:
            desc = QLabel(" / ".join(detail_parts))
            desc.setObjectName("fieldDescription")
            desc.setWordWrap(True)
            label_layout.addWidget(desc)
        row_layout.addWidget(label_block, 1)

        editor_container = QWidget()
        editor_container.setMinimumWidth(300)
        editor_container.setMaximumWidth(440)
        editor_layout = QHBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(8)
        editor = self._create_editor(spec)
        if spec.value_type == "bool":
            editor_layout.addStretch()
            editor_layout.addWidget(editor, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        else:
            editor_layout.addWidget(editor)
        if spec.value_type == "path":
            browse_btn = StyledButton("浏览", variant="secondary", min_height=32, min_width=72, horizontal_padding=10)
            browse_btn.clicked.connect(lambda _checked=False, key=spec.key: self._browse_path(key))
            editor_layout.addWidget(browse_btn)
        row_layout.addWidget(editor_container)

        return row

    def _create_editor(self, spec: ConfigItemSpec) -> QWidget:
        value = self._config.get(spec.key)

        if spec.value_type == "bool":
            widget = ToggleSwitch()
            widget.setChecked(bool(value))
            widget.toggled.connect(lambda checked, key=spec.key: self._save_value(key, checked))
        elif spec.value_type == "int":
            widget = StyledSpinBox()
            widget.setRange(
                int(spec.min_value if spec.min_value is not None else -(2**31)),
                int(spec.max_value if spec.max_value is not None else 2**31 - 1),
            )
            if spec.unit:
                widget.setSuffix(f" {spec.unit}")
            widget.setValue(int(value))
            widget.valueChanged.connect(lambda new_value, key=spec.key: self._save_value(key, new_value))
        elif spec.value_type == "enum":
            widget = StyledComboBox()
            for choice in spec.choices:
                widget.addItem(choice.label, choice.value)
            self._set_combo_value(widget, value)
            widget.currentIndexChanged.connect(
                lambda _index, key=spec.key, combo=widget: self._save_value(key, combo.currentData())
            )
        else:
            widget = StyledLineEdit()
            widget.setText(str(value or ""))
            if spec.value_type == "secret":
                widget.setEchoMode(StyledLineEdit.EchoMode.Password)
            if spec.description:
                widget.setPlaceholderText(spec.description)
            widget.editingFinished.connect(lambda key=spec.key, edit=widget: self._save_value(key, edit.text()))

        if spec.value_type != "bool":
            widget.setMinimumWidth(260)
        self._field_widgets[spec.key] = widget
        self._field_specs[spec.key] = spec
        return widget

    def _select_domain(self, domain_id: str) -> None:
        self._current_domain = domain_id
        page = self._domain_pages[domain_id]
        self.content_stack.setCurrentWidget(page)
        for key, button in self._domain_buttons.items():
            button.set_variant("primary" if key == domain_id else "ghost")
        self.restart_label.hide()
        self.status_label.hide()

    def _save_value(self, key: str, value: Any) -> None:
        spec = self._field_specs[key]
        try:
            self._config.set(key, value)
        except ConfigValidationError as exc:
            self._show_status(str(exc), success=False)
            self._set_widget_value(key, self._config.get(key))
            return
        except Exception as exc:
            logger.exception(f"保存配置失败: key={key}")
            self._show_status(f"保存失败：{exc}", success=False)
            self._set_widget_value(key, self._config.get(key))
            return

        if spec.effect != "immediate":
            self.restart_label.show()
        self._show_status(f"已保存：{spec.label}", success=True)

    def _browse_path(self, key: str) -> None:
        widget = self._field_widgets[key]
        if not isinstance(widget, StyledLineEdit):
            return
        selected, _filter = QFileDialog.getOpenFileName(self, "选择程序", widget.text() or "")
        if not selected:
            return
        widget.setText(selected)
        self._save_value(key, selected)

    def _on_reset_domain(self) -> None:
        if not self._current_domain:
            return
        count = self._config.reset_domain(self._current_domain)
        for value in self._config.list_values(domain=self._current_domain):
            self._set_widget_value(value.spec.key, value.value)
        self.restart_label.show()
        self._show_status(f"已恢复本页默认配置（{count} 项）", success=True)

    def _on_config_changed(self, key: str, value: Any, effect: str) -> None:
        if key in self._field_widgets:
            self._set_widget_value(key, value)
        if effect != "immediate":
            self.restart_label.show()

    def _set_widget_value(self, key: str, value: Any) -> None:
        widget = self._field_widgets.get(key)
        if widget is None:
            return

        widget.blockSignals(True)
        try:
            if isinstance(widget, ToggleSwitch):
                widget.setChecked(bool(value))
            elif isinstance(widget, StyledSpinBox):
                widget.setValue(int(value))
            elif isinstance(widget, StyledComboBox):
                self._set_combo_value(widget, value)
            elif isinstance(widget, StyledLineEdit):
                widget.setText(str(value or ""))
        finally:
            widget.blockSignals(False)

    def _set_combo_value(self, combo: StyledComboBox, value: Any) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

    def _show_status(self, message: str, *, success: bool) -> None:
        self.status_label.setText(message)
        color = "#34d399" if success else "#f87171"
        self.status_label.setStyleSheet(f"font-size: 12px; color: {color};")
        self.status_label.show()

    @staticmethod
    def _effect_hint(spec: ConfigItemSpec) -> str:
        if spec.effect == "restart_required":
            return "重启后生效"
        if spec.effect == "new_tasks_only":
            return "仅对新任务生效"
        return ""
