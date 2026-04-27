from src.ui.components.text_edit import StyledPlainTextEdit, StyledTextEdit


def test_styled_text_edit_supports_monospace_variant(qtbot):
    editor = StyledTextEdit(monospace=True)
    qtbot.addWidget(editor)

    assert "font-family" in editor.styleSheet()
    assert "SF Mono" in editor.styleSheet()
    assert "QTextEdit:focus" in editor.styleSheet()


def test_styled_plain_text_edit_supports_shared_read_only_palette(qtbot):
    editor = StyledPlainTextEdit()
    qtbot.addWidget(editor)
    editor.setReadOnly(True)

    assert 'QPlainTextEdit[readOnly="true"]' in editor.styleSheet()
