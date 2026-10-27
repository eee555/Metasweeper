# -*- mode: python ; coding: utf-8 -*-
# 元扫雷插件管理器 macOS 打包配置（PyInstaller）
# 构建产物 plugin_manager.app 由 build_mac.sh 内嵌进 Metasweeper.app/Contents/Resources
import glob
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
SRC = os.path.join(ROOT, "src")

datas = [
    # 内置插件以源码形式随包分发（与 Windows 版 internal/plugins 一致）
    (os.path.join(SRC, "plugins"), "plugins"),
    (os.path.join(ROOT, "AI_AGENT_POLICY.md"), "."),
    (os.path.join(ROOT, "README.md"), "."),
]
datas += [(qm, ".") for qm in glob.glob(os.path.join(SRC, "*.qm"))]

a = Analysis(
    [os.path.join(SRC, "plugin_manager_nuitka.py")],
    pathex=[SRC],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # 对齐 Windows 版 Nuitka 打包的显式包含清单（动态导入无法被静态分析发现）
        "sqlite3", "code", "xmlrpc.server", "xmlrpc.client",
        "http.server", "socketserver",
        "Crypto.Cipher.AES", "Crypto.Random",
        "PySide6.QtQuickWidgets", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtCharts",
        "zmq", "msgspec", "loguru", "requests", "textdistance",
        "cryptography", "PyMCUlib", "ms_toollib",
    ],
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
    name="plugin_manager",
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
    name="plugin_manager",
)
app = BUNDLE(
    coll,
    name="plugin_manager.app",
    icon=os.path.join(SPECPATH, "build", "Metasweeper.icns"),
    bundle_identifier="top.openms.metasweeper.plugin-manager",
    # 托盘常驻应用，不占用 Dock
    info_plist={"LSUIElement": True},
)
