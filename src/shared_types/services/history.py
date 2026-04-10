"""
历史记录服务接口

定义历史记录查询的标准接口，供插件间通讯使用。

Usage::

    # 服务提供者 (HistoryPlugin)
    class HistoryPlugin(BasePlugin):
        def query_records(self, limit: int = 100, ...) -> list[GameRecord]:
            return [GameRecord(...) for row in rows]
        
        def on_initialized(self):
            self.register_service(self, protocol=HistoryService)
    
    # 服务使用者
    class StatsPlugin(BasePlugin):
        def on_initialized(self):
            self._history = self.get_service(HistoryService)
        
        def _update(self):
            records = self._history.query_records(limit=100)
            for r in records:
                print(r.rtime, r.level, r.bbbv)  # IDE 完整补全
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class GameRecord:
    """
    游戏记录数据类型
    
    使用 frozen=True 保证不可变（线程安全）
    使用 slots=True 减少内存占用
    """
    replay_id: int
    rtime: float
    level: int
    bbbv: int
    bbbv_solved: int = 0
    left: int = 0
    right: int = 0
    double: int = 0
    cl: int = 0
    ce: int = 0
    flag: int = 0
    game_board_state: int = 0
    mode: int = 0
    software: str = ""
    start_time: int = 0
    end_time: int = 0


@runtime_checkable
class HistoryService(Protocol):
    """
    历史记录服务接口（只读）
    
    提供游戏历史记录的查询功能。
    实现此接口的插件可被其他插件通过 call_service() 调用。
    
    注意：此接口仅提供只读操作，删除等敏感操作不对外暴露。
    
    类型安全：IDE 可完整推断返回类型和方法签名。
    """
    
    def query_records(
        self,
        limit: int = 100,
        offset: int = 0,
        level: int | None = None,
    ) -> list[GameRecord]:
        """
        查询游戏记录
        
        Args:
            limit: 返回记录数量上限
            offset: 偏移量（用于分页）
            level: 游戏难度筛选（None 表示全部）
            
        Returns:
            GameRecord 列表
        """
        ...
    
    def get_record_count(self, level: int | None = None) -> int:
        """获取记录总数"""
        ...
    
    def get_last_record(self) -> GameRecord | None:
        """获取最近一条记录"""
        ...
