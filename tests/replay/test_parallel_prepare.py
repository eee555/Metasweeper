"""有界并行准备池与并行维护调度的回归测试。"""
from __future__ import annotations

import sqlite3
import threading
import zlib

import pytest

from plugins.history.parallel_prepare import PreparePool
from plugins.history.replay_store import (
    cleanup_low_value_replays,
    ensure_tables,
    migrate_from_replay_data,
    read_raw_data,
    write_record,
)

from tests.replay.test_replay_store import make_evf


def test_pool_runs_tasks_and_reports_results():
    with PreparePool(workers=2) as pool:
        futures = [pool.submit(pow, 2, n) for n in range(4)]
        assert [f.result() for f in futures] == [1, 2, 4, 8]


def test_pool_rejects_new_tasks_after_close():
    pool = PreparePool(workers=1)
    pool.close()
    with pytest.raises(RuntimeError):
        pool.submit(pow, 2, 3)


def test_pool_close_waits_for_running_task():
    started = threading.Event()
    release = threading.Event()
    shutdown_started = threading.Event()
    close_finished = threading.Event()
    shutdown_wait: list[bool] = []

    def slow() -> str:
        started.set()
        assert release.wait(5)
        return "done"

    pool = PreparePool(workers=1)
    executor = pool._executor
    assert executor is not None
    original_shutdown = executor.shutdown

    def observed_shutdown(*, wait: bool = True, cancel_futures: bool = False) -> None:
        shutdown_wait.append(wait)
        shutdown_started.set()
        original_shutdown(wait=wait, cancel_futures=cancel_futures)

    executor.shutdown = observed_shutdown

    def close_pool() -> None:
        pool.close()
        close_finished.set()

    future = pool.submit(slow)
    assert started.wait(5)
    closer = threading.Thread(target=close_pool)
    closer.start()
    try:
        assert shutdown_started.wait(5)
        # 任务仍被阻塞时，close 必须保持等待。
        assert not close_finished.wait(0.1)
    finally:
        release.set()
    closer.join(5)
    assert not closer.is_alive()
    assert close_finished.is_set()
    assert shutdown_wait == [True]
    assert future.result() == "done"


def _legacy_db(path, raws):
    conn = sqlite3.connect(path)
    try:
        ensure_tables(conn)
        conn.execute(
            "CREATE TABLE replay_data ("
            "replay_id INTEGER PRIMARY KEY, raw_data BLOB, compressed INTEGER)")
        for i, raw in enumerate(raws, 1):
            conn.execute("INSERT INTO replay_data VALUES (?, ?, 1)",
                         (i, zlib.compress(raw, 6)))
        conn.commit()
    finally:
        conn.close()


def test_migration_stops_cleanly_when_pool_closes(tmp_path):
    """准备池已关闭时不派发新批次，旧表与 staging 均保持可重跑。"""
    path = tmp_path / "history.db"
    raws = [make_evf(checksum=bytes([i]) * 32) for i in range(1, 4)]
    _legacy_db(path, raws)

    conn = sqlite3.connect(path)
    try:
        pool = PreparePool(workers=1)
        pool.close()
        stats: dict[str, int] = {}
        migrated, _sealed = migrate_from_replay_data(conn, prepare=pool,
                                                     stats=stats)
        assert migrated == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM replay_data").fetchone()[0] == len(raws)
        # 下一次（未关闭的池）仍能完整迁移
        with PreparePool(workers=1) as fresh:
            assert migrate_from_replay_data(conn, prepare=fresh)[0] == len(raws)
        for i, raw in enumerate(raws, 1):
            assert read_raw_data(conn, i) == raw
    finally:
        conn.close()


def test_cleanup_without_prepare_pool_still_works(tmp_path):
    """不给 prepare 时退化为串行，行为与旧实现一致。"""
    path = tmp_path / "history.db"
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE history ("
            "replay_id INTEGER PRIMARY KEY, bbbv INTEGER, bbbv_solved INTEGER)")
        ensure_tables(conn)
        raws = [make_evf(checksum=bytes([i]) * 32) for i in (1, 2)]
        for rid, solved in ((1, 1), (2, 100)):
            conn.execute("INSERT INTO history VALUES (?, 100, ?)", (rid, solved))
            write_record(conn, rid, raws[rid - 1])
        conn.commit()
        from plugins.history.replay_store import seal_staging
        assert seal_staging(conn, limit=2) == 2
        conn.commit()

        seen = []
        assert cleanup_low_value_replays(
            conn, 30, progress=lambda d, t: seen.append((d, t))) == 1
        assert seen[-1] == (1, 1)
        assert read_raw_data(conn, 1) is None
        assert read_raw_data(conn, 2) == raws[1]
    finally:
        conn.close()
