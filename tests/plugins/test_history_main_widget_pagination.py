"""历史记录分页在数据减少后保持总数和表格一致。"""
from __future__ import annotations

import json
import sqlite3

import pytest

from plugins.history.main_widget import HistoryMainWidget


@pytest.fixture
def history_widget(qtbot, tmp_path):
    db_path = tmp_path / "history.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE history (replay_id INTEGER PRIMARY KEY)")
        conn.executemany(
            "INSERT INTO history (replay_id) VALUES (?)",
            ((i,) for i in range(1, 26)),
        )
    config_path = tmp_path / "columns.json"
    config_path.write_text(json.dumps(["replay_id"]), encoding="utf-8")
    widget = HistoryMainWidget(db_path, config_path, page_size="10")
    qtbot.addWidget(widget)
    # 启动期不再自动查；恢复完配置后由插件统一触发一次。
    assert widget.table.model._data == []
    widget.run_startup_query()
    assert_page(widget, 1, 3, "共25行,3页", list(range(25, 15, -1)))
    return widget, db_path


def assert_page(widget, page, maximum, label, ids):
    assert widget.page_spin.value() == page
    assert widget.page_spin.maximum() == maximum
    assert widget.limit_label.text() == label
    assert [row.replay_id for row in widget.table.model._data] == ids


def test_deleting_last_page_falls_back_without_overwriting_rows(history_widget):
    widget, db_path = history_widget
    widget.page_spin.setValue(3)
    assert_page(widget, 3, 3, "共25行,3页", list(range(5, 0, -1)))
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM history WHERE replay_id <= 5")
    widget.load_data()
    assert_page(widget, 2, 2, "共20行,2页", list(range(15, 5, -1)))


def test_increasing_page_size_falls_back_to_last_page(history_widget):
    widget, _ = history_widget
    widget.page_spin.setValue(3)
    widget.one_page_combo.setCurrentText("20")
    assert_page(widget, 2, 2, "共25行,2页", list(range(5, 0, -1)))


def test_filter_with_out_of_range_offset_keeps_filtered_count(history_widget):
    widget, _ = history_widget
    widget.page_spin.setValue(3)
    widget._filter_rows = [{"field": "replay_id", "compare": "小于等于", "value": "12", "logic": "与"}]
    widget.load_data()
    assert_page(widget, 2, 2, "共12行,2页", [2, 1])


def test_or_filter_respects_page_boundaries(history_widget):
    widget, _ = history_widget
    widget._filter_rows = [
        {"field": "replay_id", "compare": "小于等于", "value": "12", "logic": "或"},
        {"field": "replay_id", "compare": "大于等于", "value": "20", "logic": "与"},
    ]
    widget.load_data()
    assert_page(widget, 1, 2, "共18行,2页", [25, 24, 23, 22, 21, 20, 12, 11, 10, 9])
    widget.page_spin.setValue(2)
    assert_page(widget, 2, 2, "共18行,2页", list(range(8, 0, -1)))


def test_preview_uses_replay_id_when_column_is_hidden(history_widget):
    widget, _ = history_widget
    table = widget.table
    table.model.update_show_fields(["board"])
    index = table.model.index(0, 0)
    assert table._preview_key(index) == (0, 0, 25)


def test_load_data_does_not_use_window_count_on_full_table(history_widget, monkeypatch):
    """大表禁止 COUNT(*) OVER() 触发全表 UDF/计算列求值。"""
    from plugins.history import main_widget

    widget, _ = history_widget
    executed = []

    real_db_connection = main_widget.db_connection

    class _SpyCursor:
        def __init__(self, inner):
            self._inner = inner

        def execute(self, sql, *args, **kwargs):
            executed.append(str(sql))
            return self._inner.execute(sql, *args, **kwargs)

        def fetchall(self):
            return self._inner.fetchall()

        def fetchone(self):
            return self._inner.fetchone()

    class _SpyConnection:
        def __init__(self, inner, context=None):
            self._inner = inner
            self._context = context

        def cursor(self):
            return _SpyCursor(self._inner.cursor())

        def execute(self, sql, *args, **kwargs):
            executed.append(str(sql))
            return self._inner.execute(sql, *args, **kwargs)

        @property
        def row_factory(self):
            return self._inner.row_factory

        @row_factory.setter
        def row_factory(self, value):
            self._inner.row_factory = value

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self._context.__exit__(*args) if self._context else None

    def spy(*args, **kwargs):
        context = real_db_connection(*args, **kwargs)
        return _SpyConnection(context.__enter__(), context)

    monkeypatch.setattr(main_widget, "db_connection", spy)
    widget.load_data()
    assert not any("COUNT(*) OVER()" in sql.upper() for sql in executed)
    assert any("SELECT COUNT(*) FROM" in sql.upper() for sql in executed)
    page_sql = next(sql for sql in executed if "LIMIT ? OFFSET ?" in sql)
    assert "replay_id IN" in page_sql


def test_startup_query_runs_once(history_widget, monkeypatch):
    widget, _ = history_widget
    calls = []
    monkeypatch.setattr(widget, "_on_query", lambda: calls.append(True))
    widget._startup_query_pending = True
    widget.run_startup_query()
    widget.run_startup_query()
    assert len(calls) == 1


def test_delete_wake_signal_is_forwarded_to_plugin(history_widget):
    widget, _ = history_widget
    seen = []
    widget.compaction_requested.connect(lambda: seen.append(True))
    widget.table.compaction_requested.emit()
    assert seen == [True]


def test_empty_filtered_result_clears_table_and_resets_page(history_widget):
    widget, _ = history_widget
    widget.page_spin.setValue(3)
    widget._filter_rows = [{"field": "replay_id", "compare": "小于", "value": "0", "logic": "与"}]
    widget.load_data()
    assert_page(widget, 1, 1, "共0行,0页", [])


def test_missing_database_clears_previously_loaded_rows(history_widget):
    widget, db_path = history_widget
    widget.page_spin.setValue(3)
    widget._db_path = db_path.with_name("missing.db")
    widget.load_data()
    assert_page(widget, 1, 1, "共0行,0页", [])
