from dataclasses import replace
import csv
import time

from shared_types.aes_gcm import encrypt_gcm
import ms_toollib as ms
import pytest
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication

from utils import StatsRecord, board_list_to_bytes
from utils.csv_export import (export_csv, CsvExportWorker, CsvExportProgressDialog,
                              CsvBatchExportWorker)


KEY = bytes(range(16))


def make_record(**changes):
    board = [[0] * 8 for _ in range(8)]
    board[0][0] = -1
    board = ms.cal_board_numbers(board)
    record = StatsRecord(
        game_state=6, row=8, column=8, mine_num=10, rtime_ms=1234,
        left=5, right=2, double=1, rce=1, lce=3, dce=1,
        bbbv=2, bbbv_solved=2, zini=3, flag=1, path=12.5,
        start_time=1700000000000000, mode=0, is_official=True,
        is_fair=True, op=ms.Board(board).op, isl=ms.Board(board).isl, pluck=0,
        board_bytes=board_list_to_bytes(board),
    )
    return replace(record, **changes)


def write_dat(path, records):
    with path.open("wb") as f:
        f.write(b"\0")
        for record in records:
            blob = encrypt_gcm(KEY, record.encode())
            f.write(len(blob).to_bytes(2, "big") + blob)


@pytest.mark.parametrize("export_all,expected_count", [(False, 1), (True, 3)])
def test_export_filters_and_board_values(tmp_path, export_all, expected_count):
    dat = tmp_path / "stats.dat"
    target = tmp_path / "out.csv"
    write_dat(dat, [make_record(), make_record(game_state=2),
                    make_record(is_official=False), make_record(is_fair=False)])
    progress = []
    assert export_csv(dat, target, KEY, export_all,
                      lambda *args: progress.append(args)) == expected_count
    with target.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == expected_count
    assert progress[-1] == ("export", 4, 4)
    assert any(p[0] == "read" for p in progress)
    # Openings and islands use the validated stored values.
    assert all(row["Openings"] == str(make_record().op) for row in rows)
    assert all(row["Islands"] == str(make_record().isl) for row in rows)
    assert all(len(row) == (34 if export_all else 31) for row in rows)


def test_invalid_record_skipped_and_empty_input(tmp_path):
    dat = tmp_path / "stats.dat"
    target = tmp_path / "out.csv"
    write_dat(dat, [make_record(), make_record()])
    data = bytearray(dat.read_bytes())
    data[20] ^= 1
    dat.write_bytes(data)
    assert export_csv(dat, target, KEY) == 1
    dat.write_bytes(b"\0")
    with pytest.raises(ValueError, match="未找到有效的记录"):
        export_csv(dat, target, KEY)


def test_batch_export_matches_individual_files(tmp_path):
    dat = tmp_path / "stats.dat"
    write_dat(dat, [make_record(), make_record(game_state=2)])
    targets = [(tmp_path / "stats.csv", False), (tmp_path / "textstats.csv", True)]
    worker = CsvBatchExportWorker(dat, targets, KEY)
    worker.run()
    assert worker.error is None
    assert [count for _, count, _ in worker.results] == [1, 2]
    assert all(published for _, _, published in worker.results)
    for path, export_all in targets:
        reference = tmp_path / (path.stem + "-reference.csv")
        export_csv(dat, reference, KEY, export_all)
        assert path.read_bytes() == reference.read_bytes()


def test_batch_export_failure_preserves_existing_files(tmp_path, monkeypatch):
    import utils.csv_export as module

    targets = [(tmp_path / "stats.csv", False), (tmp_path / "textstats.csv", True)]
    for path, _ in targets:
        path.write_text("original", encoding="utf-8")
    def fail_second(dat, target, key, export_all, progress):
        if export_all:
            raise OSError("write failed")
        with open(target, "w", encoding="utf-8") as f:
            f.write("new")
        return 1

    monkeypatch.setattr(module, "export_csv", fail_second)
    worker = CsvBatchExportWorker(tmp_path / "stats.dat", targets, KEY)
    worker.run()
    assert worker.error == "write failed"
    assert all(path.read_text(encoding="utf-8") == "original" for path, _ in targets)
    assert not list(tmp_path.glob(".csv-export-*.tmp"))


def test_batch_export_reports_partial_publish_failure(tmp_path, monkeypatch):
    import utils.csv_export as module

    targets = [(tmp_path / "stats.csv", False), (tmp_path / "textstats.csv", True)]
    for path, _ in targets:
        path.write_text("original", encoding="utf-8")

    def fake_export(dat, target, key, export_all, progress):
        with open(target, "w", encoding="utf-8") as f:
            f.write("new")
        return 1

    replace_file = module.os.replace

    def fail_second(source, target):
        if target == targets[1][0]:
            raise OSError("replace failed")
        replace_file(source, target)

    monkeypatch.setattr(module, "export_csv", fake_export)
    monkeypatch.setattr(module.os, "replace", fail_second)
    worker = CsvBatchExportWorker(tmp_path / "stats.dat", targets, KEY)
    worker.run()
    assert worker.error == "replace failed"
    assert [published for _, _, published in worker.results] == [True, False]
    assert targets[0][0].read_text(encoding="utf-8") == "new"
    assert targets[1][0].read_text(encoding="utf-8") == "original"
    assert not list(tmp_path.glob(".csv-export-*.tmp"))


@pytest.mark.parametrize("fail", [False, True])
def test_worker_progress_keeps_gui_event_loop_running(monkeypatch, fail):
    import utils.csv_export as module

    app = QApplication.instance() or QApplication([])
    main_thread = QThread.currentThread()
    calls = []
    def slow_export(*args):
        assert QThread.currentThread() != main_thread
        for i in range(5):
            args[-1]("export", i, 5)
            time.sleep(0.03)
        if fail:
            raise OSError("write failed")
        return 5

    monkeypatch.setattr(module, "export_csv", slow_export)
    dialog = CsvExportProgressDialog()
    worker = CsvExportWorker(None, None, KEY, parent=dialog)
    worker.progress.connect(dialog.update_progress)
    worker.finished.connect(dialog.accept)
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: calls.append(QThread.currentThread()))
    timer.start()
    QTimer.singleShot(0, worker.start)
    # Esc/reject must not destroy a running thread.
    QTimer.singleShot(30, dialog.reject)
    watchdog = QTimer()
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(dialog.accept)
    watchdog.start(5000)
    dialog.exec()
    assert worker.wait(5000)
    timer.stop()
    watchdog.stop()
    assert len(calls) >= 3
    assert all(t == main_thread for t in calls)
    assert dialog.value() > 300
    assert worker.error == ("write failed" if fail else None)
    assert worker.record_num == (0 if fail else 5)
    dialog.deleteLater()
    app.processEvents()


@pytest.mark.parametrize("export_all", [False, True])
def test_export_preserves_order_and_monotonic_progress(tmp_path, export_all):
    dat = tmp_path / "stats.dat"
    records = [make_record(rtime_ms=i + 1000) for i in range(1100)]
    records[1] = replace(records[1], is_fair=False)
    records[400] = replace(records[400], game_state=2)
    records[600] = replace(records[600], mode=5)
    records[900] = replace(records[900], is_official=False)
    write_dat(dat, records)
    target = tmp_path / "out.csv"
    progress = []
    expected = [rec.rtime_ms / 1000 for rec in records
                if rec.is_fair and (export_all or
                   (rec.game_state == 6 and rec.mode == 0 and rec.is_official))]
    assert export_csv(dat, target, KEY, export_all,
                      lambda *args: progress.append(args)) == len(expected)
    with target.open(newline="", encoding="utf-8") as f:
        assert [float(row["Time"]) for row in csv.DictReader(f)] == expected
    export_progress = [current / total for phase, current, total in progress
                       if phase == "export" and total]
    assert export_progress == sorted(export_progress)
    assert export_progress[-1] == 1


def test_real_export_from_background_thread(tmp_path, qtbot):
    dat = tmp_path / "stats.dat"
    write_dat(dat, [make_record(rtime_ms=i + 1000) for i in range(1100)])
    dialog = CsvExportProgressDialog()
    qtbot.addWidget(dialog)
    target = tmp_path / "background.csv"
    worker = CsvExportWorker(dat, target, KEY, all=True, parent=dialog)
    worker.progress.connect(dialog.update_progress)
    worker.finished.connect(dialog.accept)
    timer = QTimer()
    heartbeats = []
    timer.setInterval(10)
    timer.timeout.connect(lambda: heartbeats.append(1))
    timer.start()
    with qtbot.waitSignal(worker.finished, timeout=15000):
        worker.start()
    timer.stop()
    assert worker.wait(5000)
    assert worker.error is None
    assert worker.record_num == 1100
    assert heartbeats
    assert dialog.value() == 1000



@pytest.mark.parametrize("export_all", [False, True])
def test_export_uses_stored_openings_and_islands_without_recalculating(tmp_path, monkeypatch, export_all):
    import utils.csv_export as module
    record = make_record()
    dat = tmp_path / "stats.dat"
    write_dat(dat, [record])
    real_board = module.ms.Board

    class BoardWithoutStoredStats:
        def __init__(self, board):
            self._board = real_board(board)

        def __getattr__(self, name):
            if name in ("op", "isl"):
                raise AssertionError("Export must use stored op/isl")
            return getattr(self._board, name)

    monkeypatch.setattr(module.ms, "Board", BoardWithoutStoredStats)
    target = tmp_path / "out.csv"
    assert export_csv(dat, target, KEY, export_all) == 1
    with target.open(newline="", encoding="utf-8") as f:
        row = next(csv.DictReader(f))
        assert row["Openings"] == str(record.op)
        assert row["Islands"] == str(record.isl)


@pytest.mark.parametrize("export_all", [False, True])
def test_threaded_csv_matches_serial_and_preserves_order(tmp_path, export_all):
    dat = tmp_path / "stats.dat"
    records = [make_record(rtime_ms=i + 1000) for i in range(1100)]
    records[1] = replace(records[1], is_fair=False)
    records[400] = replace(records[400], game_state=2)
    records[600] = replace(records[600], mode=5)
    records[900] = replace(records[900], is_official=False)
    write_dat(dat, records)
    serial = tmp_path / "serial.csv"
    parallel = tmp_path / "parallel.csv"
    expected_count = export_csv(dat, serial, KEY, export_all, threads=1)
    progress = []
    assert export_csv(dat, parallel, KEY, export_all,
                      lambda *args: progress.append(args), threads=4) == expected_count
    assert parallel.read_bytes() == serial.read_bytes()
    fractions = [current / total for phase, current, total in progress
                 if phase == "export" and total]
    assert fractions == sorted(fractions)
    assert fractions[-1] == 1


def test_thread_calculation_error_propagates(tmp_path):
    dat = tmp_path / "stats.dat"
    records = [make_record() for _ in range(600)]
    records[500] = replace(records[500], mode=99)
    write_dat(dat, records)
    with pytest.raises(IndexError):
        export_csv(dat, tmp_path / "error.csv", KEY, all=True, threads=2)


def test_small_export_keeps_serial(tmp_path, monkeypatch, capsys):
    import utils.csv_export as module

    def unexpected_pool(*args, **kwargs):
        raise AssertionError("Small exports must remain serial")

    dat = tmp_path / "stats.dat"
    write_dat(dat, [make_record() for _ in range(511)])
    monkeypatch.setattr(module, "ThreadPoolExecutor", unexpected_pool)
    assert export_csv(dat, tmp_path / "small.csv", KEY, all=True) == 511
    assert "计算线程数: 1" in capsys.readouterr().out


def test_only_hzini_runs_in_pool(tmp_path, monkeypatch):
    import threading
    import utils.csv_export as module
    dat = tmp_path / "stats.dat"
    write_dat(dat, [make_record() for _ in range(600)])
    coordinator = threading.get_ident()
    real_board = module.ms.Board
    calls = []

    class CheckedBoard:
        def __init__(self, board):
            assert threading.get_ident() == coordinator
            self.board = real_board(board)

        def __getattr__(self, name):
            if name == "hzini":
                assert threading.get_ident() != coordinator
                calls.append(name)
            else:
                assert threading.get_ident() == coordinator
            return getattr(self.board, name)

    monkeypatch.setattr(module.ms, "Board", CheckedBoard)
    assert export_csv(dat, tmp_path / "out.csv", KEY, all=True, threads=4) == 600
    assert len(calls) == 600


@pytest.mark.parametrize("cpus,records,expected", [
    (None, 44083, 1), (1, 44083, 1), (2, 44083, 1),
    (4, 44083, 2), (8, 44083, 4), (12, 44083, 6),
    (16, 44083, 8), (32, 44083, 8),
    (16, 0, 1), (16, 511, 1), (16, 1024, 2),
])
def test_automatic_thread_count(monkeypatch, cpus, records, expected):
    import utils.csv_export as module
    monkeypatch.setattr(module.os, "process_cpu_count", lambda: cpus, raising=False)
    assert module._choose_export_threads(records) == expected
