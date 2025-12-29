# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/ui/styles/dark_theme.qss', 'src/ui/styles'),
        ('src/assets/icon.png', 'src/assets'),
    ],
    hiddenimports=[
        'PyQt6.sip',
        'playwright',
        'pandas',
        'ddddocr',
        'cv2',
        'numpy',
        'sqlite3',
    ],
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
    icon='src/assets/icon.png',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Crawler4j',
)

import sys
from src.__version__ import VERSION

is_mac = sys.platform == 'darwin'

if is_mac:
    app = BUNDLE(
        coll,
        name='Crawler4j.app',
        icon='src/assets/icon.png',
        bundle_identifier='com.crawler4j.app',
        version=VERSION
    )

import os
import shutil

# Post-build: Copy Playwright browsers if needed (instructions for user)
# Or handle versioning as needed

app_name = 'Crawler4j'
if os.path.exists('dist'):
    print(f"Build completed! Application is in dist/{app_name}")
