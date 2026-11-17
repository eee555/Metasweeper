from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from config.key_bindings import (
    KEY_BINDINGS, TOGGLE_CURSOR_LIMIT_ID, apply_bindings,
)
from mineSweeperGUI import MineSweeperGUI


class _FakeBoardGUI:
    limit_cursor = MineSweeperGUI.limit_cursor
    unlimit_cursor = MineSweeperGUI.unlimit_cursor
    _focus_outside_board_window = MineSweeperGUI._focus_outside_board_window
    _suspend_cursor_lock = MineSweeperGUI._suspend_cursor_lock
    _sync_cursor_lock_with_focus = MineSweeperGUI._sync_cursor_lock_with_focus
    _save_cursor_limit = MineSweeperGUI._save_cursor_limit
    set_cursor_lock = MineSweeperGUI.set_cursor_lock
    toggle_cursor_limit = MineSweeperGUI.toggle_cursor_limit

    def __init__(self):
        self.renderer = Mock()
        self.label = object()
        self.mainWindow = object()
        self.game_setting = Mock()
        self.cursor_locked = False
        self.cursor_limit = False
        self._cursor_lock_suspended = False


def test_toggle_holds_lock_until_released():
    gui = _FakeBoardGUI()

    with patch.object(_FakeBoardGUI, "_focus_outside_board_window", return_value=False):
        gui.toggle_cursor_limit()
        assert gui.cursor_locked is True
        assert gui.cursor_limit is True
        gui.renderer.limit_cursor.assert_called_once_with(
            gui.label, gui.mainWindow)
        gui.game_setting.set_value.assert_called_with(
            "DEFAULT/cursor_limit", True)

        gui.toggle_cursor_limit()
        assert gui.cursor_locked is False
        assert gui.cursor_limit is False
        gui.renderer.unlimit_cursor.assert_called_once_with(gui.mainWindow)


def test_other_window_focus_suspends_and_restores_lock():
    gui = _FakeBoardGUI()

    with patch.object(_FakeBoardGUI, "_focus_outside_board_window", return_value=True):
        gui.set_cursor_lock(True)
        assert gui.cursor_locked is True
        assert gui._cursor_lock_suspended is True
        gui.renderer.limit_cursor.assert_not_called()
        gui.renderer.unlimit_cursor.assert_called_once_with(gui.mainWindow)

    with patch.object(_FakeBoardGUI, "_focus_outside_board_window", return_value=False):
        gui._sync_cursor_lock_with_focus()
        assert gui._cursor_lock_suspended is False
        gui.renderer.limit_cursor.assert_called_once_with(
            gui.label, gui.mainWindow)


def test_toggle_binding_is_registered_and_non_repeating():
    binding = next(b for b in KEY_BINDINGS
                   if b.id == TOGGLE_CURSOR_LIMIT_ID)
    assert binding.default == "F4"
    assert binding.attr == "frameShortcutCursorLimit"

    shortcut = Mock()
    target = SimpleNamespace(frameShortcutCursorLimit=shortcut, mainWindow=None)
    apply_bindings(target, {TOGGLE_CURSOR_LIMIT_ID: "F4"})

    shortcut.setKey.assert_called_once()
    shortcut.setAutoRepeat.assert_called_once_with(False)
