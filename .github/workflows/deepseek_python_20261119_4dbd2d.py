# dextop.spec
# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['dextop/gui.py'],
    pathex=[],
    binaries=[],
    datas=[('bin/', 'bin')],  # <-- Inclut les binaires
    # ...
)
# ...