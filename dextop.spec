# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from pathlib import Path

datas = []
binaries = []
hiddenimports = []

if Path("bin").exists():
    datas.append(("bin", "bin"))

ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all("customtkinter")
datas += ctk_datas
binaries += ctk_binaries
hiddenimports += ctk_hiddenimports

a = Analysis(
    ["dextop/__main__.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DeXtop",
    console=False,
)
