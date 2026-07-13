# -*- mode: python ; coding: utf-8 -*-
import os

project_root = os.path.abspath(os.path.join(SPECPATH, ".."))
backend_dir = os.path.join(project_root, "backend")
frontend_dist = os.path.join(project_root, "frontend", "dist")

a = Analysis(
    [os.path.join(backend_dir, "launcher.py")],
    pathex=[project_root, backend_dir],
    binaries=[],
    datas=[
        (frontend_dist, "frontend/dist"),
    ],
    hiddenimports=[
        "pandas",
        "numpy",
        "matplotlib",
        "matplotlib.pyplot",
        "openpyxl",
        "docx",
        "pypdf",
        "chardet",
        "passlib",
        "pkg_resources",
        "uvicorn.logging",
        "uvicorn.lifespan.off",
        "uvicorn.protocols.http.auto",
        "sqlalchemy.ext.asyncio",
        "platformdirs",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Project37",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, "frontend", "public", "favicon.ico") if os.path.exists(os.path.join(project_root, "frontend", "public", "favicon.ico")) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Project37",
)
