from src.ui.theme.palette import Palette


class StyleSheets:
    """Shared stylesheet helpers."""

    @staticmethod
    def card(*, variant: str = "card") -> str:
        normalized_variant = variant if variant in {"plain", "group", "card"} else "card"
        if normalized_variant == "plain":
            frame_style = "background: transparent; border: none;"
        elif normalized_variant == "group":
            frame_style = (
                "background: rgba(255, 255, 255, 0.04); "
                f"border: 1px solid {Palette.BORDER_LIGHT}; "
                "border-radius: 14px;"
            )
        else:
            frame_style = (
                "background: rgba(17, 24, 39, 0.92); "
                f"border: 1px solid {Palette.BORDER_LIGHT}; "
                "border-radius: 18px;"
            )

        return f"""
        QFrame {{
            {frame_style}
        }}
        QLabel#cardTitle {{
            color: rgba(255, 255, 255, 0.7);
            font-size: 13px;
            font-weight: 600;
        }}
        """
