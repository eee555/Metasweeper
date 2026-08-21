"""
OpenmsService 服务接口
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from dataclasses import dataclass


# @dataclass(frozen=True, slots=True)
# class OpenmsData:
#     """数据类型"""
#     id: int
#     name: str


@runtime_checkable
class OpenmsService(Protocol):
    """服务接口定义"""
    pass

# 示例方法（取消注释后使用）:
#     def get_data(self, id: int) -> OpenmsData | None: ...
#     def list_data(self, limit: int = 100) -> list[OpenmsData]: ...
