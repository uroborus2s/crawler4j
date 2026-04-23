from src.ui.theme.palette import Palette


class StyleSheets:
    """Shared stylesheet helpers."""

    @staticmethod
    def stat_card(*, accent_color: str) -> str:
        return f"""
        QFrame {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(20, 25, 40, 0.92),
                stop:1 rgba(20, 25, 40, 0.82)
            );
            border: 1px solid {Palette.BORDER_LIGHT};
            border-radius: 10px;
        }}
        QLabel#statCardTitle {{
            color: rgba(255, 255, 255, 0.6);
            font-size: 12px;
            font-weight: 500;
        }}
        QLabel#statCardValue {{
            color: {accent_color};
            font-size: 28px;
            font-weight: 700;
        }}
        QLabel#statCardSubtitle {{
            color: rgba(255, 255, 255, 0.5);
            font-size: 11px;
        }}
        """
