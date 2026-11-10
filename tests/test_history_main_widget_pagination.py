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
