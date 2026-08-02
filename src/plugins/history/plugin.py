"""
历史记录插件主体
"""

from __future__ import annotations
from .widgets import HistoryMainWidget
from .compression import compress, decompress
from .computed_column import ComputedColumn
from plugins.services.history import HistoryService, GameRecord
from shared_types.events import GameFinishedEvent, LanguageChangeEvent
from plugin_sdk import (
    BasePlugin, PluginInfo, make_plugin_icon, WindowMode,
    OtherInfoBase, IntConfig, TextConfig, ChoiceConfig,
)

import sqlite3
from pathlib import Path
from typing import Any

from .db import db_connection

import msgspec
from PyQt5.QtCore import QCoreApplication, QThread, pyqtSignal
from PyQt5.QtWidgets import QWidget

_translate = QCoreApplication.translate


class _CompressionMigrateWorker(QThread):
    """后台压缩迁移工作线程，静默处理旧数据"""

    def __init__(self, db_path: Path, batch_size: int = 100, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._batch_size = batch_size

    def run(self):
        with db_connection(self._db_path, register_custom_functions=False) as conn:
            try:
                cursor = conn.cursor()
                # 检查 compressed 列是否存在
                cursor.execute("PRAGMA table_info(history)")
                cols = {row[1] for row in cursor.fetchall()}
                if "compressed" not in cols:
                    return  # schema 还没升级，跳过

                while True:
                    cursor.execute(
                        "SELECT replay_id, raw_data FROM history "
                        "WHERE compressed = 0 AND raw_data IS NOT NULL "
                        "LIMIT ?",
                        (self._batch_size,),
                    )
                    rows = cursor.fetchall()
                    if not rows:
                        break
                    for replay_id, raw_data in rows:
                        if raw_data is None:
                            continue
                        compressed_data = compress(raw_data)
                        cursor.execute(
                            "UPDATE history SET raw_data = ?, compressed = 1 "
                            "WHERE replay_id = ?",
                            (compressed_data, replay_id),
                        )
                    conn.commit()
                # 所有记录压缩完成，VACUUM 回收磁盘空间
                cursor.execute("VACUUM")
            except Exception:
                pass  # 静默失败，下次启动继续


class HistoryConfig(OtherInfoBase):
    """历史记录插件配置"""

    float_decimals = IntConfig(
        default=2,
        label=_translate("Form", "小数位数"),
        description=_translate("Form", "查询窗口中浮点数显示的小数位数"),
        min_value=0,
        max_value=10,
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
        label=_translate("Form", "每页条数"),
        choices=[
            ("10", "10"),
            ("20", "20"),
            ("50", "50"),
            ("100", "100"),
            ("200", "200"),
            ("500", "500"),
            ("1000", "1000"),
        ],
    )


class HistoryPlugin(BasePlugin[HistoryConfig]):
    """
    历史记录插件

    - 后台：监听 GameFinishedEvent，写入 SQLite
    - 界面：提供筛选、分页、播放/导出功能
    - 服务：提供 HistoryService 接口供其他插件查询历史记录
    """
    video_save_over = pyqtSignal()
    _widget: HistoryMainWidget

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name=_translate("Form", "历史记录"),
            description=_translate("Form", "游戏历史记录（SQLite 持久化）"),
            author="ljzloser",
            version="1.0.0",
            icon=make_plugin_icon("#7b1fa2", "\N{SCROLL}"),
            window_mode=WindowMode.TAB,  # type: ignore
            other_info=HistoryConfig,
        )

    def __init__(self, info):
        super().__init__(info)
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

        # 获取配置中的小数位数和每页条数
        float_decimals = 2
        page_size = "50"
        if self.other_info:
            float_decimals = self.other_info.float_decimals
            page_size = self.other_info.page_size

        self._widget = HistoryMainWidget(
            db_path, config_path, float_decimals, page_size)

        # 连接排序和过滤状态变化信号
        self._widget.filter_sort_state_changed.connect(
            self._on_filter_sort_state_changed)

        # 连接列显示配置变化信号
        self._widget.show_fields_changed.connect(
            self._on_show_fields_changed)

        # 连接计算列变化信号
        self._widget.computed_columns_changed.connect(
            self.set_computed_columns)

        # 连接自定义函数变化信号
        self._widget.custom_functions_changed.connect(
            self._on_custom_functions_changed)

        # 初始化计算列（必须在恢复过滤/排序状态之前，否则过滤引用计算列时查不到）
        if self.other_info:
            columns = ComputedColumn.from_json(
                self.other_info.saved_computed_columns)
            self._widget.on_computed_columns_changed(columns, reload=False)
            # 初始化自定义函数脚本
            if self.other_info.saved_custom_functions:
                self._widget.set_custom_functions(
                    self.other_info.saved_custom_functions)

        # 恢复保存的排序和过滤状态
        if self.other_info:
            self._widget.set_filter_sort_state(
                self.other_info.saved_filter,
                self.other_info.saved_sort
            )
            # 恢复保存的列显示配置
            self._widget.restore_show_fields(self.other_info.saved_show_fields)

        self.video_save_over.connect(self._widget.query_button.click)
        return self._widget

    def _on_language_change(self, event: LanguageChangeEvent) -> None:
        self.run_on_gui(self._widget.retranslateUi)

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
        if hasattr(self, '_widget'):
            self._widget.load_data()
        self.register_service(self, protocol=HistoryService)
        self.logger.info("历史记录插件已初始化，HistoryService 已注册")
        # 后台静默压缩旧数据
        self._start_compression_migrate()

    def _start_compression_migrate(self) -> None:
        """启动后台压缩迁移线程"""
        db_path = self.data_dir / "history.db"
        if not db_path.exists():
            return
        # 检查是否有未压缩的记录
        with db_connection(db_path, register_custom_functions=False) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(history)")
            cols = {row[1] for row in cursor.fetchall()}
            if "compressed" not in cols:
                return
            cursor.execute(
                "SELECT COUNT(*) FROM history WHERE compressed = 0 AND raw_data IS NOT NULL"
            )
            count = cursor.fetchone()[0]
        if count > 0:
            self._migrate_worker = _CompressionMigrateWorker(
                db_path)
            self._migrate_worker.start()
            self.logger.info(f"后台压缩迁移启动，待处理 {count} 条记录")

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
        """更新计算列配置"""
        if self.other_info:
            self.other_info.saved_computed_columns = ComputedColumn.to_json(
                columns)
            self.save_config()
        # 通知 widget 刷新
        if hasattr(self, '_widget'):
            self._widget.on_computed_columns_changed(columns)

    # ── 数据库 ──────────────────────────────────────────────

    def _init_db(self) -> None:
        db_path = self.data_dir / "history.db"
        if db_path.exists():
            with db_connection(db_path, register_custom_functions=False) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(history)")
                cols = {row[1] for row in cursor.fetchall()}
                if "game_state" in cols:
                    # 旧 schema 缺少 compressed 列则追加
                    if "compressed" not in cols:
                        cursor.execute(
                            "ALTER TABLE history ADD COLUMN compressed INTEGER DEFAULT 0"
                        )
                        conn.commit()
                        self.logger.info("已添加 compressed 列")
                    # 清理旧版本遗留的 VIEW（改用子查询方式不再需要）
                    cursor.execute("DROP VIEW IF EXISTS history_view")
                    conn.commit()
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
                    board               TEXT,
                    raw_data            BLOB,
                    compressed          INTEGER DEFAULT 0
                )
            """)
            conn.commit()
            self.logger.info(f"Database created: {db_path}")

    # ── 事件处理 ──────────────────────────────────────────

    def _on_video_save(self, event: GameFinishedEvent) -> None:
        data: dict[str, Any] = msgspec.structs.asdict(event)
        if isinstance(data.get("board"), list):
            import json
            data["board"] = json.dumps(data["board"], separators=(",", ":"))
        data.pop("timestamp", None)
        # 压缩 raw_data
        if data.get("raw_data") is not None:
            data["raw_data"] = compress(data["raw_data"])
            data["compressed"] = 1
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())

        db_path = self.data_dir / "history.db"
        with db_connection(db_path, register_custom_functions=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO history ({columns}) VALUES ({placeholders})",
                data,
            )
            conn.commit()
            self.logger.info(
                f"Saved: game_state={event.game_state} time={event.rtime:.1f}s"
            )
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
        """删除指定记录"""
        db_path = self.data_dir / "history.db"
        with db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM history WHERE replay_id = ?", (record_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                self.logger.info(f"Deleted record: {record_id}")
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
            self._widget.set_float_decimals(value)
        elif name == "saved_custom_functions":
            from .db import set_custom_script
            set_custom_script(value or "")
