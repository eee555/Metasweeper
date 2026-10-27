# -*- mode: python ; coding: utf-8 -*-
# 元扫雷主程序 macOS 打包配置（PyInstaller）
# 由 package_tool/macos/build_mac.sh 调用
import glob
import os

from PyInstaller.utils.hooks import collect_data_files

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))  # 仓库根目录
SRC = os.path.join(ROOT, "src")

datas = [
    (os.path.join(SRC, "media"), "media"),
    (os.path.join(SRC, "params.onnx"), "."),
    (os.path.join(ROOT, "AI_AGENT_POLICY.md"), "."),  # 只读资源副本；policy_guard 用的是 Contents/MacOS 那份
    (os.path.join(ROOT, "README.md"), "."),
]
# 语言文件为发布版资源，源码仓库可能没有，有则一并打包
datas += [(qm, ".") for qm in glob.glob(os.path.join(SRC, "*.qm"))]
# textdistance 依赖包内数据文件
datas += collect_data_files("textdistance")

a = Analysis(
    [os.path.join(SRC, "main.py")],
    pathex=[SRC],
    binaries=[],
    datas=datas,
    hiddenimports=["ms_toollib", "textdistance"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "pywin32", "win32api", "win32con", "win32gui", "win32event",
        "winerror", "pythoncom", "pywintypes", "debugpy",
        "pytest", "_pytest", "tkinter",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Metasweeper",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=os.path.join(SPECPATH, "build", "Metasweeper.icns"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Metasweeper",
)
app = BUNDLE(
    coll,
    name="Metasweeper.app",
    icon=os.path.join(SPECPATH, "build", "Metasweeper.icns"),
    bundle_identifier="top.openms.metasweeper",
)
