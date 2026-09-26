"""
query_builder 模块单元测试

覆盖：枚举显示名转换、datetime 多格式解析、in/not-in 列表、
括号配对校验、非法字段名白名单、含引号值的参数化、排序白名单
"""
from __future__ import annotations

import sqlite3

import pytest
from PySide6.QtCore import QCoreApplication

from plugins.history.models import (
    CompareSymbol, LogicSymbol, HistoryData,
)
from plugins.history.query_builder import build_where, build_order_by

_translate = QCoreApplication.translate

# 比较符显示名（与 CompareSymbol 枚举顺序一致）
EQUAL = CompareSymbol.display_names()[0]        # 等于
GREATER = CompareSymbol.display_names()[2]      # 大于
LESS = CompareSymbol.display_names()[3]         # 小于
CONTAINS = CompareSymbol.display_names()[6]     # 包含（in）
NOT_CONTAINS = CompareSymbol.display_names()[7]  # 不包含（not in）
AND = LogicSymbol.display_names()[0]            # 与
OR = LogicSymbol.display_names()[1]             # 或
ASC = _translate("Form", "升序")
DESC = _translate("Form", "降序")


def make_field_types(extra: dict | None = None) -> dict:
    """构造字段类型样本映射（与 main_widget._get_field_types 一致）"""
    types = {f: HistoryData.get_field_value(f) for f in HistoryData.fields()}
    if extra:
        types.update(extra)
    return types


def make_known_fields(extra: set[str] | None = None) -> set[str]:
    fields = set(HistoryData.fields())
    if extra:
        fields |= extra
    return fields


def row(field: str, compare: str, value: str, logic: str = AND,
        left_bracket: str = "", right_bracket: str = "") -> dict:
    return {
        "left_bracket": left_bracket,
        "field": field,
        "compare": compare,
        "value": value,
        "right_bracket": right_bracket,
        "logic": logic,
    }


class TestBuildWhere:
    """测试 build_where"""

    def test_empty_rows(self):
        sql, params = build_where([], make_known_fields())
        assert sql == ""
        assert params == []

    def test_simple_equality(self):
        rows = [row("level", EQUAL, "5")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert "level = ?" in sql
        assert params == ["5"]

    def test_enum_display_name_converted(self):
        """枚举显示名 → 枚举值（参数绑定）"""
        from shared_types.enums import GameMode
        display = GameMode.Standard.display_name
        rows = [row("mode", EQUAL, display)]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert "mode = ?" in sql
        assert params == [str(GameMode.Standard.value)]

    def test_enum_unmatched_value_passthrough(self):
        """枚举未匹配显示名时原值透传（与旧版行为一致）"""
        rows = [row("mode", EQUAL, "unknown_mode")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert "mode = ?" in sql
        assert params == ["unknown_mode"]

    def test_datetime_full_micro_format(self):
        """%Y-%m-%d %H:%M:%S.%f 格式 → µs 时间戳"""
        from datetime import datetime
        value = "2024-01-15 10:30:00.123456"
        rows = [row("start_time", GREATER, value)]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        expected = int(datetime.strptime(
            value, "%Y-%m-%d %H:%M:%S.%f").timestamp() * 1_000_000)
        assert "start_time > CAST(? AS INTEGER)" in sql
        assert params == [expected]

    def test_datetime_plain_format(self):
        """%Y-%m-%d %H:%M:%S 格式 → µs 时间戳"""
        from datetime import datetime
        value = "2024-01-15 10:30:00"
        rows = [row("end_time", LESS, value)]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        expected = int(datetime.strptime(
            value, "%Y-%m-%d %H:%M:%S").timestamp() * 1_000_000)
        assert params == [expected]

    def test_datetime_microsecond_timestamp(self):
        """纯数字 → 直接作为 µs 时间戳"""
        ts = 1705305000123456
        rows = [row("start_time", EQUAL, str(ts))]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert params == [ts]

    def test_datetime_invalid_raises(self):
        rows = [row("start_time", EQUAL, "not-a-date")]
        with pytest.raises(ValueError, match="不是合法的日期时间"):
            build_where(rows, make_known_fields(), make_field_types())

    def test_in_list_numeric(self):
        """in 列表：数值展开为 CAST 占位符（保证按数值比较）"""
        rows = [row("mine_num", CONTAINS, "3,5")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert "mine_num in (CAST(? AS INTEGER),CAST(? AS INTEGER))" in sql
        assert params == ["3", "5"]

    def test_not_in_list_enum(self):
        """not in 列表：枚举显示名逐值转换"""
        from shared_types.enums import GameMode
        d1 = GameMode.Standard.display_name
        rows = [row("mode", NOT_CONTAINS, f"{d1}")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert "mode not in (?)" in sql
        assert params == [str(GameMode.Standard.value)]

    def test_in_list_string(self):
        rows = [row("software", CONTAINS, "a,b")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert "software in (?,?)" in sql
        assert params == ["a", "b"]

    def test_in_list_empty_string_field(self):
        """空 in 列表（字符串字段）：恒假条件 0 = 1"""
        rows = [row("software", CONTAINS, "")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert "0 = 1" in sql
        assert params == []

    def test_in_list_empty_enum_field(self):
        """空 in 列表（枚举字段）：恒假条件 0 = 1"""
        rows = [row("mode", CONTAINS, "")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert "0 = 1" in sql
        assert params == []

    def test_in_list_empty_datetime_field(self):
        """空 in 列表（datetime 字段）：恒假条件 0 = 1"""
        rows = [row("start_time", CONTAINS, "")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert "0 = 1" in sql
        assert params == []

    def test_in_list_numeric_empty_still_error(self):
        """数值字段空 in 列表保持旧行为：报"不是数字"错误"""
        rows = [row("mine_num", CONTAINS, "")]
        with pytest.raises(ValueError, match="不是数字"):
            build_where(rows, make_known_fields(), make_field_types())

    def test_in_list_numeric_invalid_member(self):
        rows = [row("mine_num", CONTAINS, "3,abc")]
        with pytest.raises(ValueError, match="不是数字"):
            build_where(rows, make_known_fields(), make_field_types())

    def test_quote_value_parameterized(self):
        """含单引号的值必须参数化，不得进入 SQL 文本"""
        rows = [row("player_identifier", EQUAL,
                    "robert'); DROP TABLE history;--")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        # 恶意 payload 不得出现在 SQL 文本中
        assert "DROP TABLE" not in sql
        assert "player_identifier = ?" in sql
        assert params == ["robert'); DROP TABLE history;--"]

    def test_surrounding_quotes_stripped(self):
        """兼容旧版手输引号定界：成对包裹的单引号被剥离"""
        rows = [row("software", EQUAL, "'ms'")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert params == ["ms"]

    def test_unknown_field_raises_with_row(self):
        """字段不在白名单 → ValueError（带行号与字段名）"""
        rows = [row("level", EQUAL, "1"),
                row("evil_field", EQUAL, "1")]
        with pytest.raises(ValueError, match="第1行.*evil_field"):
            build_where(rows, make_known_fields(), make_field_types())

    def test_computed_column_in_whitelist(self):
        """已加载计算列名在白名单中（int 型样本值，占位符带 CAST）"""
        rows = [row("bbbvs", GREATER, "0.5")]
        known = make_known_fields({"bbbvs"})
        types = make_field_types({"bbbvs": 0})  # int 计算列样本
        sql, params = build_where(rows, known, types)
        assert "bbbvs > CAST(? AS INTEGER)" in sql
        assert params == ["0.5"]

    def test_bracket_right_exceeds_left(self):
        """右括号数量超过左括号 → 立即报错"""
        rows = [row("level", EQUAL, "1", right_bracket=")")]
        with pytest.raises(ValueError, match="右括号数量大于左括号"):
            build_where(rows, make_known_fields(), make_field_types())

    def test_bracket_final_mismatch(self):
        """结尾左右括号数量不等 → 报错"""
        rows = [row("level", EQUAL, "1", left_bracket="(")]
        with pytest.raises(ValueError, match="左括号数量和右括号数量不匹配"):
            build_where(rows, make_known_fields(), make_field_types())

    def test_brackets_balanced(self):
        """括号配对正常时片段含括号"""
        rows = [
            row("level", EQUAL, "1", logic=OR, left_bracket="("),
            row("mode", EQUAL, "1", logic=OR, right_bracket=")"),
        ]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert "(" in sql and ")" in sql
        assert " or " in sql
        assert len(params) == 2

    def test_double_brackets_counted(self):
        """(( 计为两个左括号"""
        rows = [
            row("level", EQUAL, "1", left_bracket="(("),
            row("mode", EQUAL, "1", logic=OR),
            row("rtime", GREATER, "0", logic=OR, right_bracket="))"),
        ]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert "(( level = ?" in sql
        assert ")) " in sql

    def test_logic_connects_non_last_row(self):
        """与旧版一致：非最后一行即使下一行为空也追加逻辑连接符"""
        rows = [row("level", EQUAL, "1"), {"field": "", "compare": ""}]
        sql, _ = build_where(rows, make_known_fields(), make_field_types())
        assert " and " in sql

    def test_numeric_int_field_cast(self):
        """数值(int)字段等值/比较：占位符为 CAST(? AS INTEGER)"""
        rows = [row("mine_num", GREATER, "3")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert "mine_num > CAST(? AS INTEGER)" in sql
        assert params == ["3"]

    def test_numeric_float_field_cast(self):
        """数值(float)字段比较：占位符为 CAST(? AS REAL)"""
        types = make_field_types()
        float_field = next(
            f for f, t in types.items() if isinstance(t, float))
        rows = [row(float_field, GREATER, "0.7")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert f"{float_field} > CAST(? AS REAL)" in sql
        assert params == ["0.7"]

    def test_datetime_field_cast(self):
        """datetime 字段比较：占位符为 CAST(? AS INTEGER)（µs 时间戳）"""
        rows = [row("start_time", LESS, "2024-01-15 10:30:00")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert "start_time < CAST(? AS INTEGER)" in sql
        assert params == [int(
            __import__("datetime").datetime.strptime(
                "2024-01-15 10:30:00", "%Y-%m-%d %H:%M:%S").timestamp()
            * 1_000_000)]

    def test_datetime_in_list_cast(self):
        """datetime in 列表：每个占位符都有 CAST"""
        rows = [row(
            "start_time", CONTAINS,
            "2024-01-15 10:30:00,2024-01-16 10:30:00")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert sql.count("CAST(? AS INTEGER)") == 2
        assert len(params) == 2

    def test_enum_field_no_cast(self):
        """枚举字段（字符串值）保持裸 ? 占位符，不包 CAST"""
        rows = [row("level", GREATER, "3")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        assert "level > ?" in sql
        assert "CAST" not in sql
        assert params == ["3"]

    def test_string_field_no_cast(self):
        """字符串字段保持裸 ? 占位符，不包 CAST"""
        rows = [row("software", EQUAL, "a")]
        sql, _ = build_where(rows, make_known_fields(), make_field_types())
        assert "software = ?" in sql
        assert "CAST" not in sql


class TestBuildOrderBy:
    """测试 build_order_by"""

    def test_empty_rows(self):
        assert build_order_by([], make_known_fields()) == ""

    def test_single_field_asc(self):
        sql = build_order_by(
            [{"field": "start_time", "order": ASC}], make_known_fields())
        assert sql == " ORDER BY start_time ASC"

    def test_single_field_desc(self):
        sql = build_order_by(
            [{"field": "rtime", "order": DESC}], make_known_fields())
        assert sql == " ORDER BY rtime DESC"

    def test_multiple_fields(self):
        sql = build_order_by(
            [{"field": "level", "order": DESC},
             {"field": "rtime", "order": ASC}],
            make_known_fields(),
        )
        assert sql == " ORDER BY level DESC, rtime ASC"

    def test_unknown_field_raises_with_row(self):
        rows = [{"field": "not_a_field", "order": ASC}]
        with pytest.raises(ValueError, match="第0行.*not_a_field"):
            build_order_by(rows, make_known_fields())

    def test_computed_column_in_whitelist(self):
        sql = build_order_by(
            [{"field": "bbbvs", "order": DESC}],
            make_known_fields({"bbbvs"}),
        )
        assert sql == " ORDER BY bbbvs DESC"


class TestSqlParameterRoundTrip:
    """端到端：构建的 SQL 在真实 SQLite 中执行验证参数化正确性"""

    def test_where_and_order_round_trip(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE history (replay_id INTEGER, level INTEGER, rtime REAL)")
        conn.executemany(
            "INSERT INTO history VALUES (?, ?, ?)",
            [(1, 3, 10.0), (2, 5, 20.0), (3, 5, 5.0)],
        )
        rows = [row("level", EQUAL, "5")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        order = build_order_by(
            [{"field": "rtime", "order": ASC}], make_known_fields())
        cursor = conn.execute(
            f"SELECT replay_id FROM history WHERE {sql}{order}", params)
        results = cursor.fetchall()
        assert results == [(3,), (2,)]
        conn.close()

    def test_malicious_value_cannot_inject(self):
        """注入 payload 作为参数值执行不会破坏 SQL"""
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE history (replay_id INTEGER, player_identifier TEXT)")
        conn.executemany(
            "INSERT INTO history VALUES (?, ?)",
            [(1, "a"), (2, "b")],
        )
        rows = [row(
            "player_identifier", EQUAL,
            "x' OR '1'='1') UNION SELECT replay_id FROM history--")]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        cursor = conn.execute(
            f"SELECT replay_id FROM history WHERE {sql}", params)
        # 无匹配行（payload 被当作字面字符串值比较）
        assert cursor.fetchall() == []
        conn.close()

    def test_computed_column_cast_round_trip(self):
        """关键回归：计算列（无列亲和性的子查询别名）过滤必须命中

        旧 bug 场景：计算列 `(bbbv_solved*1.0/rtime) AS "bbbvs"` 无
        列亲和性，字符串参数绑定导致按文本比较恒空；CAST 后按数值比较。
        """
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE history (replay_id INTEGER, "
            "bbbv_solved REAL, rtime REAL)")
        conn.executemany(
            "INSERT INTO history VALUES (?, ?, ?)",
            [(1, 2.0, 10.0),   # bbbvs = 0.2
             (2, 0.5, 0.5),    # bbbvs = 1.0
             (3, 0.9, 0.9)],   # bbbvs = 1.0
        )
        # 模拟 main_widget.load_data 的计算列子查询
        subquery = ('SELECT *, (bbbv_solved*1.0/rtime) AS "bbbvs" '
                    "FROM history")
        known = make_known_fields({"bbbvs"})
        types = make_field_types({"bbbvs": 0.5})  # float 类型样本
        rows = [row("bbbvs", GREATER, "0.7")]
        sql, params = build_where(rows, known, types)
        # 占位符已显式 CAST 为 REAL
        assert "bbbvs > CAST(? AS REAL)" in sql
        cursor = conn.execute(
            f'SELECT replay_id FROM ({subquery}) WHERE {sql}', params)
        # 修复后按数值比较命中 2 行（旧 bug 场景命中 0 行）
        assert sorted(cursor.fetchall()) == [(2,), (3,)]

        # 对照：裸字符串参数对无亲和性列恒空（旧 bug 行为）
        cursor = conn.execute(
            f'SELECT replay_id FROM ({subquery}) WHERE bbbvs > ?',
            ("0.7",))
        assert cursor.fetchall() == []
        conn.close()

    def test_datetime_cast_round_trip(self):
        """datetime 计算列/物理列 CAST(? AS INTEGER) 参数绑定命中"""
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE history (replay_id INTEGER, start_time INTEGER)")
        ts = 1705305000_000000  # µs 时间戳
        conn.executemany(
            "INSERT INTO history VALUES (?, ?)",
            [(1, ts), (2, ts + 1_000_000)],
        )
        rows = [row("start_time", GREATER, str(ts))]
        sql, params = build_where(
            rows, make_known_fields(), make_field_types())
        cursor = conn.execute(
            f"SELECT replay_id FROM history WHERE {sql}", params)
        assert cursor.fetchall() == [(2,)]
        conn.close()


class TestComputedColumnName:
    """计算列名统一校验（validate_column_name / from_dict / from_json）"""

    def test_valid_names(self):
        """默认配置中的列名与常见合法名均通过"""
        from plugins.history.computed_column import validate_column_name
        assert validate_column_name("bbbvs") is None
        assert validate_column_name("距今天数") is None
        assert validate_column_name("_x1") is None
        assert validate_column_name("A1_b2c3") is None

    def test_invalid_names(self):
        from plugins.history.computed_column import validate_column_name
        # 空名
        assert validate_column_name("") == "列名不能为空"
        # 数字开头
        error = validate_column_name("1abc")
        assert error is not None and "非法字符" in error
        # 含连字符（SQL 注入常用载体）
        error = validate_column_name("a-b")
        assert error is not None and "非法字符" in error
        # 含空格
        error = validate_column_name("a b")
        assert error is not None and "非法字符" in error
        # 含单引号
        error = validate_column_name("a'b")
        assert error is not None and "非法字符" in error

    def test_reserved_name_total_count(self):
        """total_count 是查询内部窗口别名，禁止用户创建"""
        from plugins.history.computed_column import validate_column_name
        error = validate_column_name("total_count")
        assert error is not None and "保留字" in error

    def test_from_dict_rejects_invalid(self):
        """from_dict 非法列名抛 ValueError，错误信息含列名"""
        from plugins.history.computed_column import ComputedColumn
        with pytest.raises(ValueError, match="a-b"):
            ComputedColumn.from_dict(
                {"name": "a-b", "expression": "bbbv / rtime"})

    def test_from_dict_rejects_reserved(self):
        from plugins.history.computed_column import ComputedColumn
        with pytest.raises(ValueError, match="保留字"):
            ComputedColumn.from_dict(
                {"name": "total_count", "expression": "1"})

    def test_from_dict_accepts_valid(self):
        from plugins.history.computed_column import ComputedColumn
        col = ComputedColumn.from_dict(
            {"name": "bbbvs", "expression": "py_safe_div(bbbv_solved,rtime)",
             "result_type": "float"})
        assert col.name == "bbbvs"

    def test_from_json_skips_invalid(self):
        """配置加载路径容错：非法列名跳过、合法列名保留"""
        from plugins.history.computed_column import ComputedColumn
        import json as _json
        items = _json.dumps([
            {"name": "bbbvs", "expression": "1"},
            {"name": "a-b", "expression": "2"},
            {"name": "距今天数", "expression": "3"},
        ], ensure_ascii=False)
        columns = ComputedColumn.from_json(items)
        assert [c.name for c in columns] == ["bbbvs", "距今天数"]

    def test_reserved_name_cannot_shadow_query_alias(self):
        """端到端：保留字列名被拒后，SELECT 拼接不会产生重复列名歧义"""
        from plugins.history.computed_column import ComputedColumn
        with pytest.raises(ValueError):
            ComputedColumn.from_dict(
                {"name": "total_count", "expression": "bbbv"})
