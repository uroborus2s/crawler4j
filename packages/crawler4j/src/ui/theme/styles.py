from src.ui.theme.palette import Palette


class StyleSheets:
    """Centralized Stylesheets."""
    
    MAIN_WINDOW = f"""
        QMainWindow {{
            background-color: {Palette.BG_MAIN};
        }}
    """
    
    GLASS_CARD = f"""
        QFrame.GlassCard {{
            background-color: {Palette.BG_GLASS};
            border: 1px solid {Palette.BORDER_LIGHT};
            border-radius: 12px;
        }}
    """
    
    SIDEBAR = f"""
        QWidget#Sidebar {{
            background-color: {Palette.BG_SIDEBAR};
            border-right: 1px solid {Palette.BORDER_LIGHT};
        }}
        QPushButton {{
            text-align: left;
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            color: {Palette.TEXT_SECONDARY};
            background-color: transparent;
            font-size: 14px;
        }}
        QPushButton:hover {{
            background-color: rgba(255, 255, 255, 0.05);
            color: {Palette.TEXT_PRIMARY};
        }}
        QPushButton:checked {{
            background-color: {Palette.ACCENT_PRIMARY};
            color: white;
            font-weight: bold;
        }}
    """

    MODERN_BUTTON = f"""
        QPushButton {{
            background-color: {Palette.ACCENT_PRIMARY};
            color: white;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {Palette.ACCENT_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {Palette.ACCENT_PRIMARY}; /* darkened slightly */
        }}
    """
