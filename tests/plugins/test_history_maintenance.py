import sqlite3
from threading import Event, Lock
from types import SimpleNamespace
import zlib

import pytest

from plugins.history.db import db_connection
from plugins.history.plugin import HistoryPlugin, _CompressionMigrateWorker
from plugins.history.replay_store import read_raw_data
from plugins.history.writer import DatabaseWriter
from shared_types.events import GameFinishedEvent


def initialized_database(path):
    shell = SimpleNamespace(data_dir=path.parent,
                            logger=SimpleNamespace(info=lambda *a: None))
    HistoryPlugin._init_db(shell)


def test_game_save_writes_only_durable_staging_and_survives_reopen(tmp_path):
    path = tmp_path / "history.db"
    initialized_database(path)
    emitted, notified = [], []
    shell = SimpleNamespace(
        data_dir=tmp_path,
        logger=SimpleNamespace(info=lambda *a: None),
        _migrate_worker=SimpleNamespace(notify=lambda: notified.append(True)),
        video_save_over=SimpleNamespace(emit=lambda: emitted.append(True)))
    writer = DatabaseWriter(path)
    try:
        event = GameFinishedEvent(raw_data=b"preserved replay bytes", board=[[0]],
                                  bbbv=100, bbbv_solved=1)
        HistoryPlugin._on_video_save(shell, event)
    finally:
        writer.close()
    assert emitted == notified == [True]
    with db_connection(path) as reader:
        assert reader.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 1
        assert reader.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0] == 0
        assert reader.execute("SELECT COUNT(*) FROM replay_staging").fetchone()[0] == 1
        assert read_raw_data(reader, 1) == event.raw_data


def test_low_value_save_keeps_metadata_without_replay(tmp_path):
    path = tmp_path / "history.db"
    initialized_database(path)
    shell = SimpleNamespace(
        data_dir=tmp_path,
        other_info=SimpleNamespace(min_replay_solved_percent=30),
        _migrate_worker=None,
        logger=SimpleNamespace(info=lambda *a: None),
        video_save_over=SimpleNamespace(emit=lambda: None))
    writer = DatabaseWriter(path)
    try:
        event = GameFinishedEvent(raw_data=b"replay", bbbv=100, bbbv_solved=29)
        HistoryPlugin._on_video_save(shell, event)
        with db_connection(path) as reader:
            assert reader.execute("SELECT bbbv_solved FROM history").fetchone()[0] == 29
            assert reader.execute("SELECT COUNT(*) FROM replay_index").fetchone()[0] == 0
            assert reader.execute("SELECT COUNT(*) FROM replay_staging").fetchone()[0] == 0
    finally:
        writer.close()


def test_save_failure_rolls_back_metadata_and_does_not_report_success(tmp_path, monkeypatch):
    from plugins.history import plugin
    path = tmp_path / "history.db"
    initialized_database(path)
    emitted = []
    shell = SimpleNamespace(
        data_dir=tmp_path,
        logger=SimpleNamespace(info=lambda *a: None),
        _migrate_worker=None,
        video_save_over=SimpleNamespace(emit=lambda: emitted.append(True)))
    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("disk full")
    monkeypatch.setattr(plugin, "write_record", fail)
    writer = DatabaseWriter(path)
    try:
        with pytest.raises(sqlite3.OperationalError, match="disk full"):
            HistoryPlugin._on_video_save(shell, GameFinishedEvent(raw_data=b"replay"))
        with db_connection(path) as reader:
            assert reader.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 0
        assert emitted == []
    finally:
        writer.close()


def test_worker_migrates_legacy_records_then_hides_progress(qtbot, tmp_path):
    path = tmp_path / "history.db"
    initialized_database(path)
    raw = b"unsupported format remains readable in staging"
    with db_connection(path) as conn:
        conn.execute("INSERT INTO history (replay_id, board) VALUES (1, '[0]')")
        conn.execute("INSERT INTO replay_data VALUES (1, ?, 1)", (zlib.compress(raw),))
        conn.commit()
    writer = DatabaseWriter(path)
    worker = _CompressionMigrateWorker(path, writer)
    states = []
    worker.progress.connect(lambda *state: states.append(state))
    try:
        worker.start()
        qtbot.waitUntil(lambda: any(s[0] for s in states) and states[-1][0] is False,
                        timeout=10000)
        with db_connection(path) as reader:
            assert read_raw_data(reader, 1) == raw
            assert reader.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0] == 0
        assert worker.isRunning()  # New data maintenance continues without the migration bar.
    finally:
        worker.requestInterruption()
        worker.notify()
        assert worker.wait(10000)
        writer.close()


def test_worker_hides_progress_after_migration_failure(qtbot, tmp_path, monkeypatch):
    from plugins.history import plugin
    path = tmp_path / "history.db"
    initialized_database(path)
    with db_connection(path) as conn:
        conn.execute("INSERT INTO replay_data VALUES (1, ?, 1)", (b"broken",))
        conn.commit()
    def fail(*args, **kwargs):
        raise ValueError("bad legacy data")
    monkeypatch.setattr(plugin, "migrate_from_replay_data", fail)
    writer = DatabaseWriter(path)
    worker = _CompressionMigrateWorker(path, writer)
    states = []
    worker.progress.connect(lambda *state: states.append(state))
    try:
        worker.start()
        qtbot.waitUntil(lambda: any(s[0] for s in states) and states[-1][0] is False,
                        timeout=10000)
        with db_connection(path) as reader:
            assert reader.execute("SELECT raw_data FROM replay_data").fetchone()[0] == b"broken"
    finally:
        worker.requestInterruption()
        worker.notify()
        assert worker.wait(10000)
        writer.close()


def test_delete_record_requests_background_compaction(tmp_path):
    path = tmp_path / "history.db"
    initialized_database(path)
    with db_connection(path) as conn:
        from plugins.history.replay_store import write_record
        conn.execute("INSERT INTO history (replay_id) VALUES (1)")
        write_record(conn, 1, b"staged replay")
        conn.commit()
    requested = []
    shell = SimpleNamespace(
        data_dir=tmp_path,
        logger=SimpleNamespace(info=lambda *a: None),
        _migrate_worker=SimpleNamespace(
            request_compaction=lambda: requested.append(True)))
    assert HistoryPlugin.delete_record(shell, 1) is True
    assert requested == [True]
    with db_connection(path) as reader:
        assert reader.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 0
        assert reader.execute("SELECT deleted FROM replay_index "
                              "WHERE replay_id = 1").fetchone()[0] == 1
        assert reader.execute("SELECT COUNT(*) FROM replay_staging "
                              "WHERE replay_id = 1").fetchone()[0] == 0


def test_worker_compacts_preexisting_tombstones_without_cleanup(qtbot, tmp_path):
    from plugins.history import replay_store
    from tests.replay.test_replay_store import make_evf

    path = tmp_path / "history.db"
    initialized_database(path)
    raws = {rid: make_evf(checksum=bytes([rid]) * 32) for rid in (1, 2, 3)}
    with db_connection(path) as conn:
        for rid, raw in raws.items():
            conn.execute("INSERT INTO history (replay_id) VALUES (?)", (rid,))
            replay_store.write_record(conn, rid, raw)
        conn.commit()
        replay_store.seal_staging(conn, limit=3)
        replay_store.mark_deleted(conn, 2)
        conn.commit()
    writer = DatabaseWriter(path)
    worker = _CompressionMigrateWorker(path, writer, min_solved_percent=0)
    try:
        worker.start()
        def compacted():
            with db_connection(path) as reader:
                return reader.execute(
                    "SELECT record_count FROM replay_segment").fetchone()[0] == 2
        qtbot.waitUntil(compacted, timeout=10000)
        with db_connection(path) as reader:
            assert read_raw_data(reader, 1) == raws[1]
            assert read_raw_data(reader, 2) is None
            assert read_raw_data(reader, 3) == raws[3]
    finally:
        worker.requestInterruption()
        worker.notify()
        assert worker.wait(10000)
        writer.close()


def test_startup_requests_reclaim_without_any_migration(qtbot, tmp_path, monkeypatch):
    path = tmp_path / "history.db"
    initialized_database(path)
    writer = DatabaseWriter(path)
    reclaimed = []
    monkeypatch.setattr(writer, "reclaim_once", lambda: reclaimed.append(True) or True)
    worker = _CompressionMigrateWorker(path, writer)
    worker.reclaim_requested = True  # 模拟 _start_compression_migrate()
    try:
        worker.start()
        qtbot.waitUntil(lambda: reclaimed == [True], timeout=10000)
        assert worker.reclaim_requested is False
        assert reclaimed == [True]
        assert worker.isRunning()
    finally:
        worker.requestInterruption()
        worker.notify()
        assert worker.wait(10000)
        writer.close()


def test_latest_progress_is_restored_for_recreated_widget():
    callbacks, shown = [], []
    shell = SimpleNamespace(
        _migration_state_lock=Lock(), _migration_state=(False, 0, 0, ""),
        run_on_widget=lambda callback: callbacks.append(callback))
    shell._apply_migration_progress = lambda widget: HistoryPlugin._apply_migration_progress(shell, widget)
    HistoryPlugin._on_migration_progress(shell, True, 2, 10, "verify")
    HistoryPlugin._on_migration_progress(shell, False, 0, 0, "")
    widget = SimpleNamespace(set_migration_progress=lambda *state: shown.append(state))
    for callback in callbacks:
        callback(widget)
    assert shown == [(False, 0, 0, ""), (False, 0, 0, "")]


def test_new_block_compression_does_not_block_saving_or_show_migration(qtbot, tmp_path, monkeypatch):
    from plugins.history import replay_store
    from tests.replay.test_replay_store import make_evf

    path = tmp_path / "history.db"
    initialized_database(path)
    raw = make_evf()
    with db_connection(path) as conn:
        for replay_id in range(1, 129):
            conn.execute("INSERT INTO history (replay_id) VALUES (?)", (replay_id,))
            replay_store.write_record(conn, replay_id, raw)
        conn.commit()
    compressing, release = Event(), Event()
    original = replay_store.lzma.compress
    def slow_compress(*args, **kwargs):
        compressing.set()
        assert release.wait(10)
        return original(*args, **kwargs)
    monkeypatch.setattr(replay_store.lzma, "compress", slow_compress)
    writer = DatabaseWriter(path)
    worker = _CompressionMigrateWorker(path, writer)
    states, saved = [], []
    worker.progress.connect(lambda *state: states.append(state))
    try:
        worker.start()
        qtbot.waitUntil(compressing.is_set, timeout=5000)
        shell = SimpleNamespace(
            data_dir=tmp_path, _migrate_worker=worker,
            logger=SimpleNamespace(info=lambda *a: None),
            video_save_over=SimpleNamespace(emit=lambda: saved.append(True)))
        HistoryPlugin._on_video_save(shell, GameFinishedEvent(raw_data=raw))
        assert saved == [True]
        with db_connection(path) as reader:
            assert reader.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 129
            assert read_raw_data(reader, 129) == raw
        assert not any(state[0] for state in states)
        release.set()
        def sealed():
            with db_connection(path) as reader:
                return reader.execute("SELECT COUNT(*) FROM replay_segment").fetchone()[0] == 1
        qtbot.waitUntil(sealed, timeout=5000)
    finally:
        release.set()
        worker.requestInterruption()
        worker.notify()
        assert worker.wait(10000)
        writer.close()


def test_worker_migrates_with_parallel_prepare_and_closes_pool(qtbot, tmp_path):
    """维护线程用有界准备池并行准备批次，停止后池被关闭。"""
    from tests.replay.test_replay_store import make_evf

    path = tmp_path / "history.db"
    initialized_database(path)
    raws = [make_evf(checksum=bytes([i % 200]) * 32) for i in range(1, 301)]
    with db_connection(path) as conn:
        for i, raw in enumerate(raws, 1):
            conn.execute("INSERT INTO history (replay_id) VALUES (?)", (i,))
            conn.execute("INSERT INTO replay_data VALUES (?, ?, 1)",
                         (i, zlib.compress(raw, 6)))
        conn.commit()

    writer = DatabaseWriter(path)
    worker = _CompressionMigrateWorker(path, writer, workers=2)
    try:
        worker.start()
        # 旧表清空的提交先于 finalized 状态发布，必须等待两者都完成。
        qtbot.waitUntil(
            lambda: worker.stats.get("finalized") == 1
            and _legacy_table_empty(path), timeout=20000)
        with db_connection(path) as reader:
            for i, raw in enumerate(raws, 1):
                assert read_raw_data(reader, i) == raw
        assert worker.stats.get("failed_batches", 0) == 0
        assert worker.stats.get("conflicts", 0) == 0
        assert worker.stats.get("finalized") == 1
    finally:
        try:
            worker.requestInterruption()
            worker.notify()
            assert worker.wait(20000)
            assert worker._prepare is None
        finally:
            # 关闭状态断言失败也不能遗留非 daemon 的数据库写线程。
            writer.close()


def _legacy_table_empty(path) -> bool:
    try:
        with db_connection(path) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM replay_data").fetchone()[0] == 0
    except Exception:
        return False
