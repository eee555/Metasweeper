"""CSV 导出计算和后台线程；工作线程不访问窗口或控件。"""
from array import array
from contextlib import contextmanager
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import os
import csv
from datetime import datetime
from time import perf_counter

import ms_toollib as ms
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PySide6.QtCore import QThread, Signal, Qt, Slot
from PySide6.QtWidgets import QProgressDialog

import utils



def _choose_export_threads(record_count):
    """Conservative CPU/workload heuristic, not a runtime performance benchmark."""
    # Prefer the process CPU limit when supported (Python 3.13+).
    cpu_count = getattr(os, "process_cpu_count", os.cpu_count)() or 1
    # Leave capacity for the coordinator/UI; logical CPUs may share physical cores.
    cpu_budget = max(1, cpu_count // 2)
    workload_budget = max(1, record_count // 512)
    return min(8, cpu_budget, workload_budget)


# One byte per cell prevents carries between neighbor counts (at most eight).
_MINE_BYTE_LANES = tuple(
    bytes((value >> bit) & 1 for bit in range(7, -1, -1))
    for value in range(256)
)


def _restore_csv_board(rows, cols, data):
    """Restore numbered cells without a cal_board_numbers round trip."""
    if rows <= 0 or cols <= 0:
        return utils.board_bytes_to_board(rows, cols, data)
    total = rows * cols
    cells = b"".join(map(_MINE_BYTE_LANES.__getitem__, data[:(total + 7) // 8]))
    if len(cells) < total:
        cells += bytes(total - len(cells))
    # Empty columns prevent neighbor shifts from wrapping across row boundaries.
    stride = cols + 2
    padded = b"".join(b"\0" + cells[i:i + cols] + b"\0"
                      for i in range(0, total, cols))
    mines = int.from_bytes(padded, "little")
    shift = stride * 8
    counts = ((mines << 8) + (mines >> 8)
              + (mines << shift) + (mines >> shift)
              + (mines << (shift - 8)) + (mines >> (shift - 8))
              + (mines << (shift + 8)) + (mines >> (shift + 8)))
    # Mark mines as 0xff, read them as signed -1, and trim shifted overflow.
    mask = (1 << (len(padded) * 8)) - 1
    values = ((counts | (mines * 255)) & mask).to_bytes(len(padded), "little")
    cells = array("b", values).tolist()
    return [cells[i + 1:i + 1 + cols] for i in range(0, len(padded), stride)]


def _prepare_board_batch(task):
    """Called only by the export coordinator; workers never construct boards."""
    batch, all = task
    started = perf_counter()
    boards = [ms.Board(_restore_csv_board(rec.row, rec.column, rec.board_bytes))
              for rec, _ in batch]
    return (batch, all, boards), perf_counter() - started


def _calculate_hzini_batch(boards):
    """The sole pool task: compute HZiNi on exclusively borrowed Board instances."""
    started = perf_counter()
    values = [board.hzini for board in boards]
    return values, perf_counter() - started


def _build_csv_batch(prepared, hzini_values):
    batch, all, boards = prepared
    if len(hzini_values) != len(batch):
        raise RuntimeError("HZiNi 批次结果数量不匹配")
    timings = {}
    rows = []

    @contextmanager
    def measure(name):
        stage_started = perf_counter()
        try:
            yield
        finally:
            timings[name] = timings.get(name, 0.0) + perf_counter() - stage_started

    def read_board_value(board, name):
        stage_started = perf_counter()
        try:
            return getattr(board, name)
        finally:
            elapsed = perf_counter() - stage_started
            label = f"board.{name} 属性读取/计算"
            timings[label] = timings.get(label, 0.0) + elapsed

    for (rec, mode), board, hzini in zip(batch, boards, hzini_values):
        dt = datetime.fromtimestamp(
            rec.start_time / 1_000_000 + rec.rtime_ms / 1000.0)

        style = "NF" if rec.rce == 0 else "Flag"
        if all:
            # 标准0、win74、经典无猜5、强无猜6、弱无猜7、准无猜8、强可猜9、弱可猜10、
            # 双击递归11、标雷递归12、双击标雷递归13、无猜双击递归14、无猜标雷递归15、无猜双击标雷递归16
            game_mode = ["classic", "", "", "", "win7", "classic no guess", "strict no guess",
                         "weak no guess", "blessing no guess", "guessable no guess", "lucky mode",
                         "chord recursive", "flag recursive", "chord flag recursive",
                         "no guess chord recursive", "no guess flag recursive",
                         "no guess chord flag recursive"][rec.mode]

        # op、isl 使用记录中的值；数字格属性保持原先访问顺序。
        with measure("其他棋盘属性读取合计（含分项计时开销）"):
            if all:
                with measure("读取已存 rec.op"):
                    op = rec.op
                with measure("读取已存 rec.isl"):
                    isl = rec.isl
                cells = {i: read_board_value(board, f"cell{i}") for i in range(1, 9)}
            else:
                cells = {i: read_board_value(board, f"cell{i}") for i in range(9)}
                with measure("读取已存 rec.op"):
                    op = rec.op
                with measure("读取已存 rec.isl"):
                    isl = rec.isl
        with measure("构造 CSV 行（不含棋盘属性计算）"):
            if all:
                row = [
                    game_mode, "win" if rec.game_state == 6 else "blast", dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second,
                    mode, rec.column, rec.row, rec.mine_num, rec.rtime_ms /
                    1000.0, rec.bbbv_solved, rec.bbbv, rec.zini, hzini,
                    op, isl, rec.left, rec.right, rec.double, rec.lce, rec.rce, rec.dce, rec.path, cells[1], cells[2], cells[3], cells[4], cells[5], cells[6], cells[7], cells[8]
                ]
            else:
                row = [
                    dt.day, dt.month, dt.year, dt.hour, dt.minute, dt.second,
                    mode, rec.rtime_ms / 1000.0, rec.bbbv, rec.bbbv_solved, style,
                    cells[0], cells[1], cells[2], cells[3], cells[4],
                    cells[5], cells[6], cells[7], cells[8],
                    rec.left, rec.right, rec.double,
                    rec.lce, rec.rce, rec.dce,
                    op, isl, rec.path, rec.zini, hzini,
                ]
        rows.append(row)
    return rows, timings


def _ordered_thread_results(pool, tasks, max_pending):
    """Prepare on the caller, calculate only HZiNi in workers, and retain source order."""
    tasks = iter(tasks)
    pending = deque()

    def submit(task):
        prepared, construction_time = _prepare_board_batch(task)
        future = pool.submit(_calculate_hzini_batch, prepared[2])
        pending.append((prepared, construction_time, future))

    try:
        for _ in range(max_pending):
            task = next(tasks, None)
            if task is None:
                break
            submit(task)
        while pending:
            prepared, construction_time, future = pending.popleft()
            started = perf_counter()
            values, calculation_time = future.result()
            wait_time = perf_counter() - started
            # No Board properties are read on the caller until the worker has returned.
            yield prepared, values, construction_time, calculation_time, wait_time
            task = next(tasks, None)
            if task is not None:
                submit(task)
    finally:
        for _, _, future in pending:
            future.cancel()


def _serial_hzini_results(tasks):
    for task in tasks:
        prepared, construction_time = _prepare_board_batch(task)
        values, calculation_time = _calculate_hzini_batch(prepared[2])
        yield prepared, values, construction_time, calculation_time, 0.0


def export_csv(dat_path, save_path, key, all=False, progress=None, *, threads=None):
    started = perf_counter()
    timings = {}
    records = []
    record_num = 0
    last_progress = started - 1
    thread_count = 1

    def report(phase, current, total, force=False):
        nonlocal last_progress
        now = perf_counter()
        if progress is not None and (force or now - last_progress >= 0.1):
            progress(phase, current, total)
            last_progress = now

    @contextmanager
    def measure(name):
        stage_started = perf_counter()
        try:
            yield
        finally:
            timings[name] = timings.get(name, 0.0) + perf_counter() - stage_started

    try:
        with measure("AES 初始化、解密与校验"):
            cipher = AESGCM(key)
        with measure("读取并解析 stats.dat（含解密、解码）"):
            with open(dat_path, 'rb') as f:
                file_size = dat_path.stat().st_size
                f.read(1)  # version byte
                while True:
                    len_bytes = f.read(2)
                    if not len_bytes or len(len_bytes) < 2:
                        break
                    blob_length = int.from_bytes(len_bytes, 'big')
                    blob = f.read(blob_length)
                    if not blob or len(blob) < blob_length:
                        break

                    report("read", f.tell(), file_size)
                    nonce = blob[:12]
                    tag = blob[12:28]
                    ciphertext = blob[28:]

                    try:
                        with measure("AES 初始化、解密与校验"):
                            # stats.dat 存储 nonce + tag + ciphertext；AESGCM 接收 ciphertext + tag。
                            plaintext = cipher.decrypt(nonce, ciphertext + tag, None)
                        with measure("StatsRecord.decode"):
                            records.append(utils.StatsRecord.decode(plaintext))
                    except Exception:
                        continue

        if not records:
            raise ValueError("未找到有效的记录")

        report("export", 0, len(records), force=True)
        if all:
            headers = [
                "Mode", "Event", "Year", "Month", "Day", "Hour", "Minute", "Second", "Level", "Width", "Height", "Mines", "Time", "Solved 3BV", "3BV", "ZiNi", "HZiNi", "Openings", "Islands", "Left Clicks", "Right Clicks", "Double Clicks", "Left Effective Clicks", "Right Effective Clicks", "Double Effective Clicks", "Path", "Ones", "Twos", "Threes", "Fours", "Fives", "Sixes", "Sevens", "Eights"
            ]
        else:
            headers = [
                "Day", "Month", "Year", "Hour", "Min", "Sec", "mode", "Time", "BBBV", "BBBVs", "style", "cell0", "cell1", "cell2", "cell3", "cell4", "cell5", "cell6", "cell7", "cell8", "Lcl", "Rcl", "Dcl", "Leff", "Reff", "Deff", "Openings", "Islands", "Path", "GZiNi", "HZiNi"
            ]

        with measure("筛选、计算与 CSV 写入（含文件关闭）"):
            selected = []
            for rec in records:
                if not rec.is_fair:
                    continue  # 只导出公平的记录
                if not all:
                    if rec.game_state != 6 or rec.mode != 0:
                        continue  # 只导出胜利的标准记录
                    if not (rec.is_official):
                        continue  # 只导出正式的记录

                if (rec.row, rec.column, rec.mine_num) == (8, 8, 10):
                    mode = "BEG"
                elif (rec.row, rec.column, rec.mine_num) == (16, 16, 40):
                    mode = "INT"
                elif (rec.row, rec.column, rec.mine_num) == (16, 30, 99):
                    mode = "EXP"
                else:
                    mode = "CUS"
                if not all and mode == "CUS":
                    continue  # 非标准模式不导出

                selected.append((rec, mode))

            if threads is None:
                thread_count = _choose_export_threads(len(selected))
            else:
                if threads < 1:
                    raise ValueError("threads 必须大于 0")
                thread_count = min(threads, 8)
            batch_size = 256
            batch_count = (len(selected) + batch_size - 1) // batch_size
            thread_count = min(thread_count, max(1, batch_count))
            tasks = ((selected[i:i + batch_size], all)
                     for i in range(0, len(selected), batch_size))
            with open(save_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)

                def consume(results):
                    nonlocal record_num
                    for prepared, values, construction_time, calculation_time, wait_time in results:
                        name = "棋盘还原与 ms.Board 构造"
                        timings[name] = timings.get(name, 0.0) + construction_time
                        name = "board.hzini 计算" + ("（计算线程累计）" if thread_count > 1 else "")
                        timings[name] = timings.get(name, 0.0) + calculation_time
                        name = "等待 HZiNi 批次完成"
                        timings[name] = timings.get(name, 0.0) + wait_time
                        rows, row_timings = _build_csv_batch(prepared, values)
                        for name, elapsed in row_timings.items():
                            timings[name] = timings.get(name, 0.0) + elapsed
                        with measure("writer.writerows（数据行）"):
                            writer.writerows(rows)
                        record_num += len(rows)
                        report("export", record_num, len(selected))

                with measure("分批计算、收集与写入（含线程调度）"):
                    if thread_count == 1:
                        consume(_serial_hzini_results(tasks))
                    else:
                        with ThreadPoolExecutor(max_workers=thread_count,
                                                thread_name_prefix="csv-export") as pool:
                            consume(_ordered_thread_results(pool, tasks, thread_count * 2))
        report("export", len(records), len(records), force=True)
        return record_num
    finally:
        total = perf_counter() - started
        print(f"[_export_csv] 类型={'Textstats' if all else 'Stats'}, "
              f"有效记录={len(records)}, 已导出={record_num}")
        print("[_export_csv] 棋盘构造方式: Python 位运算计算数字 + 二维列表")
        print(f"[_export_csv] 计算线程数: {thread_count}（线程池仅计算 HZiNi）")
        for name, elapsed in timings.items():
            print(f"[_export_csv] {name}: {elapsed:.6f} s")
        # 父阶段包含子阶段；线程累计值包含重叠执行/等待，不能当作实际处理时间。
        if thread_count > 1:
            print("[_export_csv] HZiNi 线程累计值包含重叠执行和等待；实际阻塞见等待 HZiNi 批次完成")
        print(f"[_export_csv] 后台处理总耗时（不含对话框等待）: {total:.6f} s",
              flush=True)


class CsvExportWorker(QThread):
    progress = Signal(str, object, object)

    def __init__(self, dat_path, save_path, key, all=False, parent=None):
        super().__init__(parent)
        self.dat_path = dat_path
        self.save_path = save_path
        self.key = key
        self.export_all = all
        self.record_num = 0
        self.error = None

    def run(self):
        try:
            self.record_num = export_csv(
                self.dat_path, self.save_path, self.key, self.export_all,
                self.progress.emit,
            )
        except Exception as exc:
            self.error = str(exc)


class CsvExportProgressDialog(QProgressDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("导出 CSV"))
        self.setLabelText(self.tr("正在读取 stats.dat..."))
        self.setRange(0, 1000)
        self.setValue(0)
        self.setCancelButton(None)
        self.setAutoClose(False)
        self.setAutoReset(False)
        self.setMinimumDuration(0)
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)

    def reject(self):
        # 导出结束前不能通过 Esc 关闭，避免销毁仍在运行的线程。
        pass

    @Slot(str, object, object)
    def update_progress(self, phase, current, total):
        fraction = current / max(total, 1)
        if phase == "read":
            self.setLabelText(self.tr("正在读取并解密记录... {n}%").replace(
                "{n}", str(int(fraction * 100))))
            self.setValue(int(fraction * 300))
        else:
            self.setLabelText(self.tr("正在计算并导出记录... {cur}/{total}")
                              .replace("{cur}", str(current))
                              .replace("{total}", str(total)))
            self.setValue(300 + int(fraction * 700))
