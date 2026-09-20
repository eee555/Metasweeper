"""
查询条件构建器

将过滤/排序条件行数据转换为参数化的 SQL 片段：
- 字段名走白名单校验（物理字段 + 已加载计算列名），非法字段抛 ValueError
- 值全部使用 ? 占位符绑定，杜绝 SQL 注入
- 枚举显示名→值、datetime→µs 时间戳等转换逻辑与旧版 _gen_filter_str 保持一致
- 「包含 / 不包含」是逗号分隔的多值精确匹配（in / not in）；
  「包含子串 / 不含子串」是文本模糊匹配（like / not like），仅文本字段可用
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PyQt5.QtCore import QCoreApplication

from shared_types.enums import BaseDiaPlayEnum

from .models import CompareSymbol, LogicSymbol

_translate = QCoreApplication.translate

# 日期时间支持的解析格式（与旧版行为一致）
_DATETIME_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S")


def _row_error(row: int, template: str, value: str = "") -> ValueError:
    """构造带行号的校验错误（模板使用 %1/%2 占位，与 UI 提示风格一致）"""
    message = _translate("Form", template).replace("%1", str(row))
    if value:
        message = message.replace("%2", value)
    return ValueError(message)


def _parse_datetime_value(value: str, row: int) -> int:
    """解析单个日期值：µs 时间戳原样使用，日期字符串按多格式解析为 µs 时间戳

    与旧版行为一致：
    - 纯数字 → 直接作为 µs 时间戳
    - "%Y-%m-%d %H:%M:%S.%f" / "%Y-%m-%d %H:%M:%S" → 转为 µs 时间戳
    - 均失败 → 抛 ValueError（带行号，供 UI 弹窗展示）
    """
    try:
        return int(float(value))
    except ValueError:
        pass
    for fmt in _DATETIME_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            return int(dt.timestamp() * 1_000_000)
        except ValueError:
            continue
    raise _row_error(row, "第%1行 %2 不是合法的日期时间", value)


def _strip_surrounding_quotes(value: str) -> str:
    """去掉成对包裹的单引号（旧版允许用户手输引号作为 SQL 字符串定界符）"""
    if len(value) >= 2 and value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    return value


def _numeric_placeholder(field_type: Any) -> str:
    """数值/日期字段的占位符：显式 CAST 保证按数值比较

    计算列是子查询表达式别名（无列亲和性），SQLite 对其执行
    `col > ?`（字符串参数）时会按文本比较导致恒假；显式 CAST
    优先于列亲和性，对物理列同样正确。
    """
    return "CAST(? AS REAL)" if isinstance(field_type, float) \
        else "CAST(? AS INTEGER)"


def _build_enum_single(field_type: Any, value: str) -> tuple[list, str]:
    """枚举字段等值/比较：显示名 → 枚举值（未匹配时原值作为参数绑定）"""
    enum_cls = field_type.__class__
    for e in enum_cls:
        if e.display_name == value:
            return [str(e.value)], "?"
    return [value], "?"


def _build_in_list(field_type: Any, value: str, row: int) -> tuple[list, str]:
    """in / not-in：展开为 (?,?,?) 占位符，逐值校验与转换（与旧版行为一致）"""
    if isinstance(field_type, (int, float)):
        values = value.split(",")
        for v in values:
            if not v.replace("-", "").replace(".", "").isdigit():
                raise _row_error(row, "第%1行 %2 不是数字", v)
        placeholder = _numeric_placeholder(field_type)
        return list(values), f"({','.join(placeholder for _ in values)})"

    if isinstance(field_type, datetime):
        placeholders: list[str] = []
        params: list = []
        for v in value.split(","):
            v = v.strip()
            if not v:
                continue
            params.append(_parse_datetime_value(v, row))
            placeholders.append(_numeric_placeholder(field_type))
        if placeholders:
            return params, f"({','.join(placeholders)})"
        # 空列表：恒假条件，避免生成非法 SQL "()"
        return [], "0 = 1"

    if isinstance(field_type, BaseDiaPlayEnum):
        enum_cls = field_type.__class__
        placeholders = []
        params = []
        for v in value.split(","):
            v = v.strip()
            if not v:
                continue
            for e in enum_cls:
                if e.display_name == v:
                    placeholders.append("?")
                    params.append(str(e.value))
                    break
            else:
                raise _row_error(row, "第%1行 %2 不是合法的枚举选项", v)
        if placeholders:
            return params, f"({','.join(placeholders)})"
        # 空列表：恒假条件，避免生成非法 SQL "()"
        return [], "0 = 1"

    # 字符串等其他类型：逐值参数绑定
    placeholders = []
    params = []
    for v in value.split(","):
        if not v.strip():
            continue
        placeholders.append("?")
        params.append(v)
    if placeholders:
        return params, f"({','.join(placeholders)})"
    # 空列表：恒假条件，避免生成非法 SQL "()"
    return [], "0 = 1"


def _like_pattern(value: str) -> str:
    """把用户输入的子串转成 LIKE 模式：转义 %、_、\\ 后前后各加一个 %

    用户输入的是「子串」而不是通配符模式，所以 % 与 _ 一律当字面量处理，
    否则「不含子串 a_b」会意外匹配到 aXb。
    """
    escaped = (value
               .replace("\\", "\\\\")
               .replace("%", "\\%")
               .replace("_", "\\_"))
    return f"%{escaped}%"


def _build_like(
    field_type: Any, value: str, row: int, field: str
) -> tuple[list, str]:
    """模糊匹配（like / not like）：按子串匹配文本字段

    只支持文本字段（TEXT 列与 string 计算列）：日期存的是微秒时间戳、枚举存的是
    整数值，都不是界面上看到的文本，按文本模糊匹配只会得出误导结果，
    因此直接报错让用户改用「包含 / 等于」。

    SQL 片段带 ``ESCAPE '\\'``，与 _like_pattern 的转义配套。
    """
    if not value:
        raise _row_error(row, "第%1行 模糊匹配的值不能为空")
    if not isinstance(field_type, str):
        raise _row_error(row, "第%1行 字段 %2 不是文本，不能用模糊匹配", field)
    return [_like_pattern(value)], r"? ESCAPE '\'"


def _build_value(
    field_type: Any, compare: CompareSymbol, value: str, row: int,
    field: str = "",
) -> tuple[list, str]:
    """构建单个条件的值部分，返回 (参数列表, SQL 值片段)"""
    is_in = compare.value in (CompareSymbol.Contains, CompareSymbol.NotContains)
    is_like = compare.value in (CompareSymbol.Like, CompareSymbol.NotLike)

    if is_like:
        return _build_like(field_type, value, row, field)

    if isinstance(field_type, BaseDiaPlayEnum) and not is_in:
        return _build_enum_single(field_type, value)

    if is_in:
        return _build_in_list(field_type, value, row)

    if isinstance(field_type, datetime) and value:
        # datetime 参数为 µs 时间戳整数，显式 CAST 保证数值比较
        return [_parse_datetime_value(value, row)], \
            _numeric_placeholder(field_type)

    if isinstance(field_type, (int, float)) and value:
        try:
            float(value)
        except ValueError:
            raise _row_error(row, "第%1行 %2 不是数字", value)
        # 显式 CAST 保证按数值比较（计算列无列亲和性）
        return [value], _numeric_placeholder(field_type)

    # 字符串等其他类型：参数绑定（兼容旧版用户手输引号定界的写法）
    return [_strip_surrounding_quotes(value)], "?"


def build_where(
    filter_rows: list[dict],
    known_fields: set[str],
    field_types: dict[str, Any] | None = None,
) -> tuple[str, list]:
    """根据过滤条件行构建参数化的 WHERE 片段

    Args:
        filter_rows: 过滤条件行（left_bracket/field/compare/value/right_bracket/logic）
        known_fields: 字段白名单（物理字段 + 已加载计算列名）
        field_types: 字段名 → 类型样本值 的映射（用于枚举/日期/数值转换，
            与 HistoryData 字段默认值语义一致）

    Returns:
        (sql_fragment, params)：sql_fragment 使用 ? 占位符，params 与占位符一一对应。
        filter_rows 为空时返回 ("", [])。

    Raises:
        ValueError: 字段不在白名单、括号不匹配或值校验失败（带行号与原因）。
    """
    if not filter_rows:
        return "", []

    field_types = field_types or {}
    clauses: list[str] = []
    params: list = []
    left_count = 0
    right_count = 0

    for row, data in enumerate(filter_rows):
        field = data.get("field") or ""
        compare_text = data.get("compare") or ""
        value = data.get("value") or ""

        if not field or not compare_text:
            continue

        # 字段白名单校验
        if field not in known_fields:
            raise _row_error(row, "第%1行 字段 %2 不是有效的字段名", field)

        field_type = field_types.get(field)
        compare = CompareSymbol.from_display_name(compare_text)
        logic = LogicSymbol.from_display_name(data.get("logic") or "").to_sql

        left_bracket = data.get("left_bracket") or ""
        right_bracket = data.get("right_bracket") or ""

        if left_bracket == "(":
            left_count += 1
        elif left_bracket == "((":
            left_count += 2
        if right_bracket == ")":
            right_count += 1
        elif right_bracket == "))":
            right_count += 2

        if right_count > left_count:
            raise _row_error(row, "第%1行 右括号数量大于左括号数量，请检查")

        row_params, value_sql = _build_value(
            field_type, compare, value, row, field)
        clauses.append(
            f" {left_bracket} {field} {compare.to_sql} {value_sql} {right_bracket} "
        )
        params.extend(row_params)

        # 与旧版一致：非最后一行时追加逻辑连接符（即使下一行为空行）
        if row != len(filter_rows) - 1:
            clauses.append(f" {logic} ")

    if left_count != right_count:
        raise ValueError(
            _translate("Form", "左括号数量和右括号数量不匹配，请检查"))

    return "".join(clauses), params


def build_order_by(sort_rows: list[dict], known_fields: set[str]) -> str:
    """根据排序条件行构建 ORDER BY 片段

    Returns:
        " ORDER BY field ASC, ..." 形式的片段；sort_rows 为空或全部无效时返回 ""。

    Raises:
        ValueError: 字段不在白名单（带行号与原因）。
    """
    if not sort_rows:
        return ""

    orders: list[str] = []
    for row, row_data in enumerate(sort_rows):
        field = row_data.get("field") or ""
        order_text = row_data.get("order") or ""
        if not field:
            continue

        # 字段白名单校验
        if field not in known_fields:
            raise _row_error(row, "第%1行 排序字段 %2 不是有效的字段名", field)

        order_sql = "ASC" if order_text == _translate("Form", "升序") else "DESC"
        orders.append(f"{field} {order_sql}")

    if orders:
        return " ORDER BY " + ", ".join(orders)
    return ""
