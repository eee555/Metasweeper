from concurrent.futures import ThreadPoolExecutor
import sqlite3
from threading import Event, get_ident

import pytest

from plugins.history.writer import DatabaseWriter, execute_write


def test_writer_prioritizes_saves_and_owns_connection(tmp_path):
    path = tmp_path / "history.db"
    writer = DatabaseWriter(path)
    started, release = Event(), Event()
    order, thread_ids = [], []
    try:
        writer.execute(lambda conn: conn.execute("CREATE TABLE saved (id INTEGER)"))
        def hold(conn):
            started.set()
            assert release.wait(5)
        def record(label):
            def write(conn):
                order.append(label)
                thread_ids.append(get_ident())
                conn.execute("INSERT INTO saved VALUES (?)", (len(order),))
            return write
        with ThreadPoolExecutor(max_workers=3) as pool:
            holding = pool.submit(writer.execute, hold)
            assert started.wait(5)
            background = pool.submit(writer.execute, record("maintenance"), background=True)
            # Wait until requests are enqueued, without timing assumptions.
            from time import monotonic
            deadline = monotonic() + 5
            while writer._queue.qsize() < 1 and monotonic() < deadline:
                Event().wait(0.001)
            saving = pool.submit(execute_write, path, record("save"))
            while writer._queue.qsize() < 2 and monotonic() < deadline:
                Event().wait(0.001)
            assert writer._queue.qsize() == 2
            release.set()
            holding.result(5)
            saving.result(5)
            background.result(5)
        assert order == ["save", "maintenance"]
        assert len(set(thread_ids)) == 1
        assert thread_ids[0] != get_ident()
        with sqlite3.connect(path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM saved").fetchone()[0] == 2
    finally:
        release.set()
        writer.close()


def test_writer_rolls_back_failed_save_and_keeps_running(tmp_path):
    path = tmp_path / "history.db"
    writer = DatabaseWriter(path)
    try:
        writer.execute(lambda conn: conn.execute("CREATE TABLE saved (id INTEGER)"))
        def fail(conn):
            conn.execute("INSERT INTO saved VALUES (1)")
            raise ValueError("save failed")
        with pytest.raises(ValueError, match="save failed"):
            writer.execute(fail)
        writer.execute(lambda conn: conn.execute("INSERT INTO saved VALUES (2)"))
        assert writer.execute(lambda conn: conn.execute("SELECT id FROM saved").fetchall()) == [(2,)]
    finally:
        writer.close()
    with pytest.raises(RuntimeError, match="closed"):
        writer.execute(lambda conn: None)


def test_reclaim_once_compacts_freelist_even_without_migration(tmp_path):
    import os

    path = tmp_path / "history.db"
    with sqlite3.connect(path) as setup:
        setup.execute("CREATE TABLE blob (id INTEGER PRIMARY KEY, data BLOB)")
        setup.executemany(
            "INSERT INTO blob VALUES (?, ?)",
            [(i, os.urandom(3000)) for i in range(300)])
        setup.commit()
    large = os.path.getsize(path)
    with sqlite3.connect(path) as setup:
        setup.execute("DELETE FROM blob")
        setup.commit()
    assert os.path.getsize(path) == large
    writer = DatabaseWriter(path)
    try:
        assert writer.reclaim_once() is True
        assert os.path.getsize(path) < large // 5
        # 没有空闲页时不重写数据库，也不产生错误。
        assert writer.reclaim_once() is False
    finally:
        writer.close()


def test_writer_allows_reader_during_uncommitted_write(tmp_path):
    path = tmp_path / "history.db"
    writer = DatabaseWriter(path)
    started, release = Event(), Event()
    try:
        writer.execute(lambda conn: conn.execute("CREATE TABLE saved (id INTEGER)"))
        def hold(conn):
            conn.execute("INSERT INTO saved VALUES (1)")
            started.set()
            assert release.wait(5)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(writer.execute, hold)
            assert started.wait(5)
            try:
                with sqlite3.connect(path, timeout=0) as reader:
                    assert reader.execute("SELECT COUNT(*) FROM saved").fetchone()[0] == 0
            finally:
                release.set()
            pending.result(5)
    finally:
        release.set()
        writer.close()
