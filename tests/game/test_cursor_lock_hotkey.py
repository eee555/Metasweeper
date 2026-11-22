from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6 import QtCore
from PySide6.QtCore import Qt

from config.constants import PLAYING
from config.key_bindings import (
    KEY_BINDINGS, TOGGLE_CURSOR_LIMIT_ID, apply_bindings,
)
from mineSweeperGUI import MineSweeperGUI, _CursorGeometryFilter


class _FakeBoardGUI:
    limit_cursor = MineSweeperGUI.limit_cursor
    unlimit_cursor = MineSweeperGUI.unlimit_cursor
    _focus_outside_board_window = MineSweeperGUI._focus_outside_board_window
    _suspend_cursor_lock = MineSweeperGUI._suspend_cursor_lock
    _sync_cursor_lock_with_focus = MineSweeperGUI._sync_cursor_lock_with_focus
    refresh_cursor_clip = MineSweeperGUI.refresh_cursor_clip
    _on_application_state_changed = MineSweeperGUI._on_application_state_changed
    _on_main_window_deactivated = MineSweeperGUI._on_main_window_deactivated
    _on_main_window_activated = MineSweeperGUI._on_main_window_activated
    _restore_saved_cursor_lock = MineSweeperGUI._restore_saved_cursor_lock
    _mark_cursor_limit_for_new_game = MineSweeperGUI._mark_cursor_limit_for_new_game
    _recorded_cursor_limit = MineSweeperGUI._recorded_cursor_limit
    _save_cursor_limit = MineSweeperGUI._save_cursor_limit
    set_cursor_lock = MineSweeperGUI.set_cursor_lock
    toggle_cursor_limit = MineSweeperGUI.toggle_cursor_limit

    def __init__(self):
        self.renderer = Mock()
        self.label = object()
        self.mainWindow = object()
        self.game_setting = Mock()
        self.game_state = 'ready'
        self.cursor_locked = False
        self.cursor_limit = False
        self._cursor_limit_used_this_game = False
        self._cursor_lock_suspended = False
        self._application_active = True
        self._saved_cursor_lock_pending = False


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


def test_main_window_deactivation_releases_and_reactivation_restores():
    gui = _FakeBoardGUI()

    with patch.object(_FakeBoardGUI, "_focus_outside_board_window", return_value=False):
        gui.set_cursor_lock(True)
        gui.renderer.limit_cursor.assert_called_once()

        gui._on_main_window_deactivated()
        assert gui._application_active is False
        assert gui._cursor_lock_suspended is True
        gui.renderer.unlimit_cursor.assert_called_once_with(gui.mainWindow)

        gui._on_main_window_activated()
        assert gui._application_active is True
        assert gui._cursor_lock_suspended is False
        assert gui.renderer.limit_cursor.call_count == 2


def test_application_state_inactive_keeps_lock_while_topmost():
    gui = _FakeBoardGUI()

    with patch.object(_FakeBoardGUI, "_focus_outside_board_window", return_value=False):
        gui.set_cursor_lock(True)
        gui._on_application_state_changed(
            Qt.ApplicationState.ApplicationInactive)

    assert gui._application_active is False
    assert gui._cursor_lock_suspended is False
    gui.renderer.unlimit_cursor.assert_not_called()


def test_saved_lock_setting_is_applied_when_focus_returns():
    gui = _FakeBoardGUI()
    gui.cursor_limit = True
    gui._saved_cursor_lock_pending = True
    gui._application_active = False

    gui._restore_saved_cursor_lock()
    assert gui._saved_cursor_lock_pending is True
    assert gui.cursor_locked is False

    with patch.object(_FakeBoardGUI, "_focus_outside_board_window", return_value=False):
        gui._application_active = True
        gui._restore_saved_cursor_lock()
        assert gui.cursor_locked is True
        assert gui._saved_cursor_lock_pending is False
        gui.renderer.limit_cursor.assert_called_once_with(
            gui.label, gui.mainWindow)
        gui.game_setting.set_value.assert_not_called()


def test_geometry_event_refreshes_clip_rectangle():
    gui = _FakeBoardGUI()

    with patch.object(_FakeBoardGUI, "_focus_outside_board_window", return_value=False):
        gui.set_cursor_lock(True)
        gui.refresh_cursor_clip()
        assert gui.renderer.limit_cursor.call_count == 2

    event_filter = _CursorGeometryFilter(gui)
    with patch.object(gui, "refresh_cursor_clip") as refresh:
        event_filter.eventFilter(
            gui.label, QtCore.QEvent(QtCore.QEvent.Type.Resize))
        refresh.assert_called_once_with()


def test_recorded_cursor_limit_records_any_enable_during_game():
    gui = _FakeBoardGUI()
    gui.game_state = PLAYING

    with patch.object(_FakeBoardGUI, "_focus_outside_board_window", return_value=False):
        gui.set_cursor_lock(True)
        assert gui._recorded_cursor_limit() is True

        gui.set_cursor_lock(False)
        assert gui.cursor_locked is False
        assert gui._recorded_cursor_limit() is True


def test_recorded_cursor_limit_uses_lock_state_at_game_start():
    gui = _FakeBoardGUI()
    gui.cursor_locked = True

    gui._mark_cursor_limit_for_new_game()
    assert gui._recorded_cursor_limit() is True
