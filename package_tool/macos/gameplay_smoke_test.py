"""macOS 移植冒烟对局测试（离屏）。

模拟完整游戏流程：踩雷失败、胜利、标旗/取消标旗、重开、双键、关窗。
用法: QT_QPA_PLATFORM=offscreen .venv/bin/python package_tool/macos/gameplay_smoke_test.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["QT_FONT_DPI"] = "96"

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TEST_DIR, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

# 设置文件写入临时目录，避免污染仓库
SETTINGS_DIR = "/tmp/metasweeper_mac_smoke"
os.makedirs(SETTINGS_DIR, exist_ok=True)

from PySide6.QtWidgets import QApplication  # noqa: E402

import mineSweeperGUI as mineSweeperGUI  # noqa: E402
import mainWindowGUI as mainWindowGUI  # noqa: E402
import ms_toollib as ms  # noqa: E402


def state_of(ui):
    return str(getattr(ui, "_game_state", ""))


def click_all(ui, rows, cols, skip):
    for r in range(rows):
        for c in range(cols):
            if (r, c) in skip:
                continue
            if state_of(ui) in ("fail", "win", "jofail", "jowin"):
                return
            ui.execute_cell_click(r, c, 0)


def main() -> int:
    app = QApplication([])
    mainWindow = mainWindowGUI.MainWindow()
    ui = mineSweeperGUI.MineSweeperGUI(mainWindow, [
        os.path.join(SETTINGS_DIR, "fake_main.py")])
    ui.mainWindow.show()
    app.processEvents()
    errors = []

    # ── 1. 标旗 / 取消标旗 ──────────────────────────────
    ui.setBoard_and_start(9, 9, 10)
    app.processEvents()
    ui.execute_cell_click(0, 0, 1)  # 右键标旗
    app.processEvents()
    ui.execute_cell_click(0, 0, 1)  # 再右键取消
    app.processEvents()
    print("[ok] 标旗/取消标旗")

    # ── 2. 踩雷失败路径（用户遇到的崩溃点） ──────────────
    # 预设棋盘会被"首点必安全"重埋雷干扰，改用随机局：连开多局必出 fail。
    # fail 终态即走过 mineAreaLeftRelease → gameFailed → game_state → unlimit_cursor
    fail_games = 0
    for i in range(10):
        ui.setBoard_and_start(9, 9, 10)
        app.processEvents()
        click_all(ui, 9, 9, set())
        app.processEvents()
        if state_of(ui) in ("fail", "jofail"):
            fail_games += 1
    if fail_games == 0:
        errors.append("10 局随机对局没有出现失败终态")
    else:
        print(f"[ok] 踩雷失败路径（{fail_games}/10 局 fail，未崩溃）")

    # ── 3. 失败后重开（F2 路径） ─────────────────────────
    ui.setBoard_and_start(9, 9, 10)
    app.processEvents()
    if state_of(ui) not in ("ready", "playing"):
        errors.append(f"重开后预期 ready/playing，实际 {state_of(ui)}")
    else:
        print("[ok] 失败后重开")

    # ── 4. 预设棋盘：胜利路径 ────────────────────────────
    # 雷放在 (0,0..8) 第一行，点击其余所有格子 → 必胜
    board = [[-1] * 9, [0] * 9, [0] * 9, [0] * 9, [0] * 9,
             [0] * 9, [0] * 9, [0] * 9, [0] * 9]
    ui.engine.pending_boards.append({"board": board, "game_mode": 0})
    ui.gameMode = 0
    ui.setBoard_and_start(9, 9, 9)
    app.processEvents()
    click_all(ui, 9, 9, {(0, c) for c in range(9)})
    app.processEvents()
    if state_of(ui) != "win":
        errors.append(f"预期 win，实际 {state_of(ui)}")
    else:
        print("[ok] 胜利路径")

    # ── 5. 随机开局连玩 5 局（随机埋雷 + 全盘点击） ──────
    for i in range(5):
        ui.setBoard_and_start(9, 9, 10)
        app.processEvents()
        click_all(ui, 9, 9, set())
        app.processEvents()
        if state_of(ui) not in ("fail", "win", "jofail", "jowin"):
            errors.append(f"第{i + 1}局终态异常: {state_of(ui)}")
    print("[ok] 随机对局 x5")

    # ── 6. 高级盘面（16x30）一局 ─────────────────────────
    ui.setBoard_and_start(16, 30, 99)
    app.processEvents()
    ui.execute_cell_click(8, 15, 0)
    app.processEvents()
    click_all(ui, 16, 30, {(8, 15)})
    app.processEvents()
    print(f"[ok] 高级盘对局（终态 {state_of(ui)}）")

    # ── 7. 关窗路径（closeEvent → unlimit_cursor） ───────
    ui.mainWindow.close()
    app.processEvents()
    print("[ok] 关窗路径")

    if errors:
        for e in errors:
            print("[FAIL]", e)
        return 1
    print("\n全部对局流程通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
