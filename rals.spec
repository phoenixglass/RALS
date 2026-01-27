# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for RALS executable.

This configuration packages the RALS application as a standalone executable.
Run with: pyinstaller rals.spec
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import sys
import os

# Determine platform-specific settings
if sys.platform == 'win32':
    exe_name = 'RALS.exe'
    icon_file = 'icon.ico' if os.path.exists('icon.ico') else None
elif sys.platform == 'darwin':
    exe_name = 'RALS'
    icon_file = 'icon.icns' if os.path.exists('icon.icns') else None
else:
    exe_name = 'RALS'
    icon_file = None

# Collect data files for openpyxl and pandas
datas = []
datas += collect_data_files('openpyxl')

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'openpyxl',
    'openpyxl.xml',
    'openpyxl.cell',
    'openpyxl.styles',
    'openpyxl.worksheet',
    'openpyxl.workbook',
    'pandas',
    'pandas._libs',
    'pandas._libs.tslibs',
    'pandas._libs.tslibs.base',
    'pandas._libs.tslibs.timedeltas',
    'pandas._libs.tslibs.np_datetime',
    'pandas._libs.tslibs.nattype',
    'pandas._libs.tslibs.timestamps',
    'et_xmlfile',
    'decimal',
    'tkinter',
]

# Analysis - find all dependencies
a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',  # Exclude if not needed
        'scipy',
        'numpy.f2py',  # Reduce size
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# PYZ - Python archive
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# EXE - Executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

# For macOS, create an app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='RALS.app',
        icon=icon_file,
        bundle_identifier='com.phoenixglass.rals',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': 'True',
        },
    )
