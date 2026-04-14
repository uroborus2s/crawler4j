from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


class YamlHighlighter(QSyntaxHighlighter):
    """Simple YAML Syntax Highlighter."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # Keywords (keys)
        key_format = QTextCharFormat()
        key_format.setForeground(QColor("#FF7675")) # Red/Pink for keys
        key_format.setFontWeight(QFont.Weight.Bold)
        self.highlighting_rules.append((QRegularExpression(r"^\\s*[\\w\\-._]+:"), key_format))
        
        # Comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#666666"))
        self.highlighting_rules.append((QRegularExpression(r"#.*"), comment_format))
        
        # Strings
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#FDCB6E")) # Yellow
        self.highlighting_rules.append((QRegularExpression(r"\".*\""), string_format))
        self.highlighting_rules.append((QRegularExpression(r"'.*'"), string_format))
        
        # Booleans
        bool_format = QTextCharFormat()
        bool_format.setForeground(QColor("#6C5CE7")) # Purple
        self.highlighting_rules.append((QRegularExpression(r"\\b(true|false|True|False)\\b"), bool_format))

    def highlightBlock(self, text: str):
        for pattern, format in self.highlighting_rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)
