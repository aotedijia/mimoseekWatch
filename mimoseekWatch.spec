# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

webview_data, webview_bins, webview_hidden = collect_all("webview")

a = Analysis(
    ["mimoseekWatch.py"],
    pathex=[],
    binaries=webview_bins,
    datas=webview_data + [("static", "static")],
    hiddenimports=webview_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="mimoseekWatch",
    icon=["static/mimoseekWatch.ico"],
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
