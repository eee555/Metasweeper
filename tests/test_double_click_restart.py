from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget

from app.game_engine import GameEngine
from config.constants import (
    READY, PLAYING, JOKING, WIN, FAIL, JOWIN, JOFAIL,
    STUDY, DISPLAY, SHOW_DISPLAY, SHOW, MODIFY,
)
from dialogs.gameSettings import ui_Form
from mineSweeperGUIEvent import MineSweeperGUIEvent
from superGUI import IniConfig, Ui_MainWindow
from ui.mineLabel import mineLabel


@pytest.fixture
def board(qtbot):
    label = mineLabel(None)
    label.row = label.column = 8
    label.pixSize = 20
    label.setFixedSize(160, 160)
    qtbot.addWidget(label)
    return label


def send_mouse(label, event_type, button, buttons, pos=(10, 30)):
    position = QPointF(*pos)
    event = QMouseEvent(event_type, position, position, position,
                        button, buttons, Qt.NoModifier)
    QApplication.sendEvent(label, event)


def double_click(label, button=Qt.LeftButton, release_pos=(10, 30)):
    send_mouse(label, QEvent.MouseButtonPress, button, button)
    send_mouse(label, QEvent.MouseButtonRelease, button, Qt.NoButton)
    send_mouse(label, QEvent.MouseButtonDblClick, button, button)
    send_mouse(label, QEvent.MouseButtonRelease, button, Qt.NoButton, release_pos)


@pytest.mark.parametrize('state', [WIN, FAIL, JOWIN, JOFAIL])
@pytest.mark.parametrize('enabled', [False, True])
def test_double_click_restarts_only_after_second_release(board, state, enabled):
    engine = GameEngine()
    engine.row = engine.column = 8
    controller = SimpleNamespace(
        double_click_restart=enabled,
        game_state=state,
        pos_is_in_board=engine.pos_is_in_board,
        gameRestart=Mock(),
        mineAreaLeftRelease=Mock(),
    )
    board.leftRelease.connect(controller.mineAreaLeftRelease)
    board.leftDoubleRelease.connect(
        lambda i, j: MineSweeperGUIEvent.mineAreaLeftDoubleRelease(controller, i, j)
    )
    presses = Mock()
    board.leftPressed.connect(presses)

    send_mouse(board, QEvent.MouseButtonPress, Qt.LeftButton, Qt.LeftButton)
    send_mouse(board, QEvent.MouseButtonRelease, Qt.LeftButton, Qt.NoButton)
    controller.gameRestart.assert_not_called()
    send_mouse(board, QEvent.MouseButtonDblClick, Qt.LeftButton, Qt.LeftButton)
    controller.gameRestart.assert_not_called()
    send_mouse(board, QEvent.MouseButtonRelease, Qt.LeftButton, Qt.NoButton)

    assert presses.call_count == 2
    assert controller.gameRestart.call_count == int(enabled)
    # The release that restarts must not reach the new board as an opening click.
    assert controller.mineAreaLeftRelease.call_count == (1 if enabled else 2)
    controller.mineAreaLeftRelease.assert_called_with(30, 10)


@pytest.mark.parametrize('state', [READY, PLAYING, JOKING, STUDY, DISPLAY, SHOW_DISPLAY, SHOW, MODIFY])
def test_double_click_preserves_normal_release_in_other_states(state):
    controller = SimpleNamespace(
        double_click_restart=True,
        game_state=state,
        pos_is_in_board=GameEngine().pos_is_in_board,
        gameRestart=Mock(),
        mineAreaLeftRelease=Mock(),
    )
    MineSweeperGUIEvent.mineAreaLeftDoubleRelease(controller, 30, 10)
    controller.gameRestart.assert_not_called()
    controller.mineAreaLeftRelease.assert_called_once_with(30, 10)


@pytest.mark.parametrize('release_pos', [(-1, 30), (160, 30), (10, -1), (10, 160)])
def test_double_click_release_outside_board_does_not_restart(board, release_pos):
    engine = GameEngine()
    engine.row = engine.column = 8
    controller = SimpleNamespace(
        double_click_restart=True,
        game_state=FAIL,
        pos_is_in_board=engine.pos_is_in_board,
        gameRestart=Mock(),
        mineAreaLeftRelease=Mock(),
    )
    board.leftDoubleRelease.connect(
        lambda i, j: MineSweeperGUIEvent.mineAreaLeftDoubleRelease(controller, i, j)
    )
    double_click(board, release_pos=release_pos)
    controller.gameRestart.assert_not_called()


def test_right_double_click_preserves_right_button_events(board):
    presses, releases, left_double_releases = Mock(), Mock(), Mock()
    board.rightPressed.connect(presses)
    board.rightRelease.connect(releases)
    board.leftDoubleRelease.connect(left_double_releases)
    double_click(board, Qt.RightButton)
    assert presses.call_count == releases.call_count == 2
    left_double_releases.assert_not_called()


def test_chording_does_not_emit_left_double_release(board):
    double_releases, chord_presses, releases = Mock(), Mock(), Mock()
    board.leftDoubleRelease.connect(double_releases)
    board.leftAndRightPressed.connect(chord_presses)
    board.leftRelease.connect(releases)
    send_mouse(board, QEvent.MouseButtonDblClick, Qt.LeftButton, Qt.LeftButton)
    send_mouse(board, QEvent.MouseButtonPress, Qt.RightButton, Qt.LeftButton | Qt.RightButton)
    send_mouse(board, QEvent.MouseButtonRelease, Qt.LeftButton, Qt.RightButton)
    chord_presses.assert_called_once_with(30, 10)
    releases.assert_called_once_with(30, 10)
    double_releases.assert_not_called()


@pytest.fixture
def settings_window(qtbot, tmp_path):
    config_path = tmp_path / 'gameSetting.ini'
    config = IniConfig(str(config_path))
    parent = QWidget()
    qtbot.addWidget(parent)
    window = SimpleNamespace(
        game_setting=config, mainWindow=parent, label=Mock(),
        row=16, column=30, minenum=99,
    )
    Ui_MainWindow.read_or_create_game_setting(window)
    assert window.double_click_restart is False
    assert config.value('DEFAULT/double_click_restart', None, bool) is False
    # Simulate an existing installation whose configuration has no new key.
    config.config.remove_option('DEFAULT', 'double_click_restart')
    config.sync()
    return window


def test_setting_defaults_off_and_persists_both_values(qtbot, settings_window):
    for expected_initial, selected in [(False, True), (True, False)]:
        settings_window.game_setting = IniConfig(settings_window.game_setting.file_path)
        dialog = ui_Form(settings_window)
        qtbot.addWidget(dialog.Dialog)
        assert dialog.checkBox_double_click_restart.isChecked() is expected_initial
        dialog.checkBox_double_click_restart.setChecked(selected)
        dialog.pushButton_yes.click()
        assert dialog.alter is True
        config = IniConfig(settings_window.game_setting.file_path)
        assert config.value('DEFAULT/double_click_restart', None, bool) is selected


def test_cancel_does_not_save_setting(qtbot, settings_window):
    dialog = ui_Form(settings_window)
    qtbot.addWidget(dialog.Dialog)
    dialog.checkBox_double_click_restart.setChecked(True)
    dialog.pushButton_no.click()
    assert dialog.alter is False
    config = IniConfig(settings_window.game_setting.file_path)
    assert config.value('DEFAULT/double_click_restart', False, bool) is False


@pytest.mark.parametrize('game_mode', [11, 12, 13, 14, 15, 16])
def test_restart_setting_preserves_recursive_game_mode(qtbot, settings_window, game_mode):
    settings_window.gameMode = game_mode
    dialog = ui_Form(settings_window)
    qtbot.addWidget(dialog.Dialog)
    dialog.checkBox_double_click_restart.setChecked(True)
    dialog.pushButton_yes.click()

    assert dialog.gameMode == game_mode
    config = IniConfig(settings_window.game_setting.file_path)
    assert config.value('EXPERT/gamemode', None, int) == game_mode
    assert config.value('DEFAULT/double_click_restart', None, bool) is True
