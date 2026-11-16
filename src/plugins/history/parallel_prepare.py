"""有界并行准备池：把解压 / 编码 / lzma 压缩等 CPU 工作移出协调线程。

数据库读写仍然只由协调线程和 ``DatabaseWriter`` 完成；准备任务只接收
不可变字节与快照，不持有 ``sqlite3.Connection``，因此不存在跨线程共享
连接的问题。

``zlib`` / ``lzma`` / ``hashlib`` 在计算期间会释放 GIL，多线程可以真正
并行；但由于结果需要按顺序提交，池只负责「同时准备几个批次」，
提交顺序由调用方保证。

资源约束：

- ``workers``：同时运行的任务数；
- ``max_in_flight``：已提交但尚未消费的任务上限，防止排队结果把内存
  撑大（每批结果含解压后的录像与编码块）。
"""

from __future__ import annotations

import os
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, TypeVar

# 默认并行度：实测 2 线程约 1.3x、4 线程约 1.9x，超过 4 后收益趋平。
DEFAULT_WORKERS = min(4, max(2, (os.cpu_count() or 4) // 4))

_T = TypeVar("_T")


class PreparePool:
    """固定并发度的准备线程池（可安全地在 ``with`` 中使用）。"""

    def __init__(self, workers: int = DEFAULT_WORKERS,
                 max_in_flight: int | None = None) -> None:
        self.workers = max(1, int(workers))
        # 在途上限略小于两倍并行度：让流水线不断流，又不把结果堆在内存里。
        self.max_in_flight = max(
            self.workers + 1, int(max_in_flight or self.workers * 2 - 1))
        self._executor: ThreadPoolExecutor | None = ThreadPoolExecutor(
            max_workers=self.workers, thread_name_prefix="history-prepare")

    def submit(self, fn: Callable[..., _T], /, *args: Any,
               **kwargs: Any) -> Future[_T]:
        executor = self._executor
        if executor is None:
            raise RuntimeError("PreparePool 已关闭")
        return executor.submit(fn, *args, **kwargs)

    def close(self) -> None:
        """停止接收新任务；取消排队任务并等待正在运行的准备结束。"""
        executor, self._executor = self._executor, None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)

    def __enter__(self) -> "PreparePool":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
