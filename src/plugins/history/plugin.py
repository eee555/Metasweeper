"""
历史记录插件主体
"""

from __future__ import annotations
from .widgets import HistoryMainWidget
from .compression import decompress
from .computed_column import ComputedColumn, validate_column_name
from .replay_store import (
    ensure_tables, write_record, migrate_from_replay_data, BLOCK_SIZE,
)
from plugins.services.history import HistoryService, GameRecord
from shared_types.events import GameFinishedEvent, LanguageChangeEvent
from plugin_sdk import (
    BasePlugin, PluginInfo, make_plugin_icon, WindowMode,
    OtherInfoBase, IntConfig, TextConfig, ChoiceConfig, BoolConfig,
)

import sqlite3
from pathlib import Path
from threading import Event, Lock
from typing import Any

from .db import db_connection, delete_record_tx, ensure_indexes
from .parallel_prepare import DEFAULT_WORKERS, PreparePool
from .writer import DatabaseWriter, execute_write

import msgspec
from PySide6.QtCore import QCoreApplication, QThread, Signal, Slot
from PySide6.QtWidgets import QWidget

from utils.plugin_i18n import PluginTranslate

_translate = PluginTranslate("HistoryPlugin")

# raw_data → replay_data 迁移批次大小
_MIGRATE_BATCH = 100


class _CompressionMigrateWorker(QThread):
    """独立准备压缩数据，仅把短事务交给数据库写线程。"""

    progress = Signal(bool, int, int, str)

    def __init__(self, db_path: Path, writer: DatabaseWriter, logger: Any = None,
                 batch_size: int = BLOCK_SIZE, min_solved_percent: int = 0,
                 workers: int = DEFAULT_WORKERS, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._writer = writer
        self._logger = logger
        self._batch_size = batch_size
        self._workers = max(1, int(workers))
        self._min_solved_percent = max(0, min(100, int(min_solved_percent)))
        self._wakeup = Event()
        self._cleanup_requested = self._min_solved_percent > 0
        self._last_fill_batch_max_id = 0
        self._fill_only_batch = False
        self._compact_requested = True
        self.reclaim_requested = False
        self._prepare: PreparePool | None = None
        self.stats: dict[str, int] = {}

    def _prepare_pool(self) -> PreparePool:
        """维护任务专用的有界准备池（线程池不跨任务复用结果）。"""
        if self._prepare is None:
            self._prepare = PreparePool(self._workers)
        return self._prepare

    def _record_stats(self, values: dict[str, int]) -> None:
        for key, value in values.items():
            self.stats[key] = self.stats.get(key, 0) + value

    def request_cleanup(self, threshold: int) -> None:
        self._min_solved_percent = max(0, min(100, int(threshold)))
        self._cleanup_requested = self._min_solved_percent > 0
        self.notify()

    def request_compaction(self) -> None:
        self._compact_requested = True
        self.notify()

    def notify(self):
        self._wakeup.set()

    def _write(self, operation):
        return self._writer.execute(operation, background=True)

    def _progress(self, phase):
        return lambda done, total: self.progress.emit(True, done, total, phase)

    def _migrate_legacy_raw(self, conn):
        """兼容极旧的 history.raw_data，每批快照复核后再转存。"""
        columns = {r[1] for r in conn.execute("PRAGMA table_info(history)")}
        if "raw_data" not in columns:
            return
        total = conn.execute(
            "SELECT COUNT(*) FROM history WHERE raw_data IS NOT NULL").fetchone()[0]
        done = 0
        while done < total and not self.isInterruptionRequested():
            rows = conn.execute(
                "SELECT replay_id, raw_data, compressed FROM history "
                "WHERE raw_data IS NOT NULL ORDER BY replay_id LIMIT ?",
                (_MIGRATE_BATCH,)).fetchall()
            if not rows:
                break
            self.progress.emit(True, done, total, "replays")

            def apply(target):
                target.execute("BEGIN IMMEDIATE")
                moved = 0
                for replay_id, raw, compressed in rows:
                    current = target.execute(
                        "SELECT raw_data, compressed FROM history WHERE replay_id = ?",
                        (replay_id,)).fetchone()
                    if current != (raw, compressed):
                        continue
                    target.execute(
                        "INSERT OR IGNORE INTO replay_data "
                        "(replay_id, raw_data, compressed) VALUES (?, ?, ?)",
                        (replay_id, raw, int(bool(compressed))))
                    # 不覆盖已有但内容不同的旧副本。
                    stored = target.execute(
                        "SELECT raw_data, compressed FROM replay_data WHERE replay_id = ?",
                        (replay_id,)).fetchone()
                    if stored == (raw, int(bool(compressed))):
                        target.execute("UPDATE history SET raw_data = NULL WHERE replay_id = ?",
                                       (replay_id,))
                        moved += 1
                return moved

            moved = self._write(apply)
            if not moved:
                raise ValueError("旧录像副本发生变化，暂缓迁移以保留原始数据")
            done += moved
        if total:
            self.progress.emit(True, done, total, "replays")

    def _migrate(self, conn) -> bool:
        """执行旧数据迁移；返回旧表是否已全部完成迁移与校验。"""
        from .replay_store import finalize_migration
        from .board_codec import migrate_board_to_ascii

        complete = True
        try:
            self._migrate_legacy_raw(conn)
            if self.isInterruptionRequested():
                return False
            count = conn.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0]
            if count:
                self.progress.emit(True, 0, count, "replays")
                stats: dict[str, int] = {}
                migrate_from_replay_data(
                    conn, batch_size=self._batch_size, write=self._write,
                    progress=self._progress("replays"),
                    cancelled=self.isInterruptionRequested,
                    prepare=self._prepare_pool(), stats=stats)
                self._record_stats(stats)
                if self.isInterruptionRequested():
                    return False
                finalized = finalize_migration(
                    conn, write=self._write, progress=self._progress("verify"),
                    cancelled=self.isInterruptionRequested)
                self.stats["finalized"] = int(bool(finalized))
                if not finalized:
                    complete = False
                    if self._logger is not None:
                        self._logger.info("旧录像表未通过校验，保留数据供下次继续")
            # board 迁移与旧录像表互不影响，校验失败时也应继续
            if not self.isInterruptionRequested():
                self.stats["boards"] = migrate_board_to_ascii(
                    conn, write=self._write, progress=self._progress("boards"),
                    cancelled=self.isInterruptionRequested)
            return complete and not self.isInterruptionRequested()
        except Exception as exc:
            if self._logger is not None:
                self._logger.warning(f"后台迁移未完成，保留数据供下次继续: {exc}")
            return False
        finally:
            self.progress.emit(False, 0, 0, "")

    def run(self):
        from .replay_store import (
            prepare_seal, apply_seal, cleanup_low_value_replays,
            count_sealable_staging, batch_sealable_staging_max_id,
            has_incomplete_segments, fill_incomplete_segments,
            compact_tombstone_segments,
        )

        try:
            with db_connection(self._db_path, register_custom_functions=False) as conn:
                migration_complete = self._migrate(conn)
                if (not migration_complete
                        and not self.isInterruptionRequested()
                        and self._logger is not None):
                    self._logger.info(
                        "旧数据迁移未全部完成，本次仍运行不依赖旧表的后台维护")
                while not self.isInterruptionRequested():
                    self._wakeup.clear()
                    try:
                        if self._cleanup_requested and not self.isInterruptionRequested():
                            self._cleanup_requested = False
                            try:
                                cleanup_low_value_replays(
                                    conn, self._min_solved_percent,
                                    write=self._write,
                                    progress=self._progress("cleanup"),
                                    cancelled=self.isInterruptionRequested,
                                    prepare=self._prepare_pool(),
                                    stats=self.stats)
                            finally:
                                self.progress.emit(False, 0, 0, "")
                        if (self._compact_requested
                                and not self.isInterruptionRequested()):
                            self._compact_requested = False
                            if compact_tombstone_segments(
                                    conn, write=self._write,
                                    cancelled=self.isInterruptionRequested):
                                self.reclaim_requested = True
                        new_batch_staging = count_sealable_staging(
                            conn, after_id=self._last_fill_batch_max_id)
                        skip_seal = False
                        if self._fill_only_batch:
                            if new_batch_staging < self._batch_size:
                                skip_seal = True
                            else:
                                self._fill_only_batch = False
                        else:
                            previous_watermark = self._last_fill_batch_max_id
                            batch_watermark = batch_sealable_staging_max_id(
                                conn, self._batch_size,
                                after_id=previous_watermark)
                            if (new_batch_staging >= self._batch_size
                                    and batch_watermark > previous_watermark
                                    and has_incomplete_segments(
                                        conn, self._batch_size)):
                                self._fill_only_batch = True
                                fill_incomplete_segments(
                                    conn, write=self._write,
                                    batch_size=self._batch_size,
                                    after_id=previous_watermark)
                                self._last_fill_batch_max_id = batch_watermark
                                self._compact_requested = True
                                if count_sealable_staging(conn) < \
                                        self._batch_size:
                                    skip_seal = True
                                else:
                                    self._fill_only_batch = False
                        if not skip_seal:
                            while not self.isInterruptionRequested():
                                prepared = prepare_seal(
                                    conn, limit=self._batch_size)
                                if prepared is None:
                                    break
                                if not self._write(
                                        lambda target: apply_seal(
                                            target, prepared)):
                                    break
                        if self.reclaim_requested and not self.isInterruptionRequested():
                            self.reclaim_requested = False
                            self._writer.reclaim_once()
                    except Exception as exc:
                        if self._logger is not None:
                            self._logger.warning(f"后台压缩暂缓，已落盘的录像不受影响: {exc}")
                    self._wakeup.wait(1.0)
        except Exception as exc:
            if self._logger is not None:
                self._logger.warning(f"后台数据库整理已停止: {exc}")
        finally:
            # 先停止接收准备任务并等待运行中的准备结束；数据库连接与写线程
            # 由外层（on_shutdown）顺序关闭。准备任务不持有连接，故此处
            # 关闭不影响已提交的数据。
            pool, self._prepare = self._prepare, None
            if pool is not None:
                pool.close()
            self.progress.emit(False, 0, 0, "")


class HistoryConfig(OtherInfoBase):
    """历史记录插件配置"""

    float_decimals = IntConfig(
        default=2,
        label=_translate("HistoryPlugin", "小数位数"),
        description=_translate("HistoryPlugin", "查询窗口中浮点数显示的小数位数"),
        min_value=0,
        max_value=10,
    )

    min_replay_solved_percent = IntConfig(
        default=0,
        label=_translate("HistoryPlugin", "录像最低 3BV 完成率（%）"),
        description=_translate(
            "HistoryPlugin", "清理低于此完成率的录像并保留历史统计；设为 0 则保留全部录像"),
        min_value=0,
        max_value=100,
    )

    # 隐藏字段：保存排序和过滤状态
    saved_filter = TextConfig(
        default="[]",
        label="saved_filter",
        visible=False,
    )

    saved_sort = TextConfig(
        default="[]",
        label="saved_sort",
        visible=False,
    )

    saved_show_fields = TextConfig(
        default="[]",
        label="saved_show_fields",
        visible=False,
    )

    saved_computed_columns = TextConfig(
        default="[{\"name\": \"bbbvs\", \"expression\": \"py_safe_div(bbbv_solved,rtime)\", \"result_type\": \"float\"}, {\"name\": \"距今天数\", \"expression\": \"py_days_since(start_time)\", \"result_type\": \"int\"}, {\"name\": \"距今月数\", \"expression\": \"py_months_since(start_time)\", \"result_type\": \"int\"}, {\"name\": \"ces\", \"expression\": \"py_safe_div(ce,rtime)\", \"result_type\": \"float\"}, {\"name\": \"cls\", \"expression\": \"py_safe_div(cl,rtime)\", \"result_type\": \"float\"}, {\"name\": \"corr\", \"expression\": \"py_safe_div(ce,cl)\", \"result_type\": \"float\"}, {\"name\": \"thrp\", \"expression\": \"py_safe_div(bbbv_solved,ce)\", \"result_type\": \"float\"}, {\"name\": \"ioe\", \"expression\": \"py_safe_div(bbbv_solved,cl)\", \"result_type\": \"float\"}]",
        label="saved_computed_columns",
        visible=False,
    )

    saved_custom_functions = TextConfig(
        default='''\
def py_safe_div(a, b):
    """安全除法，除零或空值返回 0（SQLite 除零会报错）"""
    if a is None or b is None or b == 0:
        return 0.0
    return a / b

def py_safe_mod(a, b):
    """安全取模，除零或空值返回 0（SQLite %0 会报错）"""
    if a is None or b is None or b == 0:
        return 0
    return a % b

def py_days_since(ts_us):
    """微秒时间戳距今天数，今天=0，昨天=1（SQLite 无内置）"""
    if ts_us is None:
        return None
    import time
    from datetime import datetime, date
    then = date.fromtimestamp(ts_us / 1_000_000)
    today = date.today()
    return (today - then).days

def py_months_since(ts_us):
    """微秒时间戳距今月数，当月=0，上月=1（SQLite 完全无法计算月差）"""
    if ts_us is None:
        return None
    from datetime import datetime
    then = datetime.fromtimestamp(ts_us / 1_000_000)
    now = datetime.now()
    return (now.year - then.year) * 12 + now.month - then.month

''',
        label="saved_custom_functions",
        visible=False,
    )

    page_size = ChoiceConfig(
        default="50",
        label=_translate("HistoryPlugin", "每页条数"),
        choices=[
            ("10", "10"),
            ("20", "20"),
            ("50", "50"),
            ("100", "100"),
            ("200", "200"),
            ("500", "500"),
            ("1000", "1000"),
        ],
        description=_translate("HistoryPlugin", "每页显示的历史记录条数"),
    )

    board_preview = BoolConfig(
        default=True,
        label=_translate("HistoryPlugin", "局面预览"),
        description=_translate(
            "HistoryPlugin", "鼠标悬浮在表格 board 列上时弹出该局的局面预览浮窗"),
    )


class HistoryPlugin(BasePlugin[HistoryConfig]):
    """
    历史记录插件

    - 后台：监听 GameFinishedEvent，写入 SQLite
    - 界面：提供筛选、分页、播放/导出功能
    - 服务：提供 HistoryService 接口供其他插件查询历史记录
    """
    video_save_over = Signal()

    @Slot(bool, int, int, str)
    def _on_migration_progress(self, active: bool, done: int, total: int,
                               phase: str) -> None:
        with self._migration_state_lock:
            self._migration_state = (active, done, total, phase)
        # 读取最新状态再投递，窗口关闭/重建后也能恢复正在进行的任务。
        self.run_on_widget(self._apply_migration_progress)

    def _apply_migration_progress(self, widget) -> None:
        with self._migration_state_lock:
            state = self._migration_state
        widget.set_migration_progress(*state)

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            # name 是配置目录、日志、状态键与授权记录的稳定标识，不随语言变化
            name="历史记录",
            display_name=_translate("HistoryPlugin", "历史记录"),
            description=_translate("HistoryPlugin", "游戏历史记录（SQLite 持久化）"),
            author="ljzloser",
            version="1.0.0",
            icon=make_plugin_icon("#7b1fa2", "\N{SCROLL}"),
            window_mode=WindowMode.TAB,  # type: ignore
            other_info=HistoryConfig,
        )

    def __init__(self, info):
        super().__init__(info)
        self._migration_state_lock = Lock()
        self._migration_state = (False, 0, 0, "")
        self._db_writer: DatabaseWriter | None = None
        self._migrate_worker: _CompressionMigrateWorker | None = None
        # 只连接一次；投递到 GUI 时再读取当前窗口，避免持有已关闭的视图。
        self.video_save_over.connect(self._refresh_widget)
        # 尽早加载自定义函数脚本，确保后续所有 db_connection 都能注册
        if self.other_info and self.other_info.saved_custom_functions:
            from .db import set_custom_script
            set_custom_script(self.other_info.saved_custom_functions)

    def _setup_subscriptions(self) -> None:
        self.subscribe(GameFinishedEvent, self._on_video_save)
        self.subscribe(LanguageChangeEvent, self._on_language_change)

    def _create_widget(self) -> QWidget:
        db_path = self.data_dir / "history.db"
        config_path = self.data_dir / "history_show_fields.json"

        # 获取配置中的小数位数、每页条数与局面预览开关
        float_decimals = 2
        page_size = "50"
        board_preview = True
        if self.other_info:
            float_decimals = self.other_info.float_decimals
            page_size = self.other_info.page_size
            board_preview = bool(self.other_info.board_preview)

        widget = HistoryMainWidget(
            db_path, config_path, float_decimals, page_size,
            board_preview=board_preview)

        # 连接排序和过滤状态变化信号
        widget.filter_sort_state_changed.connect(
            self._on_filter_sort_state_changed)

        # 连接列显示配置变化信号
        widget.show_fields_changed.connect(
            self._on_show_fields_changed)

        # 连接计算列变化信号
        widget.computed_columns_changed.connect(
            self.set_computed_columns)

        # 连接自定义函数变化信号
        widget.custom_functions_changed.connect(
            self._on_custom_functions_changed)

        # 删除记录后唤醒后台分块重组，避免墓碑槽位长期占用空间
        widget.compaction_requested.connect(self._on_compaction_requested)

        # 初始化计算列（必须在恢复过滤/排序状态之前，否则过滤引用计算列时查不到）
        if self.other_info:
            columns = ComputedColumn.from_json(
                self.other_info.saved_computed_columns)
            widget.on_computed_columns_changed(columns, reload=False)
            # 初始化自定义函数脚本
            if self.other_info.saved_custom_functions:
                widget.set_custom_functions(
                    self.other_info.saved_custom_functions)

        # 恢复保存的排序和过滤状态
        if self.other_info:
            widget.set_filter_sort_state(
                self.other_info.saved_filter,
                self.other_info.saved_sort
            )
            # 恢复保存的列显示配置
            widget.restore_show_fields(self.other_info.saved_show_fields)
            # 所有配置恢复完成后只执行一次启动查询
            widget.run_startup_query()

        self._apply_migration_progress(widget)
        return widget

    def _refresh_widget(self) -> None:
        self.run_on_widget(lambda widget: widget.query_button.click())

    def _on_language_change(self, event: LanguageChangeEvent) -> None:
        self.run_on_widget(lambda widget: widget.retranslateUi())

    @Slot()
    def _on_compaction_requested(self) -> None:
        worker = getattr(self, "_migrate_worker", None)
        if worker is not None:
            worker.request_compaction()

    def _on_filter_sort_state_changed(self, filter_json: str, sort_json: str) -> None:
        """保存排序和过滤状态"""
        if self.other_info:
            self.other_info.saved_filter = filter_json
            self.other_info.saved_sort = sort_json
            self.save_config()

    def _on_show_fields_changed(self, show_fields_json: str) -> None:
        """保存列显示配置"""
        if self.other_info:
            self.other_info.saved_show_fields = show_fields_json
            self.save_config()

    def _on_custom_functions_changed(self, script: str) -> None:
        """保存自定义函数脚本"""
        if self.other_info:
            self.other_info.saved_custom_functions = script
            self.save_config()

    def on_initialized(self) -> None:
        self._init_db()
        self._cleanup_legacy_view()
        self._db_writer = DatabaseWriter(self.data_dir / "history.db")
        self.run_on_widget(lambda widget: widget.run_startup_query())
        self.register_service(self, protocol=HistoryService)
        self.logger.info("历史记录插件已初始化，HistoryService 已注册")
        # 后台静默压缩旧数据
        self._start_compression_migrate()

    def _start_compression_migrate(self) -> None:
        """旧数据迁移完成后继续等待新暂存数据，进度条仅用于旧数据。"""
        if self._db_writer is None:
            return
        threshold = int(getattr(
            getattr(self, "other_info", None),
            "min_replay_solved_percent", 0))
        self._migrate_worker = _CompressionMigrateWorker(
            self.data_dir / "history.db", self._db_writer, logger=self.logger,
            min_solved_percent=threshold)
        self._migrate_worker.progress.connect(self._on_migration_progress)
        # 每次启动都尝试一次：即使没有旧数据迁移，也回收此前删除留下的空页。
        self._migrate_worker.reclaim_requested = True
        self._migrate_worker.start()

    def _cleanup_legacy_view(self) -> None:
        """清理旧版本遗留的 VIEW（子查询方式不再需要）"""
        db_path = self.data_dir / "history.db"
        if not db_path.exists():
            return
        with db_connection(db_path, register_custom_functions=False) as conn:
            cursor = conn.cursor()
            cursor.execute("DROP VIEW IF EXISTS history_view")
            conn.commit()
            self.logger.info("已清理旧 history_view")

    def get_computed_columns(self) -> list[ComputedColumn]:
        """获取当前计算列配置"""
        if self.other_info:
            return ComputedColumn.from_json(self.other_info.saved_computed_columns)
        return []

    def set_computed_columns(self, columns: list[ComputedColumn]) -> None:
        """更新计算列配置（统一校验入口：非法列名拒绝并记录警告）"""
        valid: list[ComputedColumn] = []
        for col in columns:
            error = validate_column_name(col.name)
            if error:
                self.logger.warning(
                    f"已拒绝非法计算列: {error.replace('%1', col.name)}")
                continue
            valid.append(col)
        columns = valid
        if self.other_info:
            self.other_info.saved_computed_columns = ComputedColumn.to_json(
                columns)
            self.save_config()
        # 通知 widget 刷新
        self.run_on_widget(
            lambda widget, value: widget.on_computed_columns_changed(value),
            columns)

    def on_shutdown(self) -> None:
        """在批次边界停止整理，再排空已接收的数据库写入。"""
        worker = self._migrate_worker
        if worker is not None:
            worker.requestInterruption()
            worker.notify()
            worker.wait()
            self._migrate_worker = None
        if self._db_writer is not None:
            self._db_writer.close()
            self._db_writer = None
        self._on_migration_progress(False, 0, 0, "")

    # ── 数据库 ──────────────────────────────────────────────

    def _init_db(self) -> None:
        db_path = self.data_dir / "history.db"
        if db_path.exists():
            with db_connection(db_path, register_custom_functions=False) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(history)")
                cols = {row[1] for row in cursor.fetchall()}
                if "game_state" in cols:
                    # 旧 schema 缺少 compressed 列则追加（列保留，供回退读取）
                    if "compressed" not in cols:
                        cursor.execute(
                            "ALTER TABLE history ADD COLUMN compressed INTEGER DEFAULT 0"
                        )
                        conn.commit()
                        self.logger.info("已添加 compressed 列")
                    # 清理旧版本遗留的 VIEW（改用子查询方式不再需要）
                    cursor.execute("DROP VIEW IF EXISTS history_view")
                    conn.commit()
                    # 极旧 raw_data 留给后台逐批迁移，启动阶段只确保表结构。
                    cursor.execute(
                        "CREATE TABLE IF NOT EXISTS replay_data ("
                        "replay_id INTEGER PRIMARY KEY, raw_data BLOB, "
                        "compressed INTEGER DEFAULT 0)")
                    conn.commit()
                    # 确保查询索引存在
                    ensure_indexes(conn)
                    # 分块列式存储表（幂等，不改 history 任何列）
                    ensure_tables(conn)
                    return
                self.logger.info("旧 schema，迁移中…")
                cursor.executescript("DROP TABLE IF EXISTS history;")
                conn.commit()
        with db_connection(db_path, register_custom_functions=False) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE history (
                    replay_id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_state          INTEGER,
                    nf                  INTEGER,
                    row                 INTEGER,
                    column              INTEGER,
                    mine_num            INTEGER,
                    rtime               REAL,
                    left                INTEGER,
                    right               INTEGER,
                    double              INTEGER,
                    level               INTEGER,
                    cl                  INTEGER,
                    ce                  INTEGER,
                    rce                 INTEGER,
                    lce                 INTEGER,
                    dce                 INTEGER,
                    bbbv                INTEGER,
                    bbbv_solved         INTEGER,
                    zini                INTEGER,
                    flag                INTEGER,
                    path                REAL,
                    start_time          INTEGER,
                    end_time            INTEGER,
                    mode                INTEGER,
                    software            TEXT,
                    player_identifier   TEXT,
                    race_identifier     TEXT,
                    unique_identifier   TEXT,
                    is_official         INTEGER,
                    is_fair             INTEGER,
                    op                  INTEGER,
                    isl                 INTEGER,
                    pluck               REAL,
                    board               TEXT
                )
            """)
            # 录像数据子表（与 history 分离，避免 BLOB 拖慢元数据查询）
            cursor.execute("""
                CREATE TABLE replay_data (
                    replay_id  INTEGER PRIMARY KEY,
                    raw_data   BLOB,
                    compressed INTEGER DEFAULT 0
                )
            """)
            conn.commit()
            # 确保查询索引存在
            ensure_indexes(conn)
            ensure_tables(conn)
            self.logger.info(f"Database created: {db_path}")

    # ── 事件处理 ──────────────────────────────────────────

    def _on_video_save(self, event: GameFinishedEvent) -> None:
        data: dict[str, Any] = msgspec.structs.asdict(event)
        if isinstance(data.get("board"), list):
            import json
            data["board"] = json.dumps(data["board"], separators=(",", ":"))
        data.pop("timestamp", None)
        # raw_data/compressed 不写入 history 元数据表，拆到录像数据子表
        raw_data = data.pop("raw_data", None)
        data.pop("compressed", None)
        threshold = int(getattr(
            getattr(self, "other_info", None),
            "min_replay_solved_percent", 0))
        bbbv = data.get("bbbv")
        solved = data.get("bbbv_solved")
        if threshold > 0 and isinstance(bbbv, int) and bbbv > 0 \
                and isinstance(solved, int) and solved * 100 < threshold * bbbv:
            raw_data = None
        # board 以每格一个字符的 ASCII 字符串落盘；查询无需 UDF 展开。
        from .board_codec import board_json_to_ascii
        board_ascii = board_json_to_ascii(data.get("board"))
        if board_ascii is not None:
            data["board"] = board_ascii
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())

        # 单条压缩在写线程外完成，写锁只覆盖元数据、暂存数据及索引落盘。
        import zlib
        staged = zlib.compress(raw_data, 6) if raw_data is not None else None

        def save(conn):
            cursor = conn.execute(
                f"INSERT INTO history ({columns}) VALUES ({placeholders})", data)
            replay_id = cursor.lastrowid
            if replay_id is None:
                raise RuntimeError("插入 history 后未取得 replay_id")
            if raw_data is not None:
                write_record(conn, replay_id, raw_data, staged=staged)

        execute_write(self.data_dir / "history.db", save)
        worker = getattr(self, "_migrate_worker", None)
        if worker is not None:
            worker.notify()
        self.logger.info(
            f"Saved: game_state={event.game_state} time={event.rtime:.1f}s")
        self.video_save_over.emit()

    # ═══════════════════════════════════════════════════════════════════
    # HistoryService 接口实现
    # ═══════════════════════════════════════════════════════════════════

    def query_records(
        self,
        limit: int = 100,
        offset: int = 0,
        level: int | None = None,
    ) -> list[GameRecord]:
        """查询游戏记录"""
        db_path = self.data_dir / "history.db"
        with db_connection(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if level is not None:
                cursor.execute(
                    """
                    SELECT * FROM history
                    WHERE level = ?
                    ORDER BY replay_id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (level, limit, offset),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM history
                    ORDER BY replay_id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )
            rows = cursor.fetchall()
            return [GameRecord(
                replay_id=row["replay_id"],
                rtime=row["rtime"],
                level=row["level"],
                bbbv=row["bbbv"],
                bbbv_solved=row["bbbv_solved"],
                left=row["left"],
                right=row["right"],
                double=row["double"],
                cl=row["cl"],
                ce=row["ce"],
                flag=row["flag"],
                game_state=row["game_state"],
                mode=row["mode"],
                software=row["software"] or "",
                start_time=row["start_time"],
                end_time=row["end_time"],
                nf=bool(row["nf"]),
                row=row["row"],
                column=row["column"],
                mine_num=row["mine_num"],
                zini=row["zini"],
            ) for row in rows]

    def get_record_count(self, level: int | None = None) -> int:
        """获取记录总数"""
        db_path = self.data_dir / "history.db"
        with db_connection(db_path) as conn:
            cursor = conn.cursor()
            if level is not None:
                cursor.execute(
                    "SELECT COUNT(*) FROM history WHERE level = ?", (level,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM history")
            return cursor.fetchone()[0]

    def get_last_record(self) -> GameRecord | None:
        """获取最近一条记录"""
        records = self.query_records(limit=1)
        return records[0] if records else None

    def delete_record(self, record_id: int) -> bool:
        """删除指定记录（元数据 + 录像数据同一事务）"""
        db_path = self.data_dir / "history.db"
        deleted = execute_write(db_path, lambda conn: delete_record_tx(conn, record_id))
        if deleted:
            self.logger.info(f"Deleted record: {record_id}")
            worker = getattr(self, "_migrate_worker", None)
            if worker is not None:
                worker.request_compaction()
        return deleted

    def raw_query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """
        直接执行 SQL 查询

        Args:
            sql: SQL 查询语句（使用 ? 作为参数占位符）
            params: 参数元组

        Returns:
            字典列表
        """
        db_path = self.data_dir / "history.db"
        with db_connection(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def raw_query_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        """
        执行 SQL 查询并返回单条结果
        """
        results = self.raw_query(sql, params)
        return results[0] if results else None

    def _on_config_changed(self, name: str, value: Any) -> None:
        if name == "float_decimals":
            # widget 可能在配置变更时尚未创建（如启用前修改配置）
            self.run_on_widget(
                lambda widget, decimals: widget.set_float_decimals(decimals),
                value)
        elif name == "board_preview":
            self.run_on_widget(
                lambda widget, enabled: widget.set_board_preview_enabled(enabled),
                bool(value))
        elif name == "saved_custom_functions":
            from .db import set_custom_script
            set_custom_script(value or "")
        elif name == "min_replay_solved_percent":
            worker = getattr(self, "_migrate_worker", None)
            if worker is not None:
                worker.request_cleanup(value)

    def _apply_runtime_config(self) -> None:
        """把配置中的界面相关设置同步到已创建的界面

        设置对话框点确定时用 apply_pending(silent=True) 写入 other_info，
        不会触发 _on_config_changed，所以保存后需要在这里补一次同步，
        让「局面预览」这类开关立即生效，不必重新加载插件。
        """
        info = self.other_info
        if info is None:
            return
        worker = getattr(self, "_migrate_worker", None)
        if worker is not None:
            worker.request_cleanup(info.min_replay_solved_percent)

        def apply(widget: HistoryMainWidget) -> None:
            widget.set_board_preview_enabled(bool(info.board_preview))
            widget.set_float_decimals(info.float_decimals)

        self.run_on_widget(apply)

    def save_config(self) -> None:
        """保存配置，并同步到当前界面（见 _apply_runtime_config）"""
        super().save_config()
        self._apply_runtime_config()
