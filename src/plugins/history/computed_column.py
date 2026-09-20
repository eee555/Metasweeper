"""
计算列定义

用户可配置的 SQL 计算列，通过子查询实现。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# 可用结果类型：int/float 按数值比较，string 按文本比较
RESULT_TYPES: tuple[str, ...] = ("float", "int", "string")

# 结果类型 → 类型样本值（查询构建器据此决定数值 CAST 还是文本参数绑定）
_TYPE_SAMPLES: dict[str, Any] = {"float": 0.0, "int": 0, "string": ""}

# 合法计算列名：中文/字母/下划线开头，仅含中文、字母、数字、下划线
_COLUMN_NAME_RE = re.compile(r"[A-Za-z_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff]*")

# 保留字：与查询 SQL 内部别名/表名冲突，禁止用户创建该名计算列
_RESERVED_NAMES = frozenset({"total_count"})


def normalize_result_type(value: Any) -> str:
    """规范化结果类型，未知取值回退为 float（兼容旧配置与手改配置文件）"""
    return value if value in RESULT_TYPES else "float"


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
        result_type: 结果类型 "int" | "float" | "string"
            （数值类型决定显示精度与过滤时是否 CAST，
            string 类型过滤/排序按文本处理）
    """

    name: str
    expression: str
    result_type: str = "float"

    @property
    def sample_value(self) -> Any:
        """类型样本值：0.0 / 0 / ""

        过滤与排序构建器靠「字段值的类型」区分数值与文本，
        这里统一给出该结果类型对应的样本值，避免各处重复判断。
        """
        return _TYPE_SAMPLES.get(self.result_type, 0.0)

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
            result_type=normalize_result_type(data.get("result_type", "float")),
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
