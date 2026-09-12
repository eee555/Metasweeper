"""
计算列定义

用户可配置的 SQL 计算列，通过子查询实现。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 合法计算列名：中文/字母/下划线开头，仅含中文、字母、数字、下划线
_COLUMN_NAME_RE = re.compile(r"[A-Za-z_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff]*")

# 保留字：与查询 SQL 内部别名/表名冲突，禁止用户创建该名计算列
_RESERVED_NAMES = frozenset({"total_count"})


def validate_column_name(name: str) -> str | None:
    """校验计算列名

    Returns:
        合法返回 None；非法返回含 %1 占位的中文错误模板（由调用方替换后提示）
    """
    if not name:
        return "列名不能为空"
    if name in _RESERVED_NAMES:
        return "列名 '%1' 是保留字，不能使用"
    if not _COLUMN_NAME_RE.fullmatch(name):
        return ("列名 '%1' 含非法字符，仅允许中文、字母、数字、下划线，"
                "且不能以数字开头")
    return None


@dataclass
class ComputedColumn:
    """
    计算列定义

    Attributes:
        name: 列名（如 "bbbvs"），需为合法 SQL 别名
        expression: SQL 表达式（如 "bbbv * 1.0 / rtime"）
        result_type: 结果类型 "int" | "float"，决定显示精度和 delegate
    """

    name: str
    expression: str
    result_type: str = "float"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "expression": self.expression,
            "result_type": self.result_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ComputedColumn:
        name = data.get("name", "")
        error = validate_column_name(name)
        if error:
            raise ValueError(error.replace("%1", name))
        return cls(
            name=name,
            expression=data.get("expression", ""),
            result_type=data.get("result_type", "float"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> list[ComputedColumn]:
        """从 JSON 字符串解析计算列列表（非法列名跳过）"""
        if not json_str:
            return []
        try:
            items = json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(items, list):
            return []
        columns: list[ComputedColumn] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                columns.append(cls.from_dict(item))
            except ValueError as e:
                # 旧配置可能残留非法列名，跳过以保证插件正常加载
                logger.warning(f"已跳过非法计算列配置: {e}")
        return columns

    @staticmethod
    def to_json(columns: list[ComputedColumn]) -> str:
        """将计算列列表序列化为 JSON 字符串"""
        return json.dumps(
            [col.to_dict() for col in columns], ensure_ascii=False
        )

    @staticmethod
    def build_subquery_sql(columns: list[ComputedColumn]) -> str | None:
        """
        构建计算列子查询的 FROM 部分

        Returns:
            子查询 SQL（如 "SELECT *, (bbbv*1.0/rtime) AS \"bbbvs\" FROM history"），
            或 None（无计算列时）
        """
        if not columns:
            return None
        computed_parts = ", ".join(
            f"({col.expression}) AS \"{col.name}\"" for col in columns
        )
        return f"SELECT *, {computed_parts} FROM history"
