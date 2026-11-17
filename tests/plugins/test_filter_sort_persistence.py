"""历史筛选/排序配置的跨语言与稳定编号持久化兼容性。"""

from __future__ import annotations

import json

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox

from plugins.history.delegates import ComboBoxDelegate
from plugins.history.main_widget import HistoryMainWidget
from plugins.history.models import CompareSymbol, LogicSymbol, SortOrder
from plugins.history.query_builder import build_order_by, build_where
from plugins.history.table_views import FilterModel, SortModel


def _field_types() -> dict:
    from plugins.history.models import HistoryData

    return {f: HistoryData.get_field_value(f) for f in HistoryData.fields()}


# 旧版配置保存的译文 → 期望的稳定编号（覆盖全部内置语言）
_LEGACY_COMPARE_CASES = [
    # en_US（报告过弹窗的 equals 场景）
    ("equals", 0), ("does not equal", 1), ("greater than", 2),
    ("less than", 3), ("greater than or equal to", 4),
    ("less than or equal to", 5), ("in list", 6), ("not in list", 7),
    ("Contains substring", 8), ("Does not contain substring", 9),
    # de_DE
    ("Gleich", 0), ("Ungleich", 1), ("Größer als", 2), ("Kleiner als", 3),
    ("Größer oder gleich", 4), ("Kleiner oder gleich", 5),
    ("Enthält", 6), ("Enthält nicht", 7),
    ("Enthält Teilzeichenfolge", 8), ("Enthält keine Teilzeichenfolge", 9),
    # ja_JP
    ("等しい", 0), ("等しくない", 1), ("より大", 2), ("より小", 3),
    ("以上", 4), ("以下", 5), ("含む", 6), ("含まない", 7),
    ("部分文字列を含む", 8), ("部分文字列を含まない", 9),
    # pl_PL
    ("Równe", 0), ("Różne", 1), ("Większe niż", 2), ("Mniejsze niż", 3),
    ("Większe lub równe niż", 4), ("Mniejsze lub równe niż", 5),
    ("Zawiera", 6), ("Nie zawiera", 7),
    ("Zawiera podciągu", 8), ("Nie zawiera podciągu", 9),
    # 源语言与稳定编号
    ("等于", 0), ("不等于", 1), ("0", 0), ("9", 9),
]


@pytest.mark.parametrize(("legacy", "expected"), _LEGACY_COMPARE_CASES)
def test_legacy_compare_names_resolve_to_stable_values(legacy, expected):
    assert CompareSymbol.from_display_name(legacy).value == expected
    assert CompareSymbol.to_stable(legacy) == str(expected)


@pytest.mark.parametrize(("legacy", "expected"), [
    ("and", 0), ("or", 1), ("与", 0), ("或", 1),
    ("かつ", 0), ("または", 1), ("0", 0), ("1", 1),
])
def test_legacy_logic_names_resolve_to_stable_values(legacy, expected):
    assert LogicSymbol.from_display_name(legacy).value == expected
    assert LogicSymbol.to_stable(legacy) == str(expected)


@pytest.mark.parametrize(("legacy", "expected_sql"), [
    ("升序", "ASC"), ("Ascending", "ASC"), ("Aufsteigend", "ASC"),
    ("昇順", "ASC"), ("Rosnąco", "ASC"),
    ("降序", "DESC"), ("Descending", "DESC"), ("Absteigend", "DESC"),
    ("降順", "DESC"), ("Malejąco", "DESC"), ("0", "ASC"), ("1", "DESC"),
])
def test_legacy_sort_order_names_resolve(legacy, expected_sql):
    assert SortOrder.from_text(legacy).to_sql == expected_sql
    assert SortOrder.to_stable(legacy) is not None


def test_build_where_accepts_legacy_english_config():
    """英文环境下保存的 equals/and 在未安装英文翻译器时也能构建查询。"""
    rows = [
        {"left_bracket": "", "field": "rtime", "compare": "equals",
         "value": "10", "right_bracket": "", "logic": "and"},
        {"left_bracket": "", "field": "flag", "compare": "greater than",
         "value": "5", "right_bracket": "", "logic": "or"},
    ]
    sql, params = build_where(rows, {"rtime", "flag"}, _field_types())
    assert " rtime = " in sql
    assert " and " in sql
    assert " flag > " in sql
    assert params == ["10", "5"]


def test_build_where_accepts_stable_indices():
    rows = [
        {"left_bracket": "", "field": "rtime", "compare": "0",
         "value": "10", "right_bracket": "", "logic": "1"},
        {"left_bracket": "", "field": "flag", "compare": "0",
         "value": "5", "right_bracket": "", "logic": "0"},
    ]
    sql, params = build_where(rows, {"rtime", "flag"}, _field_types())
    assert " rtime = " in sql
    assert " or " in sql
    assert params == ["10", "5"]


def test_build_where_unknown_compare_has_context():
    rows = [{
        "left_bracket": "", "field": "rtime", "compare": "bogus-op",
        "value": "10", "right_bracket": "", "logic": "and",
    }]
    with pytest.raises(ValueError) as excinfo:
        build_where(rows, {"rtime"}, _field_types())
    message = str(excinfo.value)
    assert "比较符" in message
    assert "bogus-op" in message


def test_build_where_missing_logic_defaults_to_and():
    rows = [{
        "left_bracket": "", "field": "rtime", "compare": "0",
        "value": "10", "right_bracket": "", "logic": "",
    }]
    sql, _ = build_where(rows, {"rtime"}, _field_types())
    assert " rtime = " in sql


def test_build_order_by_legacy_and_stable_values():
    fields = {"rtime"}
    legacy = [{"field": "rtime", "order": "Ascending"}]
    assert build_order_by(legacy, fields) == " ORDER BY rtime ASC"
    stable = [{"field": "rtime", "order": "1"}]
    assert build_order_by(stable, fields) == " ORDER BY rtime DESC"
    # 无法识别时保持旧行为：降序
    unknown = [{"field": "rtime", "order": "sideways"}]
    assert build_order_by(unknown, fields) == " ORDER BY rtime DESC"


def test_set_filter_sort_state_normalizes_legacy_rows(qtbot, tmp_path):
    widget = HistoryMainWidget(tmp_path / "history.db", tmp_path / "fields.json")
    qtbot.addWidget(widget)
    filter_rows = [{"field": "rtime", "compare": "equals", "logic": "and"}]
    sort_rows = [{"field": "rtime", "order": "Ascending"}]
    widget.set_filter_sort_state(json.dumps(filter_rows), json.dumps(sort_rows))
    assert widget._filter_rows == [
        {"field": "rtime", "compare": "0", "logic": "0"}]
    assert widget._sort_rows == [{"field": "rtime", "order": "0"}]


def test_filter_display_formats_stable_values_translated(qtbot, tmp_path):
    widget = HistoryMainWidget(tmp_path / "history.db", tmp_path / "fields.json")
    qtbot.addWidget(widget)
    rows = [{"left_bracket": "", "field": "rtime", "compare": "0",
             "value": "10", "right_bracket": "", "logic": "1"}]
    display = widget._format_filter_display(rows)
    # 中文环境：稳定编号应显示为“等于 … 或”
    assert "等于" in display
    assert "或" in display
    assert " 0 " not in display
    assert widget._format_sort_display(
        [{"field": "rtime", "order": "0"}]) == "rtime 升序"


def test_filter_model_saves_stable_indices(qapp):
    model = FilterModel()
    model.insertRow(0)
    label = CompareSymbol.display_names()[3]
    assert model.setData(model.index(0, FilterModel.COL_COMPARE), label)
    assert model.setData(model.index(0, FilterModel.COL_LOGIC), LogicSymbol.display_names()[1])
    assert model.data(model.index(0, FilterModel.COL_COMPARE),
                      Qt.ItemDataRole.EditRole) == "3"
    assert model.data(model.index(0, FilterModel.COL_LOGIC),
                      Qt.ItemDataRole.EditRole) == "1"
    row = model.get_row_data(0)
    assert row["compare"] == "3"
    assert row["logic"] == "1"
    # 显示仍为当前语言译文
    assert model.data(model.index(0, FilterModel.COL_COMPARE)) == label


def test_sort_model_saves_stable_indices(qapp):
    model = SortModel()
    model.insertRow(0)
    assert model.setData(model.index(0, SortModel.COL_ORDER), "Ascending")
    # 委托/显示读取到当前语言译文，持久化则保存稳定编号
    assert model.data(model.index(0, SortModel.COL_ORDER),
                      Qt.ItemDataRole.EditRole) == SortOrder.display_names()[0]
    assert model.get_row_data(0)["order"] == "0"
    assert model.data(model.index(0, SortModel.COL_ORDER)) == SortOrder.display_names()[0]


def test_combo_delegate_preselects_from_stable_index(qapp):
    model = FilterModel()
    model.insertRow(0)
    label = CompareSymbol.display_names()[5]
    model.setData(model.index(0, FilterModel.COL_COMPARE), label)
    editor = QComboBox()
    editor.addItems(CompareSymbol.display_names())
    delegate = ComboBoxDelegate(CompareSymbol.display_names())
    delegate.setEditorData(editor, model.index(0, FilterModel.COL_COMPARE))
    assert editor.currentText() == label
