# PyInstaller specification for the self-contained Windows distribution.
from pathlib import Path

import astropy
from PyInstaller.utils.hooks import collect_data_files


ROOT = Path(SPECPATH).parent
datas = [
    (str(ROOT / "astrochecker" / "static"), "astrochecker/static"),
    (str(ROOT / "data" / "catalog.sqlite3"), "data"),
]
datas.extend(collect_data_files("astropy"))
datas.extend(collect_data_files("tzdata"))
astropy_root = Path(astropy.__file__).resolve().parent
for parser_table in astropy_root.rglob("*_parsetab.py"):
    datas.append((str(parser_table), str(parser_table.parent.relative_to(astropy_root.parent))))
for lexer_table in astropy_root.rglob("*_lextab.py"):
    datas.append((str(lexer_table), str(lexer_table.parent.relative_to(astropy_root.parent))))
hiddenimports = [
    "astropy.constants.codata2022",
    "astropy.constants.iau2015",
]


a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(ROOT / "packaging" / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "playwright"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AstroChecker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
