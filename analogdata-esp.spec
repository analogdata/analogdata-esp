# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for analogdata-esp — onedir mode for fast startup.

Build:
    pip install pyinstaller
    pyinstaller analogdata-esp.spec

Output: dist/analogdata-esp/   (directory — starts in <1s vs 20s for onefile)
Release: packaging/build_release.sh creates the tar.gz for GitHub releases.
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect data files from packages that need them
datas = [
    # Bundle the project templates
    ("templates", "templates"),
]
datas += collect_data_files("rich")
datas += collect_data_files("typer")

# Hidden imports that PyInstaller misses via static analysis
hidden_imports = [
    "typer",
    "rich",
    "rich.console",
    "rich.panel",
    "rich.table",
    "rich.progress",
    "rich.markdown",
    "httpx",
    "jinja2",
    "serial",
    "dotenv",
    "google.generativeai",
    "analogdata_esp.commands.new",
    "analogdata_esp.commands.agent",
    "analogdata_esp.commands.doctor",
    "analogdata_esp.agent.router",
    "analogdata_esp.agent.context",
    "analogdata_esp.core.config",
    "analogdata_esp.core.template",
]
hidden_imports += collect_submodules("google.generativeai")
hidden_imports += collect_submodules("httpx")

a = Analysis(
    ["analogdata_esp/main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "scipy",
        "IPython",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── onedir EXE — exclude_binaries=True puts binary in WORKPATH for COLLECT ───
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,     # REQUIRED for onedir: binary → build dir, not dist
    name="analogdata-esp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# ── Collect everything into dist/analogdata-esp/ directory ───────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="analogdata-esp",
)
