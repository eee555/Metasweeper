import math
import threading
from types import SimpleNamespace

import pytest
import mineSweeperGUI as live_pluck


class Snapshot:
    def __init__(self, values):
        self.values = iter(values)

    def poll(self):
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return value


def test_wait_for_snapshot(monkeypatch):
    monkeypatch.setattr(live_pluck.time, 'sleep', lambda _: None)
    assert live_pluck.wait_for_pluck(Snapshot([None, None, 0.25])) == 0.25


def test_blocking_snapshot_called_once_and_errors_preserved():
    class BlockingSnapshot:
        calls = 0

        def wait(self):
            self.calls += 1
            return 0.25

        def poll(self):
            raise AssertionError('poll should not be called')

    snapshot = BlockingSnapshot()
    assert live_pluck.wait_for_pluck(snapshot) == 0.25
    assert snapshot.calls == 1

    class FailedSnapshot:
        def wait(self):
            raise RuntimeError('worker failed')

    with pytest.raises(RuntimeError, match='后台计算失败') as error:
        live_pluck.wait_for_pluck(FailedSnapshot())
    assert str(error.value.__cause__) == 'worker failed'


def test_real_rust_snapshot_survives_reset(qtbot):
    import ms_toollib as ms

    if not hasattr(ms.BaseVideo, 'live_pluck_snapshot'):
        pytest.skip('installed ms_toollib has no snapshot API')
    board = ms.BaseVideo([[1, -1], [1, 1]], 16)
    if not hasattr(board, 'live_pluck_enabled'):
        pytest.skip('installed ms_toollib has no live pluck switch')
    assert board.live_pluck_enabled is False
    assert board.live_pluck is None
    with pytest.raises(RuntimeError, match='disabled'):
        board.live_pluck_snapshot().wait()
    board.live_pluck_enabled = True
    for row, col in [(0, 0), (1, 0), (0, 1)]:
        for action in ('lc', 'lr'):
            board.step(action, (row * 16 + 1, col * 16 + 1))
    snapshot = board.live_pluck_snapshot()
    board.reset(2, 2, 16)
    assert board.live_pluck_enabled is True
    value = live_pluck.wait_for_pluck(snapshot)
    assert value == pytest.approx(-math.log10(2 / 3))
    assert live_pluck.wait_for_pluck(snapshot) == value


def test_real_rust_switch_replays_and_preserves_snapshot():
    import ms_toollib as ms

    board = ms.BaseVideo([[1, -1], [1, 1]], 16)
    if not hasattr(board, 'live_pluck_enabled'):
        pytest.skip('installed ms_toollib has no live pluck switch')
    for row, col in [(0, 0), (1, 0)]:
        for action in ('lc', 'lr'):
            board.step(action, (row * 16 + 1, col * 16 + 1))
    board.live_pluck_enabled = True
    snapshot = board.live_pluck_snapshot()
    board.live_pluck_enabled = False
    assert board.live_pluck is None
    assert snapshot.wait() == pytest.approx(-math.log10(2 / 3))
    board.live_pluck_enabled = True
    assert board.live_pluck_snapshot().wait() == pytest.approx(snapshot.wait())


def test_scoreboard_uses_legacy_sync_property():
    from dialogs import gameScoreBoard

    class Board:
        def __getattr__(self, name):
            return 0.4 if name == 'pluck' else 0

    manager = SimpleNamespace(namespace={})
    gameScoreBoard.gameScoreBoardManager.update_namespace(manager, Board(), 2)
    assert manager.namespace['pluck'] == 0.4


def test_scoreboard_uses_finished_result_without_sync_calculation():
    from dialogs import gameScoreBoard

    class Board:
        @property
        def pluck(self):
            raise AssertionError('synchronous pluck must not be read')

        def __getattr__(self, name):
            return 0

    board = Board()
    manager = SimpleNamespace(namespace={})
    wrapped = live_pluck._FinishedScoreBoard(board, 0.5)
    gameScoreBoard.gameScoreBoardManager.update_namespace(manager, wrapped, 2)
    gameScoreBoard.gameScoreBoardManager.update_namespace(manager, wrapped, 2)
    assert manager.namespace['pluck'] == 0.5


@pytest.mark.parametrize('method', ['gameStart', 'gameRestart'])
def test_start_and_restart_enable_live_pluck_after_reset(method):
    class Board:
        live_pluck_enabled = False

        def reset(self, *args):
            self.live_pluck_enabled = False

    board = Board()
    noop = lambda *args, **kwargs: None
    gui = SimpleNamespace(
        game_state='ready', minenum=1, row=2, column=2, pixSize=16,
        player_identifier='', label=SimpleNamespace(ms_board=board, reloadCellPic=noop, update=noop),
        label_2=SimpleNamespace(reloadFace=noop), label_info=SimpleNamespace(setText=noop),
        score_board_manager=SimpleNamespace(editing_row=0), timer_10ms=SimpleNamespace(stop=noop),
        showMineNum=noop, set_face=noop, showTime=noop, minimumWindow=noop,
        enable_screenshot=noop)
    getattr(live_pluck.MineSweeperGUI, method)(gui)
    assert board.live_pluck_enabled is True


def test_finished_view_uses_waited_result():
    class Board:
        game_board_state = 3

        @property
        def pluck(self):
            raise AssertionError('synchronous pluck must not be read')

    board = Board()
    displayed = []
    noop = lambda *args, **kwargs: None
    gui = SimpleNamespace(
        label=SimpleNamespace(ms_board=board, update=noop), end_then_flag=False,
        _finished_score_board=live_pluck._FinishedScoreBoard(board, 0.75),
        timeCount=noop, is_official=lambda: True, is_fair=lambda: True,
        score_board_manager=SimpleNamespace(with_namespace=noop,
                                            show=lambda b, **kw: displayed.append(b.pluck)),
        enable_screenshot=noop, unlimit_cursor=noop)
    live_pluck.MineSweeperGUI.gameFinished(gui)
    assert displayed == [0.75]


def test_failure_timeout_and_close_are_explicit(monkeypatch):
    with pytest.raises(RuntimeError, match='后台计算失败') as error:
        live_pluck.wait_for_pluck(Snapshot([RuntimeError('worker failed')]))
    assert str(error.value.__cause__) == 'worker failed'
    for value in (math.nan,):
        with pytest.raises(ValueError, match='结果无效'):
            live_pluck.wait_for_pluck(Snapshot([value]))
    assert live_pluck.wait_for_pluck(Snapshot([math.inf])) == math.inf
    with pytest.raises(RuntimeError, match='快照不可用'):
        live_pluck.wait_for_pluck(None)


def test_finished_event_is_sent_before_record_is_saved(monkeypatch, tmp_path):
    from mineSweeperGUI import MineSweeperGUI, GameServerBridge

    path = tmp_path / 'stats.dat'
    seen = []
    monkeypatch.setattr(GameServerBridge, 'instance', lambda: SimpleNamespace(
        send_event=lambda event: seen.append((event.pluck, path.exists()))))
    gui = SimpleNamespace(setting_path=tmp_path)
    event = SimpleNamespace(pluck=0.75)
    record = SimpleNamespace(pluck=0.75, encode=lambda: b'record')
    MineSweeperGUI._save_finished_record(gui, event, record)
    assert seen == [(0.75, False)]
    assert len(path.read_bytes()) > 1


def test_finished_record_keeps_unknown_pluck(monkeypatch, tmp_path):
    from mineSweeperGUI import MineSweeperGUI
    from mineSweeperGUI import GameServerBridge

    monkeypatch.setattr(GameServerBridge, 'instance', lambda: SimpleNamespace(send_event=lambda event: None))
    gui = SimpleNamespace(setting_path=tmp_path)
    MineSweeperGUI._save_finished_record(
        gui, SimpleNamespace(pluck=math.nan), SimpleNamespace(pluck=math.nan, encode=lambda: b'record'))
    assert (tmp_path / 'stats.dat').exists()


def test_game_finish_waits_for_snapshot(monkeypatch, tmp_path):
    import mineSweeperGUI
    from mineSweeperGUI import MineSweeperGUI

    monkeypatch.setattr(mineSweeperGUI, 'Path', lambda _: tmp_path / 'src' / 'mineSweeperGUI.py')
    class Board:
        board = [[0]]
        raw_data = b'replay'
        software = player_identifier = race_identifier = unique_identifier = ''

        def live_pluck_snapshot(self):
            return self.snapshot

        def __getattr__(self, name):
            return 0

    calls = []
    entered, release = threading.Event(), threading.Event()
    class BlockingSnapshot:
        def poll(self):
            entered.set()
            return 0.75 if release.is_set() else None
    board = Board()
    board.snapshot = BlockingSnapshot()
    gui = SimpleNamespace(
        label=SimpleNamespace(ms_board=board), autosave_video=False,
        mainWindow=None, game_state='win',
        score_board_manager=SimpleNamespace(show=lambda *args, **kwargs: None),
        dump_evf_file_data=lambda: calls.append('dump'),
        _save_finished_record=lambda event, record: calls.append((event.pluck, record.pluck)),
        try_append_evfs=lambda state: calls.append('evfs'))
    thread = threading.Thread(target=MineSweeperGUI.onGameFinished, args=(gui, 'win'))
    thread.start()
    try:
        assert entered.wait(2)
        assert thread.is_alive() and calls == ['dump']
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive()
    assert calls == ['dump', (0.75, 0.75), 'evfs']


def test_failed_snapshot_does_not_save(monkeypatch):
    import mineSweeperGUI

    class Board:
        board = [[0]]
        raw_data = b'same replay'
        software = player_identifier = race_identifier = unique_identifier = ''

        def live_pluck_snapshot(self):
            return Snapshot([RuntimeError('worker failed')])

        def __getattr__(self, name):
            return 0

    saved, refreshed = [], []
    gui = SimpleNamespace(
        label=SimpleNamespace(ms_board=Board()), autosave_video=False, mainWindow=None,
        game_state='win', dump_evf_file_data=lambda: None,
        try_append_evfs=lambda state: None,
        _save_finished_record=lambda event, record: saved.append((event.pluck, record.pluck)),
        score_board_manager=SimpleNamespace(show=lambda *a, **kw: refreshed.append(True)))
    with pytest.raises(RuntimeError, match='计算 pluck 失败'):
        mineSweeperGUI.MineSweeperGUI.onGameFinished(gui, 'win')
    assert saved == [] and refreshed == []


def test_legacy_board_preserves_pluck_before_reset(monkeypatch, tmp_path):
    import mineSweeperGUI

    monkeypatch.setattr(mineSweeperGUI, 'Path', lambda _: tmp_path / 'src' / 'mineSweeperGUI.py')
    class Board:
        board = [[0]]
        raw_data = b'replay'
        software = player_identifier = race_identifier = unique_identifier = ''
        pluck = 0.45

        def __getattr__(self, name):
            if name == 'live_pluck_snapshot':
                raise AttributeError(name)
            return 0

    saved = []
    board = Board()
    gui = SimpleNamespace(label=SimpleNamespace(ms_board=board), autosave_video=False,
                          mainWindow=None, dump_evf_file_data=lambda: None,
                          try_append_evfs=lambda state: None,
                          _save_finished_record=lambda event, record: saved.append((event.pluck, record.pluck)))
    mineSweeperGUI.MineSweeperGUI.onGameFinished(gui, 'win')
    board.pluck = 0.9
    assert saved == [(0.45, 0.45)]