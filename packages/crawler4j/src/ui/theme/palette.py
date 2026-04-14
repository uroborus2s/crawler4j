from dataclasses import dataclass


@dataclass
class ColorPalette:
    # Backgrounds
    BG_MAIN = "#121212"  # Deep dark functionality
    BG_GLASS = "rgba(40, 40, 45, 0.70)" # Semi-transparent container
    BG_SIDEBAR = "rgba(25, 25, 30, 0.85)" # Blurred sidebar
    BG_SECONDARY = "rgba(255, 255, 255, 0.05)" # Lighter background for headers/items

    
    # Text
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#AAAAAA"
    TEXT_DISABLED = "#666666"

    # Accents (Blue/Purple Gradient vibes in logic, here solid colors for Qt)
    ACCENT_PRIMARY = "#6C5CE7" # Purple-ish
    ACCENT_HOVER = "#5541C8"
    ACCENT_SUCCESS = "#00B894" # Green
    ACCENT_WARNING = "#FDCB6E" # Yellow/Orange
    ACCENT_ERROR = "#FF7675"   # Red
    ACCENT_INFO = "#74B9FF"    # Blue


    # Borders
    BORDER_LIGHT = "rgba(255, 255, 255, 0.1)"
    BORDER = "rgba(255, 255, 255, 0.1)" # General border
    BORDER_FOCUS = "rgba(108, 92, 231, 0.5)"


Palette = ColorPalette()
