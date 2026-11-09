"""离屏复现：高级缩放后 predefined_Board(1) 切初级，测量窗口/边框贴合与拖拽缩放。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["QT_FONT_DPI"] = "96"

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TEST_DIR, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

SETTINGS_DIR = "/tmp/metasweeper_mac_geom"
os.makedirs(SETTINGS_DIR, exist_ok=True)

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402

import mineSweeperGUI as mineSweeperGUI  # noqa: E402
import mainWindowGUI as mainWindowGUI  # noqa: E402


def report(ui, app, tag):
    app.processEvents()
    mw = ui.mainWindow
    hint = mw.minimumSizeHint()
    label = ui.label
    frame1 = getattr(ui, "frame_1", None)
    print(f"--- {tag} ---")
    print(f"  pixSize={ui.pixSize} row={ui.row} col={ui.column}")
    print(f"  window={mw.width()}x{mw.height()} minimumSizeHint={hint.width()}x{hint.height()}")
    print(f"  mw.minimumSize={mw.minimumSize().width()}x{mw.minimumSize().height()}")
    print(f"  label size={label.width()}x{label.height()} (期望 {ui.pixSize*ui.column}x{ui.pixSize*ui.row})")
    if frame1 is not None:
        g = frame1.geometry()
        lg = label.geometry()
        # frame_1 相对父容器的几何 vs label 几何，看边框是否包住棋盘
        print(f"  frame_1 geo=({g.x()},{g.y()},{g.width()}x{g.height()}) lineWidth={frame1.lineWidth()}")
        print(f"  label  geo=({lg.x()},{lg.y()},{lg.width()}x{lg.height()}) parent={label.parent().objectName() if label.parent() else None}")
        print(f"  label parent geo: {label.parent().geometry() if label.parent() else None}")
    print(f"  flag_drag_border={mw.flag_drag_border} suppress={mw._suppress_drag} "
          f"programmatic={mw._programmatic} aspect={mw._drag_aspect:.3f} native={mw._native_aspect}")


def main() -> int:
    app = QApplication([])
    mainWindow = mainWindowGUI.MainWindow()
    ui = mineSweeperGUI.MineSweeperGUI(mainWindow, [
        os.path.join(SETTINGS_DIR, "fake_main.py")])
    ui.mainWindow.show()
    app.processEvents()

    # 1. 初始初级
    report(ui, app, "启动后（初级）")

    # 2. 切高级并模拟缩放到 40
    ui.predefined_Board(3)
    for _ in range(200):
        app.processEvents()
    ui.pixSize = 40
    for _ in range(200):
        app.processEvents()
    report(ui, app, "高级@40（滚轮缩放后）")

    # 3. 按 1 切初级（保持比例 → 应仍为 40）
    ui.predefined_Board(1)
    # 等 minimumWindow 的吸附 timer 跑完（100 tick × 1ms + 布局）
    import time
    end = time.time() + 0.6
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)
    report(ui, app, "切回初级后（应保持 40）")

    # 4. 模拟拖拽：窗口放大，应触发 apply_drag_scale
    mw = ui.mainWindow
    w0, h0 = mw.width(), mw.height()
    mw.resize(w0 + 120, h0 + 120)
    for _ in range(30):
        app.processEvents()
    report(ui, app, f"拖拽放大 +120 后（拖拽中 flag={mw.flag_drag_border}）")
    # 触发松手吸附
    end = time.time() + 0.6
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)
    report(ui, app, "松手吸附后")
    print(f"  [probe] minimum_counter={ui.minimum_counter} timer_active={getattr(ui.timer_, 'isActive', lambda: None)() if getattr(ui, 'timer_', None) else None}")

    # 5. 吸附完成（suppress=False）后模拟真拖拽：放大窗口 → pixSize 应跟随
    mw = ui.mainWindow
    w0, h0 = mw.width(), mw.height()
    mw.resize(w0 + 160, h0 + 160)
    end = time.time() + 0.3
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)
    print(f"--- 真拖拽放大后（flag={mw.flag_drag_border} suppress={mw._suppress_drag}）---")
    print(f"  window={mw.width()}x{mw.height()} pixSize={ui.pixSize}（应 > 40 且窗口>起点）")
    # 松手吸附
    ui.finish_drag_scale()
    end = time.time() + 0.6
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)
    report(ui, app, "拖拽松手吸附后")
    ok = ui.pixSize > 40 and mw.width() > w0
    print("\n结果:", "拖拽缩放正常 ✅" if ok else "拖拽缩放异常 ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
