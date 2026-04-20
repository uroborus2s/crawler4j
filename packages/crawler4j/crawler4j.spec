# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import shutil
import sys
import tomllib

import debugpy
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


def _load_project_version(pyproject_path: Path) -> str:
    with pyproject_path.open("rb") as f:
        pyproject = tomllib.load(f)
    return str(pyproject["project"]["version"])


block_cipher = None
PROJECT_ROOT = Path(globals().get("SPECPATH", Path.cwd())).resolve()
WORKSPACE_ROOT = PROJECT_ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
PROJECT_METADATA = PROJECT_ROOT / "pyproject.toml"
APP_ENTRY = PROJECT_ROOT / "src" / "ui" / "app.py"
UI_STYLE = PROJECT_ROOT / "src" / "ui" / "styles" / "dark_theme.qss"
UI_ICON = PROJECT_ROOT / "src" / "ui" / "assets" / "icon.jpg"
MODULES_DIR = PROJECT_ROOT / "modules"
DOCS_ROOT = WORKSPACE_ROOT / "docs"
PROJECT_VERSION = _load_project_version(PROJECT_METADATA)
PYINSTALLER_SUPPORT_ROOT = PROJECT_ROOT / "build" / "pyinstaller-support"
DEBUGPY_ROOT = Path(debugpy.__file__).resolve().parent
DEBUGPY_VENDORED_PYDEVD_ROOT = DEBUGPY_ROOT / "_vendored" / "pydevd"
WORKSPACE_RUNTIME_DISTS = {
    "crawler4j_contracts": "crawler4j-contracts",
    "crawler4j_sdk": "crawler4j-sdk",
}
WORKSPACE_RUNTIME_SOURCES = {
    "crawler4j_contracts": WORKSPACE_ROOT / "packages" / "crawler4j-contracts" / "src",
    "crawler4j_sdk": WORKSPACE_ROOT / "packages" / "crawler4j-sdk" / "src",
}


def _build_datas() -> list[tuple[str, str]]:
    datas = [
        (str(PROJECT_METADATA), "."),
        (str(UI_STYLE), "src/ui/styles"),
        (str(UI_ICON), "src/ui/assets"),
        (str(DOCS_ROOT / "index.md"), "docs"),
        (str(DOCS_ROOT / "01-getting-started"), "docs/01-getting-started"),
        (str(DOCS_ROOT / "02-user-guide"), "docs/02-user-guide"),
        (str(DOCS_ROOT / "03-developer-guide"), "docs/03-developer-guide"),
    ]
    if MODULES_DIR.exists():
        datas.append((str(MODULES_DIR), "modules"))
    datas.extend(collect_data_files("debugpy"))
    datas.extend(collect_data_files("debugpy", include_py_files=True))
    for dist_name in WORKSPACE_RUNTIME_DISTS.values():
        datas.extend(copy_metadata(dist_name))
    return datas


def _build_hiddenimports() -> list[str]:
    hiddenimports = [
        "PyQt6.sip",
        "debugpy",
        "playwright",
        "pandas",
        "ddddocr",
        "cv2",
        "numpy",
        "sqlite3",
    ]
    hiddenimports.extend(collect_submodules("debugpy"))
    hiddenimports.extend(_build_debugpy_vendored_hiddenimports())
    for package_name in WORKSPACE_RUNTIME_DISTS:
        hiddenimports.extend(collect_submodules(package_name))
    return hiddenimports


def _prepare_workspace_package_aliases() -> Path:
    alias_root = PYINSTALLER_SUPPORT_ROOT / "workspace-package-aliases"
    shutil.rmtree(alias_root, ignore_errors=True)
    alias_root.mkdir(parents=True, exist_ok=True)
    for package_name, source_root in WORKSPACE_RUNTIME_SOURCES.items():
        target_root = alias_root / package_name
        shutil.copytree(source_root, target_root)
    return alias_root


def _build_debugpy_vendored_hiddenimports() -> list[str]:
    hiddenimports: list[str] = []
    for path in sorted(DEBUGPY_VENDORED_PYDEVD_ROOT.rglob("*.py")):
        relative = path.relative_to(DEBUGPY_VENDORED_PYDEVD_ROOT)
        if "tests" in relative.parts:
            continue
        if path.name == "__init__.py":
            module_name = ".".join(relative.parts[:-1])
        else:
            module_name = ".".join(relative.with_suffix("").parts)
        if module_name:
            hiddenimports.append(module_name)
    return hiddenimports


WORKSPACE_PACKAGE_ALIAS_ROOT = _prepare_workspace_package_aliases()

a = Analysis(
    [str(APP_ENTRY)],
    pathex=[
        str(PROJECT_ROOT),
        str(WORKSPACE_PACKAGE_ALIAS_ROOT),
        str(DEBUGPY_VENDORED_PYDEVD_ROOT),
    ],
    binaries=[],
    datas=_build_datas(),
    hiddenimports=_build_hiddenimports(),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Crawler4j',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Crawler4j",
)

is_mac = sys.platform == "darwin"

if is_mac:
    app = BUNDLE(
        coll,
        name="Crawler4j.app",
        bundle_identifier="com.crawler4j.app",
        version=PROJECT_VERSION,
    )

import os
import shutil

# Post-build: Copy Playwright browsers if needed (instructions for user)
# Or handle versioning as needed

app_name = "Crawler4j"
if os.path.exists("dist"):
    print(f"Build completed! Application is in dist/{app_name}")
