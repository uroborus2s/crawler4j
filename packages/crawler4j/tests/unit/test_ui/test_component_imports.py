import importlib
from pathlib import Path

import src.ui.components as components_pkg


def test_ui_component_modules_import_cleanly():
    components_dir = Path(components_pkg.__file__).resolve().parent
    module_names = sorted(
        path.stem
        for path in components_dir.glob("*.py")
        if path.name != "__init__.py"
    )

    for module_name in module_names:
        importlib.import_module(f"src.ui.components.{module_name}")
