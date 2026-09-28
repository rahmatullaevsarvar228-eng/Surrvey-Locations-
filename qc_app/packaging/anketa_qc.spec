# -*- mode: python ; coding: utf-8 -*-
# Сборка: pyinstaller packaging/anketa_qc.spec --noconfirm   (из папки qc_app)
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "run_app.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "anketa_qc" / "web"), "anketa_qc/web"),
           (str(ROOT / "anketa_qc" / "geo_plan_default.json"), "anketa_qc"),
           (str(ROOT / "anketa_qc" / "cities_uz.json"), "anketa_qc"),
           (str(ROOT / "server" / "Connector.gs"), "anketa_qc/server")]
          + collect_data_files("docx"),          # шаблон пустого документа для отчёта Word
    hiddenimports=["openpyxl", "matplotlib.backends.backend_agg"],
    excludes=["tkinter", "matplotlib.backends.backend_tkagg", "matplotlib.backends._backend_tk",
              "IPython", "streamlit", "pytest"],
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
