"""QScintilla-backed YAML editor widget."""

from __future__ import annotations

import math
import re

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF
from PyQt6.Qsci import QsciLexerCustom, QsciScintilla

_MONO_FONT_CANDIDATES = (
    "SF Mono",
    "Menlo",
    "Consolas",
    "Cascadia Mono",
    "Monaco",
    "JetBrains Mono",
    "Courier New",
)
_EDITOR_FONT_POINT_SIZE = 15
_MIN_EXTRA_LINE_SPACING = 3
_EXTRA_LINE_SPACING_RATIO = 0.18


def _available_fixed_monospace_families() -> list[str]:
    families = set(QFontDatabase.families())
    return [
        family
        for family in _MONO_FONT_CANDIDATES
        if family in families and QFontDatabase.isFixedPitch(family)
    ]


def _build_monospace_font(point_size: int = _EDITOR_FONT_POINT_SIZE) -> QFont:
    preferred_families = _available_fixed_monospace_families()
    font = (
        QFont(preferred_families[0])
        if preferred_families
        else QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    )
    if preferred_families and hasattr(font, "setFamilies"):
        font.setFamilies(preferred_families)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    font.setPointSize(point_size)
    return font


def _recommended_extra_line_spacing(font: QFont) -> int:
    return max(
        math.ceil(QFontMetricsF(font).lineSpacing() * _EXTRA_LINE_SPACING_RATIO),
        _MIN_EXTRA_LINE_SPACING,
    )


class YamlDisplayLexer(QsciLexerCustom):
    """Lightweight YAML-oriented syntax colors without QsciLexerYAML indent bugs."""

    DEFAULT = 0
    KEY = 1
    STRING = 2
    NUMBER = 3
    LITERAL = 4
    COMMENT = 5
    OPERATOR = 6

    _NUMBER_PATTERN = re.compile(r"[-+]?(?:0|[1-9]\d*)(?:\.\d+)?")
    _LITERAL_VALUES = {"true", "false", "null", "~"}

    def __init__(self, parent: QsciScintilla | None = None):
        super().__init__(parent)
        font = parent.font() if parent is not None else _build_monospace_font()
        self.setDefaultFont(font)
        self.setDefaultPaper(QColor("#0b1020"))
        self.setDefaultColor(QColor("#e5e7eb"))

        style_colors = {
            self.DEFAULT: QColor("#e5e7eb"),
            self.KEY: QColor("#ffca70"),
            self.STRING: QColor("#88a96f"),
            self.NUMBER: QColor("#8fb4e8"),
            self.LITERAL: QColor("#d8924a"),
            self.COMMENT: QColor("#94a3b8"),
            self.OPERATOR: QColor("#d1d5db"),
        }
        for style, color in style_colors.items():
            self.setColor(color, style)
            self.setPaper(QColor("#0b1020"), style)
            self.setFont(font, style)

    def language(self) -> str:
        return "YAML"

    def description(self, style: int) -> str:
        descriptions = {
            self.DEFAULT: "Default",
            self.KEY: "Key",
            self.STRING: "String",
            self.NUMBER: "Number",
            self.LITERAL: "Literal",
            self.COMMENT: "Comment",
            self.OPERATOR: "Operator",
        }
        return descriptions.get(style, "")

    @classmethod
    def classify_scalar_style(cls, value: str) -> int:
        stripped = value.strip()
        if not stripped:
            return cls.DEFAULT
        if stripped.startswith("#"):
            return cls.COMMENT
        if stripped[:1] in {'"', "'"} and stripped[-1:] == stripped[:1]:
            return cls.STRING
        if stripped.lower() in cls._LITERAL_VALUES:
            return cls.LITERAL
        if cls._NUMBER_PATTERN.fullmatch(stripped):
            return cls.NUMBER
        return cls.STRING

    def styleText(self, start: int, end: int) -> None:
        del start, end
        editor = self.editor()
        if editor is None:
            return

        self.startStyling(0)
        for line in editor.text().splitlines(keepends=True):
            self._style_line(line)

    def _style_line(self, line: str) -> None:
        body = line[:-1] if line.endswith("\n") else line
        newline = "\n" if line.endswith("\n") else ""
        indent_len = len(body) - len(body.lstrip(" "))
        indent = body[:indent_len]
        stripped = body[indent_len:]

        self._apply(indent, self.DEFAULT)
        if not stripped:
            self._apply(newline, self.DEFAULT)
            return

        if stripped.startswith("#"):
            self._apply(stripped, self.COMMENT)
            self._apply(newline, self.DEFAULT)
            return

        if stripped.startswith("- "):
            self._apply("-", self.OPERATOR)
            self._apply(" ", self.DEFAULT)
            self._apply_scalar(stripped[2:])
            self._apply(newline, self.DEFAULT)
            return

        separator_index = stripped.find(":")
        if separator_index == -1:
            self._apply_scalar(stripped)
            self._apply(newline, self.DEFAULT)
            return

        key = stripped[:separator_index]
        tail = stripped[separator_index + 1 :]
        self._apply(key, self.KEY)
        self._apply(":", self.OPERATOR)
        leading_spaces = tail[: len(tail) - len(tail.lstrip(" "))]
        if leading_spaces:
            self._apply(leading_spaces, self.DEFAULT)
        self._apply_scalar(tail[len(leading_spaces) :])
        self._apply(newline, self.DEFAULT)

    def _apply_scalar(self, value: str) -> None:
        if not value:
            return
        self._apply(value, self.classify_scalar_style(value))

    def _apply(self, segment: str, style: int) -> None:
        if segment:
            self.setStyling(len(segment.encode("utf-8")), style)


class YamlCodeEditor(QsciScintilla):
    """Code editor tuned for module YAML configuration."""

    _ERROR_INDICATOR = 8
    _ERROR_MARKER = 1
    _EXTRA_ASCENT_MESSAGE = 2525
    _GET_EXTRA_ASCENT_MESSAGE = 2526
    _EXTRA_DESCENT_MESSAGE = 2527
    _GET_EXTRA_DESCENT_MESSAGE = 2528
    _SEQUENCE_INDENT_WIDTH = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._configure_editor()
        self._configure_lexer()
        self._configure_validation_markers()
        self.textChanged.connect(self.clear_validation_error)

    def _configure_editor(self) -> None:
        font = _build_monospace_font()
        self.setFont(font)
        self.setMarginsFont(font)
        self._set_line_spacing(_recommended_extra_line_spacing(font))
        self.setUtf8(True)

        self.setAutoIndent(True)
        self.setIndentationsUseTabs(False)
        self.setTabWidth(2)
        self.setIndentationGuides(False)
        self.setBackspaceUnindents(True)
        self.setTabIndents(True)

        self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        self.setCaretLineVisible(True)
        self.setCaretLineBackgroundColor(QColor("#182033"))
        self.setCaretForegroundColor(QColor("#e5e7eb"))
        self.setSelectionBackgroundColor(QColor("#334155"))
        self.setSelectionForegroundColor(QColor("#f8fafc"))

        self.setWrapMode(QsciScintilla.WrapMode.WrapNone)
        self.setScrollWidthTracking(True)
        self.setEolMode(QsciScintilla.EolMode.EolUnix)
        self.setEolVisibility(False)
        self.setWhitespaceVisibility(QsciScintilla.WhitespaceVisibility.WsInvisible)
        self.setEdgeMode(QsciScintilla.EdgeMode.EdgeNone)

        self.setFolding(QsciScintilla.FoldStyle.NoFoldStyle)
        self.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        self.setMarginLineNumbers(0, True)
        self.setMarginWidth(0, "0000")
        self.setMarginsBackgroundColor(QColor("#111827"))
        self.setMarginsForegroundColor(QColor("#94a3b8"))

        self.setColor(QColor("#e5e7eb"))
        self.setPaper(QColor("#0b1020"))
        self.setMinimumHeight(120)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _configure_lexer(self) -> None:
        # QsciLexerYAML visually outdents block sequence items even when the
        # underlying text has the correct leading spaces, so use a narrow custom lexer.
        self.setLexer(YamlDisplayLexer(self))

    def _set_line_spacing(self, pixels: int) -> None:
        if hasattr(self, "setExtraAscent"):
            self.setExtraAscent(pixels)
        else:
            self.SendScintilla(self._EXTRA_ASCENT_MESSAGE, pixels)

        if hasattr(self, "setExtraDescent"):
            self.setExtraDescent(pixels)
        else:
            self.SendScintilla(self._EXTRA_DESCENT_MESSAGE, pixels)

    def _configure_validation_markers(self) -> None:
        self.indicatorDefine(
            QsciScintilla.IndicatorStyle.SquiggleIndicator,
            self._ERROR_INDICATOR,
        )
        self.setIndicatorForegroundColor(QColor("#ef4444"), self._ERROR_INDICATOR)
        self.markerDefine(QsciScintilla.MarkerSymbol.RightArrow, self._ERROR_MARKER)
        self.setMarkerBackgroundColor(QColor("#ef4444"), self._ERROR_MARKER)

    def toPlainText(self) -> str:
        return self.text()

    def setPlainText(self, text: str) -> None:
        self.setText(self.normalize_yaml_layout(text))
        self.clear_validation_error()

    @classmethod
    def normalize_yaml_layout(cls, text: str) -> str:
        lines = str(text or "").splitlines()
        if not lines:
            return str(text or "")

        normalized: list[str] = []
        active_sequence_parent_indent: int | None = None
        active_item_original_indent: int | None = None
        active_item_shift: int = 0
        active_item_starts_mapping = False
        for line in lines:
            stripped = line.lstrip(" ")
            indent = len(line) - len(stripped)

            if stripped.startswith("- "):
                target_indent: int | None = None
                if (
                    active_sequence_parent_indent is not None
                    and indent < active_sequence_parent_indent + cls._SEQUENCE_INDENT_WIDTH
                ):
                    target_indent = active_sequence_parent_indent + cls._SEQUENCE_INDENT_WIDTH
                elif normalized:
                    previous = cls._previous_significant_line(normalized)
                    if previous is not None:
                        previous_stripped = previous.strip()
                        previous_indent = len(previous) - len(previous.lstrip(" "))
                        if previous_stripped.endswith(":") and indent < previous_indent + cls._SEQUENCE_INDENT_WIDTH:
                            active_sequence_parent_indent = previous_indent
                            target_indent = previous_indent + cls._SEQUENCE_INDENT_WIDTH
                if target_indent is not None:
                    active_item_original_indent = indent
                    active_item_shift = target_indent - indent
                    active_item_starts_mapping = cls._sequence_item_starts_mapping(stripped[2:])
                    line = " " * target_indent + stripped
                else:
                    active_item_original_indent = None
                    active_item_shift = 0
                    active_item_starts_mapping = False
            elif active_item_starts_mapping and active_sequence_parent_indent is not None:
                if stripped and indent <= active_sequence_parent_indent:
                    active_sequence_parent_indent = None
                    active_item_original_indent = None
                    active_item_shift = 0
                    active_item_starts_mapping = False
                elif (
                    active_item_original_indent is not None
                    and active_item_shift > 0
                    and indent > active_item_original_indent
                ):
                    line = " " * (indent + active_item_shift) + stripped
            elif stripped and not stripped.startswith("#"):
                active_sequence_parent_indent = None
                active_item_original_indent = None
                active_item_shift = 0
                active_item_starts_mapping = False

            normalized.append(line)

        suffix = "\n" if str(text or "").endswith("\n") else ""
        return "\n".join(normalized) + suffix

    @staticmethod
    def _sequence_item_starts_mapping(value: str) -> bool:
        return re.match(r"^[^\s\[\]{},][^:]*:(?:\s|$)", value.strip()) is not None

    @staticmethod
    def _previous_significant_line(lines: list[str]) -> str | None:
        for line in reversed(lines):
            if line.strip() and not line.lstrip(" ").startswith("#"):
                return line
        return None

    def clear_validation_error(self) -> None:
        last_line = max(self.lines() - 1, 0)
        last_index = max(self.lineLength(last_line), 0)
        self.clearIndicatorRange(0, 0, last_line, last_index, self._ERROR_INDICATOR)
        self.markerDeleteAll(self._ERROR_MARKER)

    def mark_validation_error(self, *, line: int | None = None, column: int | None = None) -> None:
        self.clear_validation_error()
        if line is None:
            return

        line_index = max(line - 1, 0)
        column_index = max((column or 1) - 1, 0)
        marker_length = max(self.lineLength(line_index) - column_index, 1)
        self.fillIndicatorRange(
            line_index,
            column_index,
            line_index,
            column_index + marker_length,
            self._ERROR_INDICATOR,
        )
        self.markerAdd(line_index, self._ERROR_MARKER)
        self.ensureLineVisible(line_index)
