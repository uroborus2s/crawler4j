"""Toast notification widget.

Provides brief, non-intrusive notifications.
"""

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect


class Toast(QWidget):
    """Toast notification widget.
    
    Usage:
        toast = Toast.show_message(parent, "Operation successful!", "success")
    """
    
    # Style presets
    STYLES = {
        "info": {
            "bg": "#313244",
            "text": "#cdd6f4",
            "icon": "ℹ️",
        },
        "success": {
            "bg": "#a6e3a1",
            "text": "#1e1e2e",
            "icon": "✅",
        },
        "warning": {
            "bg": "#f9e2af",
            "text": "#1e1e2e",
            "icon": "⚠️",
        },
        "error": {
            "bg": "#f38ba8",
            "text": "#1e1e2e",
            "icon": "❌",
        },
    }
    
    def __init__(
        self,
        message: str,
        style: str = "info",
        duration: int = 3000,
        parent=None,
    ):
        """Initialize toast notification.
        
        Args:
            message: Toast message text.
            style: Style preset (info/success/warning/error).
            duration: Display duration in milliseconds.
            parent: Parent widget.
        """
        super().__init__(parent)
        
        self.duration = duration
        self._opacity = 1.0
        
        # Get style config
        style_config = self.STYLES.get(style, self.STYLES["info"])
        
        # Setup UI
        self._setup_ui(message, style_config)
        
        # Setup animation
        self._setup_animation()
    
    def _setup_ui(self, message: str, style: dict):
        """Setup the toast UI."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        # Icon
        icon = QLabel(style["icon"])
        icon.setStyleSheet("font-size: 16px;")
        layout.addWidget(icon)
        
        # Message
        label = QLabel(message)
        label.setStyleSheet(f"""
            color: {style['text']};
            font-size: 13px;
            font-weight: 500;
        """)
        layout.addWidget(label)
        
        # Container style
        self.setStyleSheet(f"""
            Toast {{
                background-color: {style['bg']};
                border-radius: 8px;
            }}
        """)
        
        self.adjustSize()
    
    def _setup_animation(self):
        """Setup fade animation."""
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        # Fade out animation
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(300)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.fade_animation.finished.connect(self.close)
    
    def show_toast(self):
        """Show the toast and start timer."""
        self.show()
        
        # Position at top-right of parent
        if self.parent():
            parent_rect = self.parent().rect()
            x = parent_rect.width() - self.width() - 20
            y = 20
            self.move(x, y)
        
        # Start close timer
        QTimer.singleShot(self.duration, self._start_fade)
    
    def _start_fade(self):
        """Start fade out animation."""
        self.fade_animation.start()
    
    @classmethod
    def show_message(
        cls,
        parent: QWidget,
        message: str,
        style: str = "info",
        duration: int = 3000,
    ) -> "Toast":
        """Convenience method to show a toast.
        
        Args:
            parent: Parent widget.
            message: Toast message.
            style: Style preset.
            duration: Display duration in ms.
            
        Returns:
            Toast instance.
        """
        toast = cls(message, style, duration, parent)
        toast.show_toast()
        return toast
    
    @classmethod
    def success(cls, parent: QWidget, message: str) -> "Toast":
        """Show success toast."""
        return cls.show_message(parent, message, "success")
    
    @classmethod
    def error(cls, parent: QWidget, message: str) -> "Toast":
        """Show error toast."""
        return cls.show_message(parent, message, "error")
    
    @classmethod
    def warning(cls, parent: QWidget, message: str) -> "Toast":
        """Show warning toast."""
        return cls.show_message(parent, message, "warning")
    
    @classmethod
    def info(cls, parent: QWidget, message: str) -> "Toast":
        """Show info toast."""
        return cls.show_message(parent, message, "info")
