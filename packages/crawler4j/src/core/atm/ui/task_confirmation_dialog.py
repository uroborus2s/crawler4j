"""Signal-driven confirmation dialog for waiting ATM tasks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from src.core.atm.models import Task


@dataclass(frozen=True)
class ConfirmationField:
    label: str
    value: str


@dataclass(frozen=True)
class ConfirmationSpec:
    title: str
    description: str
    fields: list[ConfirmationField]
    confirm_text: str
    reject_text: str


def build_confirmation_spec(task: Task) -> ConfirmationSpec:
    signal = task.signal or {}
    payload = signal.get("payload") if isinstance(signal, dict) else {}
    if not isinstance(payload, dict):
        payload = {}

    confirmation = payload.get("confirmation")
    if not isinstance(confirmation, dict):
        confirmation = {}

    title = str(confirmation.get("title") or task.message or "等待人工确认")
    description = str(
        confirmation.get("description")
        or signal.get("message")
        or task.message
        or "请确认该任务的后续处理结果。"
    )
    confirm_text = str(confirmation.get("confirm_text") or "确认成功")
    reject_text = str(confirmation.get("reject_text") or "确认失败")

    fields: list[ConfirmationField] = []
    raw_fields = confirmation.get("fields")
    if isinstance(raw_fields, list):
        for item in raw_fields:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("key") or "").strip()
            if not label:
                continue
            fields.append(ConfirmationField(label=label, value=_stringify_value(item.get("value"))))

    if not fields:
        for key, value in payload.items():
            if key == "confirmation":
                continue
            fields.append(ConfirmationField(label=str(key), value=_stringify_value(value)))

    return ConfirmationSpec(
        title=title,
        description=description,
        fields=fields,
        confirm_text=confirm_text,
        reject_text=reject_text,
    )


def _stringify_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return str(value)
    return json.dumps(value, ensure_ascii=False, indent=2)


class TaskConfirmationDialog(QDialog):
    """展示任务信号中的结构化确认内容。"""

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self.spec = build_confirmation_spec(task)
        self.confirmed = False

        self.setWindowTitle(self.spec.title)
        self.resize(680, 520)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background-color: #1a1b26;
                color: #c0caf5;
            }
            QLabel {
                color: #c0caf5;
            }
            QTextEdit, QTableWidget {
                background-color: rgba(30, 30, 40, 0.88);
                color: #e5e7eb;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: rgba(45, 45, 55, 0.95);
                color: rgba(255, 255, 255, 0.8);
                padding: 8px;
                border: none;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        self.title_label = QLabel(self.spec.title)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        layout.addWidget(self.title_label)

        self.description_label = QLabel(self.spec.description)
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("color: rgba(255,255,255,0.78);")
        layout.addWidget(self.description_label)

        self.details_table = QTableWidget(len(self.spec.fields), 2, self)
        self.details_table.setHorizontalHeaderLabels(["字段", "内容"])
        self.details_table.verticalHeader().setVisible(False)
        self.details_table.horizontalHeader().setStretchLastSection(True)
        self.details_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.details_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        for row, field in enumerate(self.spec.fields):
            self.details_table.setItem(row, 0, QTableWidgetItem(field.label))
            self.details_table.setItem(row, 1, QTableWidgetItem(field.value))
        layout.addWidget(self.details_table, stretch=1)

        note_label = QLabel("确认备注")
        note_label.setStyleSheet("font-weight: bold; color: white;")
        layout.addWidget(note_label)

        self.message_edit = QTextEdit(self)
        self.message_edit.setPlaceholderText("可选：填写本次人工确认说明")
        self.message_edit.setMinimumHeight(110)
        layout.addWidget(self.message_edit)

        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel_btn = QPushButton("稍后处理")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        self.reject_btn = QPushButton(self.spec.reject_text)
        self.reject_btn.setStyleSheet("background: rgba(248, 113, 113, 0.85); color: white; padding: 8px 14px;")
        self.reject_btn.clicked.connect(self._reject_and_accept)
        buttons.addWidget(self.reject_btn)

        self.confirm_btn = QPushButton(self.spec.confirm_text)
        self.confirm_btn.setStyleSheet("background: rgba(74, 222, 128, 0.85); color: black; padding: 8px 14px;")
        self.confirm_btn.clicked.connect(self._confirm_and_accept)
        buttons.addWidget(self.confirm_btn)

        layout.addLayout(buttons)

    def _confirm_and_accept(self) -> None:
        self.confirmed = True
        self.accept()

    def _reject_and_accept(self) -> None:
        self.confirmed = False
        self.accept()

    def get_message(self) -> str:
        return self.message_edit.toPlainText().strip()
