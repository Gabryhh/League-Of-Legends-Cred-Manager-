# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file per RiotAccountsManager By Gabry
#
# Per buildare:
#   pyinstaller RiotAccountsManager.spec
#
# L'exe finale sarà in dist\RiotAccountsManager By Gabry\

import sys
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

APP_NAME = "RiotAccountsManager By Gabry"

a = Analysis(
    ["RiotAccountsManager.py"],
    pathex=[],
    binaries=[],
    datas=[
        # Include la cartella icone
        ("info/ico", "info/ico"),
    ],
    hiddenimports=[
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "cryptography.hazmat.primitives.kdf.pbkdf2",
        "cryptography.hazmat.backends.openssl",
        "PySide6.QtSvg",
        "PySide6.QtXml",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # nessuna finestra console
    icon="info/ico/256x256.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
