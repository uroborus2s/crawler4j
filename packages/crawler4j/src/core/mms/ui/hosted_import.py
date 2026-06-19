"""Hosted UI batch import helpers and dialog."""

from __future__ import annotations

import csv
import json
import re
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from PyQt6.QtWidgets import (
    QFileDialog,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.ui.components.button import StyledButton
from src.ui.components.dialog_window import configure_titled_dialog
from src.ui.components.line_edit import StyledLineEdit
from src.ui.components.message_dialog import MessageDialog

SUPPORTED_IMPORT_EXTENSIONS = {".csv", ".xlsx"}
DEFAULT_MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_ROWS = 5000
SENSITIVE_KEY_PARTS = (
    "token",
    "cookie",
    "password",
    "secret",
    "authorization",
    "credential",
    "passwd",
)


@dataclass(frozen=True, slots=True)
class HostedImportLimits:
    """Host-side limits for a batch import payload."""

    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES
    max_rows: int = DEFAULT_MAX_ROWS

    @classmethod
    def from_schema(cls, raw: dict[str, Any] | None) -> "HostedImportLimits":
        if not isinstance(raw, dict):
            return cls()
        return cls(
            max_file_size_bytes=_positive_int(raw.get("max_file_size_bytes"), DEFAULT_MAX_FILE_SIZE_BYTES),
            max_rows=_positive_int(raw.get("max_rows"), DEFAULT_MAX_ROWS),
        )


def parse_import_file(
    path: str | Path,
    *,
    target_type: str,
    limits: HostedImportLimits | None = None,
    business_key_field: str = "",
    field_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Read an xlsx/csv file on the host and return the module-safe import payload."""

    file_path = Path(path)
    normalized_limits = limits or HostedImportLimits()
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_IMPORT_EXTENSIONS:
        raise ValueError("只支持 .xlsx/.csv 文件")
    if not file_path.exists() or not file_path.is_file():
        raise ValueError(f"导入文件不存在: {file_path}")
    file_size = file_path.stat().st_size
    if file_size > normalized_limits.max_file_size_bytes:
        raise ValueError("导入文件超过大小限制")

    if suffix == ".csv":
        parsed_rows = _parse_csv_text(file_path.read_text(encoding="utf-8-sig"))
    else:
        parsed_rows = _parse_xlsx_first_sheet(file_path)

    return _build_import_payload(
        parsed_rows,
        source_type="file",
        source_name=file_path.name,
        target_type=target_type,
        limits=normalized_limits,
        business_key_field=business_key_field,
        field_mapping=field_mapping,
    )


def parse_clipboard_import_text(
    text: str,
    *,
    target_type: str,
    limits: HostedImportLimits | None = None,
    business_key_field: str = "",
    field_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Parse tabular clipboard text as CSV/TSV rows."""

    return _build_import_payload(
        _parse_csv_text(text),
        source_type="clipboard",
        source_name="clipboard",
        target_type=target_type,
        limits=limits or HostedImportLimits(),
        business_key_field=business_key_field,
        field_mapping=field_mapping,
    )


def parse_manual_json_import(
    text: str,
    *,
    target_type: str,
    limits: HostedImportLimits | None = None,
    business_key_field: str = "",
    field_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Parse manually entered JSON rows."""

    try:
        raw_rows = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"手工 JSON 格式错误: {exc}") from exc
    if not isinstance(raw_rows, list):
        raise ValueError("手工 JSON 必须是对象数组")

    parsed_rows: list[tuple[int, dict[str, Any]]] = []
    for index, raw_row in enumerate(raw_rows, start=1):
        if not isinstance(raw_row, dict):
            raise ValueError(f"第 {index} 行必须是对象")
        parsed_rows.append((index, {str(key): _stringify_cell(value) for key, value in raw_row.items()}))

    return _build_import_payload(
        parsed_rows,
        source_type="manual",
        source_name="manual",
        target_type=target_type,
        limits=limits or HostedImportLimits(),
        business_key_field=business_key_field,
        field_mapping=field_mapping,
    )


def redact_import_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy with sensitive fields masked for logs or UI diagnostics."""

    return _redact_value(deepcopy(payload), parent_key="")


class HostedImportDialog(QDialog):
    """Host-owned import dialog that turns local input into module-safe rows."""

    def __init__(self, action: dict[str, Any], *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._action = dict(action)
        self._payload: dict[str, Any] | None = None
        self._selected_file_path: Path | None = None

        self.setWindowTitle(str(self._action.get("title") or self._action.get("label") or "批量导入"))
        self.setModal(True)
        self.setMinimumWidth(720)
        configure_titled_dialog(self)
        self.setStyleSheet(self._build_stylesheet())
        self._setup_ui()

    @staticmethod
    def _build_stylesheet() -> str:
        return """
            QDialog {
                background-color: #1e1e28;
            }
            QLabel {
                color: rgba(255, 255, 255, 0.78);
                background: transparent;
                font-size: 13px;
            }
            QLabel#hostedImportTitle {
                color: #f7f7fb;
                font-size: 18px;
                font-weight: 800;
            }
            QLabel#hostedImportHint {
                color: rgba(255, 255, 255, 0.58);
                font-size: 12px;
            }
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                top: -1px;
            }
            QTabBar::tab {
                color: rgba(255, 255, 255, 0.72);
                background: rgba(255, 255, 255, 0.06);
                padding: 8px 14px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                color: #ffffff;
                background: rgba(99, 102, 241, 0.8);
            }
            QPlainTextEdit {
                background-color: rgba(255, 255, 255, 0.07);
                color: rgba(255, 255, 255, 0.86);
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 8px;
                padding: 10px;
                selection-background-color: rgba(99, 102, 241, 0.55);
                font-size: 12px;
            }
        """

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel(self.windowTitle())
        title.setObjectName("hostedImportTitle")
        root.addWidget(title)

        hint = QLabel(
            f"目标类型: {self._target_type() or '-'} · "
            f"最大 {self._limits().max_rows} 行 · "
            f"最大文件 {self._limits().max_file_size_bytes // 1024} KB"
        )
        hint.setObjectName("hostedImportHint")
        root.addWidget(hint)

        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        source_types = {
            str(item or "").strip().lower()
            for item in list(self._action.get("source_types") or ["file", "clipboard"])
        }
        if "file" in source_types:
            self._tabs.addTab(self._build_file_tab(), "文件")
        if "clipboard" in source_types:
            self._tabs.addTab(self._build_clipboard_tab(), "剪贴板")
        if "manual" in source_types:
            self._tabs.addTab(self._build_manual_tab(), "手工 JSON")
        if self._tabs.count() == 0:
            self._tabs.addTab(self._build_clipboard_tab(), "剪贴板")

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_button = StyledButton("取消", variant="secondary", min_height=40, min_width=96)
        cancel_button.clicked.connect(self.reject)
        button_row.addWidget(cancel_button)
        import_button = StyledButton("开始导入", variant="success", min_height=40, min_width=112)
        import_button.clicked.connect(self._accept_import)
        button_row.addWidget(import_button)
        root.addLayout(button_row)

    def _build_file_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self._file_path_edit = StyledLineEdit()
        self._file_path_edit.setReadOnly(True)
        choose_button = StyledButton("选择文件", variant="secondary", min_height=34, min_width=92)
        choose_button.clicked.connect(self._choose_file)
        file_row = QHBoxLayout()
        file_row.setSpacing(8)
        file_row.addWidget(self._file_path_edit, 1)
        file_row.addWidget(choose_button)
        form.addRow("文件：", _layout_widget(file_row))
        layout.addLayout(form)
        layout.addStretch()
        return tab

    def _build_clipboard_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        self._clipboard_text = QPlainTextEdit()
        self._clipboard_text.setPlaceholderText("粘贴带表头的 CSV/TSV 数据")
        self._clipboard_text.setMinimumHeight(260)
        layout.addWidget(self._clipboard_text)
        return tab

    def _build_manual_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        self._manual_json_text = QPlainTextEdit()
        self._manual_json_text.setPlaceholderText('[{"phone": "13800000000", "name": "Alice"}]')
        self._manual_json_text.setMinimumHeight(260)
        layout.addWidget(self._manual_json_text)
        return tab

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择导入文件",
            "",
            "Import files (*.xlsx *.csv)",
        )
        if not path:
            return
        self._selected_file_path = Path(path)
        self._file_path_edit.setText(path)

    def _accept_import(self) -> None:
        try:
            self._payload = self._parse_current_tab()
        except Exception as exc:
            MessageDialog.warning(self, "导入数据无效", str(exc))
            return
        self.accept()

    def _parse_current_tab(self) -> dict[str, Any]:
        tab_label = self._tabs.tabText(self._tabs.currentIndex())
        if tab_label == "文件":
            if self._selected_file_path is None:
                raise ValueError("请选择 .xlsx 或 .csv 文件")
            return parse_import_file(
                self._selected_file_path,
                target_type=self._target_type(),
                limits=self._limits(),
                business_key_field=self._business_key_field(),
                field_mapping=self._field_mapping(),
            )
        if tab_label == "手工 JSON":
            return parse_manual_json_import(
                self._manual_json_text.toPlainText(),
                target_type=self._target_type(),
                limits=self._limits(),
                business_key_field=self._business_key_field(),
                field_mapping=self._field_mapping(),
            )
        return parse_clipboard_import_text(
            self._clipboard_text.toPlainText(),
            target_type=self._target_type(),
            limits=self._limits(),
            business_key_field=self._business_key_field(),
            field_mapping=self._field_mapping(),
        )

    def import_payload(self) -> dict[str, Any] | None:
        return deepcopy(self._payload)

    def _target_type(self) -> str:
        return str(self._action.get("target_type") or "").strip()

    def _business_key_field(self) -> str:
        return str(self._action.get("business_key_field") or "").strip()

    def _field_mapping(self) -> dict[str, str]:
        raw = self._action.get("field_mapping")
        if not isinstance(raw, dict):
            return {}
        return {str(key): str(value) for key, value in raw.items() if str(key) and str(value)}

    def _limits(self) -> HostedImportLimits:
        return HostedImportLimits.from_schema(self._action.get("limits"))


def _positive_int(raw: Any, default: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, value)


def _layout_widget(layout: QHBoxLayout) -> QWidget:
    widget = QWidget()
    widget.setLayout(layout)
    return widget


def _build_import_payload(
    parsed_rows: list[tuple[int, dict[str, Any]]],
    *,
    source_type: str,
    source_name: str,
    target_type: str,
    limits: HostedImportLimits,
    business_key_field: str = "",
    field_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    mapping = field_mapping or {}
    normalized_business_key_field = str(business_key_field or "").strip()
    for source_row_no, raw_payload in parsed_rows:
        payload = _apply_field_mapping(raw_payload, mapping)
        business_key = _business_key(payload, raw_payload, normalized_business_key_field)
        rows.append(
            {
                "source_row_no": source_row_no,
                "business_key": business_key,
                "payload": payload,
                "raw_payload": dict(raw_payload),
            }
        )
        if len(rows) > limits.max_rows:
            raise ValueError(f"导入数据超过最大行数: {limits.max_rows}")
    return {
        "source_type": source_type,
        "source_name": source_name,
        "target_type": str(target_type or "").strip(),
        "rows": rows,
    }


def _apply_field_mapping(raw_payload: dict[str, Any], field_mapping: dict[str, str]) -> dict[str, Any]:
    if not field_mapping:
        return dict(raw_payload)
    payload: dict[str, Any] = {}
    for source_key, value in raw_payload.items():
        target_key = str(field_mapping.get(source_key) or source_key).strip()
        if target_key:
            payload[target_key] = value
    return payload


def _business_key(payload: dict[str, Any], raw_payload: dict[str, Any], field_name: str) -> str:
    if not field_name:
        return ""
    value = payload.get(field_name)
    if value in (None, ""):
        value = raw_payload.get(field_name)
    return "" if value is None else str(value)


def _parse_csv_text(text: str) -> list[tuple[int, dict[str, str]]]:
    normalized_text = str(text or "")
    if not normalized_text.strip():
        raise ValueError("导入数据为空")
    sample = normalized_text[:4096]
    dialect = csv.excel_tab if "\t" in sample else csv.excel
    if "\t" not in sample:
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
    reader = csv.reader(normalized_text.splitlines(), dialect)
    all_rows = list(reader)
    if not all_rows:
        raise ValueError("导入数据为空")
    headers = [_normalize_header(value) for value in all_rows[0]]
    _validate_headers(headers)

    parsed: list[tuple[int, dict[str, str]]] = []
    for row_number, row in enumerate(all_rows[1:], start=2):
        if not any(str(value or "").strip() for value in row):
            continue
        padded = list(row) + [""] * max(0, len(headers) - len(row))
        raw_payload = {
            header: str(padded[index]).strip()
            for index, header in enumerate(headers)
            if header
        }
        parsed.append((row_number, raw_payload))
    return parsed


def _validate_headers(headers: list[str]) -> None:
    if not any(headers):
        raise ValueError("导入数据缺少表头")
    seen: set[str] = set()
    for header in headers:
        if not header:
            raise ValueError("导入数据表头不能为空")
        if header in seen:
            raise ValueError(f"导入数据表头重复: {header}")
        seen.add(header)


def _normalize_header(value: Any) -> str:
    return str(value or "").strip().lstrip("\ufeff")


def _parse_xlsx_first_sheet(path: Path) -> list[tuple[int, dict[str, str]]]:
    try:
        with zipfile.ZipFile(path) as archive:
            sheet_path = _first_xlsx_sheet_path(archive)
            shared_strings = _xlsx_shared_strings(archive)
            sheet_xml = archive.read(sheet_path)
    except zipfile.BadZipFile as exc:
        raise ValueError("xlsx 文件格式无效") from exc
    except KeyError as exc:
        raise ValueError(f"xlsx 文件缺少必要内容: {exc}") from exc

    root = ElementTree.fromstring(sheet_xml)
    sheet_rows: list[tuple[int, dict[int, str]]] = []
    for row in root.findall(".//{*}sheetData/{*}row"):
        row_number = _positive_int(row.attrib.get("r"), len(sheet_rows) + 1)
        cells: dict[int, str] = {}
        for cell in row.findall("{*}c"):
            cell_ref = str(cell.attrib.get("r") or "")
            column_index = _xlsx_column_index(cell_ref)
            if column_index < 0:
                continue
            cells[column_index] = _xlsx_cell_value(cell, shared_strings)
        if any(value.strip() for value in cells.values()):
            sheet_rows.append((row_number, cells))
    if not sheet_rows:
        raise ValueError("导入数据为空")

    header_row_no, header_cells = sheet_rows[0]
    del header_row_no
    max_column = max(header_cells) if header_cells else -1
    headers = [_normalize_header(header_cells.get(index, "")) for index in range(max_column + 1)]
    _validate_headers(headers)

    parsed: list[tuple[int, dict[str, str]]] = []
    for row_number, cells in sheet_rows[1:]:
        if not any(value.strip() for value in cells.values()):
            continue
        raw_payload = {
            header: str(cells.get(index, "")).strip()
            for index, header in enumerate(headers)
            if header
        }
        parsed.append((row_number, raw_payload))
    return parsed


def _first_xlsx_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    first_sheet = workbook.find(".//{*}sheets/{*}sheet")
    if first_sheet is None:
        raise ValueError("xlsx 文件不包含工作表")
    relationship_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    if not relationship_id:
        raise ValueError("xlsx 工作表关系无效")

    relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for relationship in relationships.findall("{*}Relationship"):
        if relationship.attrib.get("Id") != relationship_id:
            continue
        target = str(relationship.attrib.get("Target") or "").lstrip("/")
        return target if target.startswith("xl/") else f"xl/{target}"
    raise ValueError("xlsx 工作表关系缺失")


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values: list[str] = []
    for item in root.findall("{*}si"):
        texts = [node.text or "" for node in item.findall(".//{*}t")]
        values.append("".join(texts))
    return values


def _xlsx_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = str(cell.attrib.get("t") or "").strip()
    if cell_type == "inlineStr":
        texts = [node.text or "" for node in cell.findall(".//{*}t")]
        return "".join(texts)
    value = cell.find("{*}v")
    raw = "" if value is None or value.text is None else str(value.text)
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return ""
    if cell_type == "b":
        return "true" if raw == "1" else "false"
    return raw


def _xlsx_column_index(cell_ref: str) -> int:
    match = re.match(r"([A-Za-z]+)", cell_ref)
    if not match:
        return -1
    index = 0
    for char in match.group(1).upper():
        index = index * 26 + ord(char) - ord("A") + 1
    return index - 1


def _stringify_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _redact_value(value: Any, *, parent_key: str) -> Any:
    if _is_sensitive_key(parent_key):
        return "***"
    if isinstance(value, dict):
        return {
            key: _redact_value(item, parent_key=str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item, parent_key=parent_key) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = str(key or "").lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)
