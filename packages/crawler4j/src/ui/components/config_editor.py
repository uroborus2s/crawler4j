from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QPlainTextEdit, QVBoxLayout

from src.ui.theme.palette import Palette
from src.ui.utils.syntax_highlighter import YamlHighlighter


class ConfigEditor(QFrame):
    """YAML Configuration Editor with Syntax Highlighting."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {Palette.BG_GLASS}; border-radius: 8px;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header/Toolbar
        # (Optional: Add 'Validate' button here later)
        
        # Editor
        self.editor = QPlainTextEdit()
        # Set Font
        font = QFont("Menlo", 12)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(font)
        
        # Style
        self.editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: transparent;
                color: {Palette.TEXT_PRIMARY};
                border: none;
                padding: 10px;
            }}
        """)
        
        self.highlighter = YamlHighlighter(self.editor.document())
        
        layout.addWidget(self.editor)

    def set_text(self, text: str):
        self.editor.setPlainText(text)
        
    def get_text(self) -> str:
        return self.editor.toPlainText()
