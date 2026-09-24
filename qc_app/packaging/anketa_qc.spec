# -*- mode: python ; coding: utf-8 -*-
# Сборка: pyinstaller packaging/anketa_qc.spec --noconfirm   (из папки qc_app)
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "run_app.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "anketa_qc" / "web"), "anketa_qc/web")],
    hiddenimports=["openpyxl"],
    excludes=["tkinter", "matplotlib", "IPython", "streamlit", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AnketaQC",
    console=False,          # без чёрного окна консоли
    icon=str(ROOT / "packaging" / "app.ico"),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="AnketaQC", upx=False)
