"""Serialized short database writes; replay compression runs on a separate worker."""
from __future__ import annotations

from concurrent.futures import Future
from itertools import count
from pathlib import Path
from queue import PriorityQueue
import sqlite3
from threading import Lock, Thread, current_thread
from typing import Callable, TypeVar

from .db import db_connection

_T = TypeVar("_T")
_writers: dict[Path, "DatabaseWriter"] = {}
_registry_lock = Lock()


class DatabaseWriter:
    def __init__(self, path: Path | str):
        self.path = Path(path).resolve()
        self._queue: PriorityQueue = PriorityQueue()
        self._sequence = count()
        self._lock = Lock()
        self._accepting = True
        self._ready: Future = Future()
        self._thread = Thread(target=self._run, name="history-db-writer")
        self._thread.start()
        self._ready.result()
        with _registry_lock:
            duplicate = self.path in _writers
            if not duplicate:
                _writers[self.path] = self
        if duplicate:
            self.close()
            raise RuntimeError("History database already has a writer")

    def execute(self, callback: Callable[[sqlite3.Connection], _T], *,
                background: bool = False, maintenance: bool = False) -> _T:
        if current_thread() is self._thread:
            return self._execute(callback)
        future: Future = Future()
        # 普通保存始终是最高优先级；回收与后台压缩同级，按入队顺序执行。
        # 插件启动后的首轮压缩完成后才入队回收，因此不会挡在迁移前面。
        priority = 1 if (background or maintenance) else 0
        with self._lock:
            if not self._accepting:
                raise RuntimeError("History database writer is closed")
            self._queue.put((priority, next(self._sequence), callback, future))
        return future.result()

    def reclaim_once(self) -> bool:
        """主动回收一次空闲页；有保存请求时保存优先执行。"""
        def compact(conn):
            # VACUUM 不能位于事务内；写线程在回调间已提交，这里只防御性清理。
            if conn.in_transaction:
                conn.rollback()
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                (free_pages,) = conn.execute("PRAGMA freelist_count").fetchone()
                if not free_pages:
                    return False
                conn.execute("VACUUM")
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                return True
            except sqlite3.OperationalError:
                # 其他连接占用 WAL/库时下次启动重试，不影响录像数据。
                return False
        return self.execute(compact, maintenance=True)

    def _execute(self, callback):
        try:
            result = callback(self._connection)
            self._connection.commit()
            return result
        except BaseException:
            self._connection.rollback()
            raise

    def _run(self):
        try:
            with db_connection(self.path, register_custom_functions=False) as conn:
                self._connection = conn
                # Readers keep seeing a committed snapshot while a short write commits.
                conn.execute("PRAGMA journal_mode=WAL").fetchone()
                self._ready.set_result(None)
                while True:
                    _, _, callback, future = self._queue.get()
                    if callback is None:
                        return
                    try:
                        future.set_result(self._execute(callback))
                    except BaseException as exc:
                        future.set_exception(exc)
        except BaseException as exc:
            if not self._ready.done():
                self._ready.set_exception(exc)
            else:
                with self._lock:
                    self._accepting = False
                    while not self._queue.empty():
                        _, _, _, future = self._queue.get_nowait()
                        if future is not None:
                            future.set_exception(exc)

    def close(self):
        with self._lock:
            if self._accepting:
                self._accepting = False
                # Drain accepted requests before closing the connection.
                self._queue.put((2, next(self._sequence), None, None))
        if current_thread() is not self._thread:
            self._thread.join()
        with _registry_lock:
            if _writers.get(self.path) is self:
                _writers.pop(self.path)


def execute_write(path: Path | str,
                  callback: Callable[[sqlite3.Connection], _T]) -> _T:
    with _registry_lock:
        writer = _writers.get(Path(path).resolve())
    if writer is not None:
        return writer.execute(callback)
    with db_connection(path, register_custom_functions=False) as conn:
        try:
            result = callback(conn)
            conn.commit()
            return result
        except BaseException:
            conn.rollback()
            raise
