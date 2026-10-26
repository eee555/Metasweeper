#!/usr/bin/env bash
# 元扫雷 macOS (Apple Silicon) 打包脚本
#
# 用法:  bash package_tool/macos/build_mac.sh
# 产物:  package_tool/macos/dist/Metasweeper.app
#
# 说明:
# - 需要本机 Python 3.10–3.12（推荐 3.12），首次运行自动创建 .venv 并安装依赖
# - pywin32 / debugpy 为 Windows 专用或可选依赖，macOS 构建不包含
# - 自行打包的版本无法对录像做官方签名（metaminesweeper_checksum 闭源），
#   其余功能与官方 Windows 版一致
# - 产物为 ad-hoc 签名，未公证：首次打开若被 Gatekeeper 拦截，
#   右键 App 选“打开”，或执行 xattr -cr dist/Metasweeper.app
set -euo pipefail

MACOS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$MACOS_DIR/../.." && pwd)"
SRC="$ROOT/src"
BUILD="$MACOS_DIR/build"
DIST="$MACOS_DIR/dist"
PY="$ROOT/.venv/bin/python"

# ── 1. 虚拟环境 ─────────────────────────────────────────
if [ ! -x "$PY" ]; then
    echo "[mac] 未找到 .venv，正在创建（需要 Python 3.10–3.12）..."
    if command -v python3.12 >/dev/null 2>&1; then
        python3.12 -m venv "$ROOT/.venv"
    else
        python3 -m venv "$ROOT/.venv"
    fi
    "$PY" -m pip install --upgrade pip
    "$PY" -m pip install \
        "PySide6>=6.8.0" "ms-toollib>=1.5.17" "msgspec>=0.20.0" "pyzmq" \
        "loguru>=0.7.3" "requests>=2.33.1" "textdistance" \
        "pycryptodome>=3.20.0" "cryptography>=50.0.2" "PyMCUlib>=1.0.3" \
        "setuptools" "pyinstaller>=6.10"
fi

"$PY" - <<'EOF'
import sys
if not (sys.version_info[:2] <= (3, 12) and sys.version_info >= (3, 10)):
    print(f"[mac] Python 版本不支持: {sys.version}（项目要求 >=3.10, <=3.12）")
    sys.exit(1)
EOF

# ── 2. 图标资源（cat.svg → iconset / cat.ico） ──────────
QT_QPA_PLATFORM=offscreen "$PY" "$MACOS_DIR/make_assets.py"
if [ ! -f "$BUILD/Metasweeper.icns" ]; then
    iconutil -c icns "$BUILD/Metasweeper.iconset" -o "$BUILD/Metasweeper.icns"
fi

# ── 3. PyInstaller 两段打包 ─────────────────────────────
rm -rf "$DIST" "$BUILD/work_main" "$BUILD/work_pm"

echo "[mac] 打包主程序 Metasweeper.app ..."
"$PY" -m PyInstaller --noconfirm --clean \
    --distpath "$DIST" --workpath "$BUILD/work_main" \
    "$MACOS_DIR/metasweeper_mac.spec"

echo "[mac] 打包插件管理器 plugin_manager.app ..."
"$PY" -m PyInstaller --noconfirm --clean \
    --distpath "$DIST" --workpath "$BUILD/work_pm" \
    "$MACOS_DIR/plugin_manager_mac.spec"

# ── 4. 组装最终 .app ────────────────────────────────────
APP="$DIST/Metasweeper.app"
echo "[mac] 内嵌插件管理器到 Resources ..."
rm -rf "$APP/Contents/Resources/plugin_manager.app"
# 用移动而非复制，保证 dist 下只剩一个 .app（运行时只使用内嵌这份）
mv "$DIST/plugin_manager.app" "$APP/Contents/Resources/plugin_manager.app"

# policy_guard 启动时校验可执行文件同级的 AI_AGENT_POLICY.md（MD5 必须与原文件一致）
cp "$ROOT/AI_AGENT_POLICY.md" "$APP/Contents/MacOS/"
cp "$ROOT/README.md" "$APP/Contents/MacOS/"
# 用户插件目录（与 Windows 版包结构一致）
mkdir -p "$APP/Contents/MacOS/plugins" "$APP/Contents/MacOS/user_plugins"

echo "[mac] ad-hoc 签名 ..."
codesign --force --deep --sign - "$APP"

# 清理 PyInstaller COLLECT 阶段的中间目录，dist 下只保留最终 .app
rm -rf "$DIST/Metasweeper" "$DIST/plugin_manager"

# ── 5. 打包 DMG（文件名带版本号） ───────────────────────
VERSION=$("$PY" - "$SRC/superGUI.py" <<'PYEOF'
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
match = re.search(r'^version\s*=\s*"元([\d.]+)"', text, re.M)
print(match.group(1) if match else "")
PYEOF
)
if [ -z "$VERSION" ]; then
    echo "[mac] 未能从 superGUI.py 解析版本号"
    exit 1
fi

DMG="$DIST/Metasweeper-$VERSION-arm64.dmg"
DMG_STAGING="$BUILD/dmg_staging"
rm -rf "$DMG_STAGING" "$DMG"
mkdir -p "$DMG_STAGING"
cp -R "$APP" "$DMG_STAGING/Metasweeper.app"
# 标准拖拽安装布局
ln -s /Applications "$DMG_STAGING/Applications"

echo "[mac] 生成 DMG: $(basename "$DMG") ..."
hdiutil create -volname "Metasweeper $VERSION" -srcfolder "$DMG_STAGING" \
    -ov -format UDZO -fs HFS+ "$DMG"
rm -rf "$DMG_STAGING"

echo
echo "[mac] 打包完成: $APP"
echo "[mac] DMG 安装包: $DMG"
echo "[mac] 启动: open \"$APP\""
