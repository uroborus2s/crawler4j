from __future__ import annotations

import yaml

from src.ui.components.yaml_code_editor import YamlCodeEditor


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
