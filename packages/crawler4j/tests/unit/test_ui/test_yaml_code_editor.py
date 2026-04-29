from __future__ import annotations

import yaml
from PyQt6.QtGui import QFont

from src.ui.components.yaml_code_editor import (
    YamlCodeEditor,
    _build_monospace_font,
    _recommended_extra_line_spacing,
)


def test_yaml_code_editor_normalizes_legacy_sequence_of_mapping(qtbot):
    editor = YamlCodeEditor()
    qtbot.addWidget(editor)

    editor.setPlainText("items:\n- name: a\n  value: 1\n- name: b\n  value: 2\n")

    assert editor.toPlainText() == (
        "items:\n"
        "    - name: a\n"
        "      value: 1\n"
        "    - name: b\n"
        "      value: 2\n"
    )
    assert yaml.safe_load(editor.toPlainText()) == {
        "items": [
            {"name": "a", "value": 1},
            {"name": "b", "value": 2},
        ]
    }


def test_build_monospace_font_prefers_available_fixed_pitch_family(monkeypatch):
    monkeypatch.setattr(
        "src.ui.components.yaml_code_editor._available_fixed_monospace_families",
        lambda: ["Consolas", "Courier New"],
    )

    font = _build_monospace_font()

    assert font.family() == "Consolas"
    assert font.pointSize() == 15
    assert font.fixedPitch()
    assert font.styleHint() == QFont.StyleHint.Monospace


def test_yaml_code_editor_applies_font_based_extra_line_spacing(qtbot):
    editor = YamlCodeEditor()
    qtbot.addWidget(editor)

    expected_spacing = _recommended_extra_line_spacing(editor.font())

    assert editor.font().pointSize() == 15
    assert editor.font().fixedPitch()
    assert editor.SendScintilla(editor._GET_EXTRA_ASCENT_MESSAGE) == expected_spacing
    assert editor.SendScintilla(editor._GET_EXTRA_DESCENT_MESSAGE) == expected_spacing
