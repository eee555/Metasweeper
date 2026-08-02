"""
QML ↔ Python 数据桥

将 HistoryService 的查询结果暴露给 QML，
通过 QQuickWidget.rootContext().setContextProperty() 注入。

所有查询方法接受统一的筛选参数：
  level (-1=全部), mode (-1=全部), startUs (0=不限), endUs (0=不限)
"""

from __future__ import annotations

import json
from typing import Any

from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal, pyqtProperty

from shared_types.enums import GameBoardState, GameLevel, GameMode
from plugins.services.history import HistoryService

from .queries import (
    SQL_SUMMARY, SQL_SUMMARY_PARAMS,
    SQL_SUMMARY_BY_LEVEL, SQL_SUMMARY_BY_LEVEL_PARAMS,
    SQL_TREND,
    SQL_TIME_DISTRIBUTION,
    SQL_LEVEL_DISTRIBUTION,
    SQL_WINRATE_MONTHLY,
    SQL_PROGRESS_ASC, SQL_PROGRESS_DESC,
    SQL_TOPN_AVG,
    SQL_BV_DISTRIBUTION,
    PROGRESS_METRICS,
    LEVEL_NAMES, MODE_NAMES,
    build_where,
)


class StatsBridge(QObject):
    """
    暴露给 QML 的数据桥

    QML 通过 bridge.xxx() 调用 Python 方法获取数据。
    所有方法返回 JSON 字符串，QML 端用 JSON.parse() 解析。
    """

    dataChanged = pyqtSignal()
    topNChanged = pyqtSignal()
    bvBeginnerMinChanged = pyqtSignal()
    bvBeginnerMaxChanged = pyqtSignal()
    bvIntermediateMinChanged = pyqtSignal()
    bvIntermediateMaxChanged = pyqtSignal()
    bvExpertMinChanged = pyqtSignal()
    bvExpertMaxChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: HistoryService | None = None
        self._top_n: int = 10
        self._bv_beginner_min: int = 2
        self._bv_beginner_max: int = 54
        self._bv_intermediate_min: int = 30
        self._bv_intermediate_max: int = 128
        self._bv_expert_min: int = 100
        self._bv_expert_max: int = 288

    def set_history_service(self, service: HistoryService) -> None:
        self._history = service
        self.dataChanged.emit()

    def _query(self, sql: str, params: tuple = ()) -> str:
        if self._history is None:
            return "[]"
        try:
            rows = self._history.raw_query(sql, params)
            return json.dumps(rows, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _query_one(self, sql: str, params: tuple = ()) -> str:
        if self._history is None:
            return "null"
        try:
            row = self._history.raw_query_one(sql, params)
            return json.dumps(row, ensure_ascii=False, default=str) if row else "null"
        except Exception as e:
            return json.dumps({"error": str(e)})

    @staticmethod
    def _filter(level: int, mode: int, startMs: float, endMs: float) -> tuple[str, tuple]:
        """将 QML 传入的筛选参数转为 WHERE 子句（QML 传毫秒float，数据库存微秒int）"""
        return build_where(
            level=None if level < 0 else level,
            mode=None if mode < 0 else mode,
            start_us=None if startMs <= 0 else int(startMs * 1000),
            end_us=None if endMs <= 0 else int(endMs * 1000),
        )

    # ── QML 可调用的槽方法 ────────────────────────────────

    @pyqtSlot(int, int, float, float, result=str)
    def getSummary(self, level: int = -1, mode: int = -1,
                   startMs: float = 0, endMs: float = 0) -> str:
        where, params = self._filter(level, mode, startMs, endMs)
        sql = SQL_SUMMARY.format(where=where)
        return self._query_one(sql, SQL_SUMMARY_PARAMS + params)

    @pyqtSlot(int, int, float, float, result=str)
    def getLevelSummary(self, level: int = -1, mode: int = -1,
                        startMs: float = 0, endMs: float = 0) -> str:
        where, params = self._filter(level, mode, startMs, endMs)
        sql = SQL_SUMMARY_BY_LEVEL.format(where=where)
        return self._query(sql, SQL_SUMMARY_BY_LEVEL_PARAMS + params)

    @pyqtSlot(int, int, float, float, int, result=str)
    def getTrend(self, level: int = -1, mode: int = -1,
                 startMs: float = 0, endMs: float = 0, limit: int = 200) -> str:
        where, params = self._filter(level, mode, startMs, endMs)
        sql = SQL_TREND.format(where=where)
        return self._query(sql, params + (limit,))

    @pyqtSlot(int, int, float, float, result=str)
    def getTimeDistribution(self, level: int = -1, mode: int = -1,
                            startMs: float = 0, endMs: float = 0) -> str:
        where, params = self._filter(level, mode, startMs, endMs)
        extra = (" AND " + where.replace("WHERE ", "")) if where else ""
        sql = SQL_TIME_DISTRIBUTION.format(where_extra=extra)
        return self._query(sql, (GameBoardState.Win.value,) + params)

    @pyqtSlot(int, int, float, float, result=str)
    def getLevelDistribution(self, level: int = -1, mode: int = -1,
                             startMs: float = 0, endMs: float = 0) -> str:
        where, params = self._filter(level, mode, startMs, endMs)
        sql = SQL_LEVEL_DISTRIBUTION.format(where=where)
        return self._query(sql, params)

    @pyqtSlot(int, int, float, float, result=str)
    def getWinrateMonthly(self, level: int = -1, mode: int = -1,
                          startMs: float = 0, endMs: float = 0) -> str:
        where, params = self._filter(level, mode, startMs, endMs)
        sql = SQL_WINRATE_MONTHLY.format(where=where)
        return self._query(sql, (GameBoardState.Win.value,) + params)

    @pyqtSlot(result=str)
    def getLevelNames(self) -> str:
        return json.dumps(LEVEL_NAMES, ensure_ascii=False)

    @pyqtSlot(result=str)
    def getModeNames(self) -> str:
        return json.dumps(MODE_NAMES, ensure_ascii=False)

    @pyqtSlot(result=str)
    def getEnumValues(self) -> str:
        return json.dumps({
            "gameState": {
                "win": GameBoardState.Win.value,
                "fail": GameBoardState.Fail.value,
                "jowin": GameBoardState.Jowin.value,
                "jofail": GameBoardState.Jofail.value,
            },
            "level": {
                "beginner": GameLevel.BEGINNER.value,
                "intermediate": GameLevel.INTERMEDIATE.value,
                "expert": GameLevel.EXPERT.value,
                "custom": GameLevel.CUSTOM.value,
            },
            "mode": {m.value: m.display_name for m in GameMode},
        }, ensure_ascii=False)

    @pyqtSlot(str, int, int, float, float, result=str)
    def getProgress(self, metric: str, level: int = -1, mode: int = -1,
                    startMs: float = 0, endMs: float = 0) -> str:
        """获取进步历程数据（仅保留创纪录的局）。"""
        if metric not in PROGRESS_METRICS:
            return json.dumps({"error": f"Unknown metric: {metric}"})
        metric_expr, direction, display_name = PROGRESS_METRICS[metric]
        where, params = self._filter(level, mode, startMs, endMs)
        # where_and: "WHERE ... AND " 或 "WHERE "（无额外条件时）
        where_and = where + " AND " if where else "WHERE "
        sql_template = SQL_PROGRESS_ASC if direction == "asc" else SQL_PROGRESS_DESC
        sql = sql_template.format(metric_expr=metric_expr, where_and=where_and)
        # 额外参数：game_state = Win
        all_params = params + (GameBoardState.Win.value,)
        return self._query(sql, all_params)

    @pyqtSlot(result=str)
    def getProgressMetrics(self) -> str:
        """返回可用指标列表及显示名。"""
        return json.dumps(
            {k: v[2] for k, v in PROGRESS_METRICS.items()},
            ensure_ascii=False,
        )

    @pyqtSlot(int)
    def setTopN(self, n: int) -> None:
        """设置前N名平均的N值，0=全部平均。"""
        n = max(0, n)
        if self._top_n != n:
            self._top_n = n
            self.topNChanged.emit()
            self.dataChanged.emit()

    @pyqtSlot(result=int)
    def getTopN(self) -> int:
        """获取当前前N名平均的N值。"""
        return self._top_n

    @pyqtSlot(str, int, int, float, float, result=str)
    def getTopNAvg(self, metric: str, level: int = -1, mode: int = -1,
                   startMs: float = 0, endMs: float = 0) -> str:
        """获取指定指标的前N名平均值。top_n=0时返回null。"""
        if self._top_n == 0 or metric not in PROGRESS_METRICS:
            return "null"
        metric_expr, direction, _ = PROGRESS_METRICS[metric]
        order = "ASC" if direction == "asc" else "DESC"
        where, params = self._filter(level, mode, startMs, endMs)
        where_and = where + " AND " if where else "WHERE "
        sql = SQL_TOPN_AVG.format(
            metric_expr=metric_expr, order=order, where_and=where_and)
        all_params = params + (GameBoardState.Win.value, self._top_n)
        return self._query_one(sql, all_params)

    @pyqtSlot()
    def refresh(self) -> None:
        self.dataChanged.emit()

    # ── BV 范围配置属性 ──────────────────────────────────

    @pyqtProperty(int, notify=bvBeginnerMinChanged)  # type: ignore
    def bvBeginnerMin(self) -> int:
        return self._bv_beginner_min

    @pyqtSlot(int)
    def setBvBeginnerMin(self, v: int) -> None:
        if self._bv_beginner_min != v:
            self._bv_beginner_min = v
            self.bvBeginnerMinChanged.emit()

    @pyqtProperty(int, notify=bvBeginnerMaxChanged)  # type: ignore
    def bvBeginnerMax(self) -> int:
        return self._bv_beginner_max

    @pyqtSlot(int)
    def setBvBeginnerMax(self, v: int) -> None:
        if self._bv_beginner_max != v:
            self._bv_beginner_max = v
            self.bvBeginnerMaxChanged.emit()

    @pyqtProperty(int, notify=bvIntermediateMinChanged)  # type: ignore
    def bvIntermediateMin(self) -> int:
        return self._bv_intermediate_min

    @pyqtSlot(int)
    def setBvIntermediateMin(self, v: int) -> None:
        if self._bv_intermediate_min != v:
            self._bv_intermediate_min = v
            self.bvIntermediateMinChanged.emit()

    @pyqtProperty(int, notify=bvIntermediateMaxChanged)  # type: ignore
    def bvIntermediateMax(self) -> int:
        return self._bv_intermediate_max

    @pyqtSlot(int)
    def setBvIntermediateMax(self, v: int) -> None:
        if self._bv_intermediate_max != v:
            self._bv_intermediate_max = v
            self.bvIntermediateMaxChanged.emit()

    @pyqtProperty(int, notify=bvExpertMinChanged)  # type: ignore
    def bvExpertMin(self) -> int:
        return self._bv_expert_min

    @pyqtSlot(int)
    def setBvExpertMin(self, v: int) -> None:
        if self._bv_expert_min != v:
            self._bv_expert_min = v
            self.bvExpertMinChanged.emit()

    @pyqtProperty(int, notify=bvExpertMaxChanged)  # type: ignore
    def bvExpertMax(self) -> int:
        return self._bv_expert_max

    @pyqtSlot(int)
    def setBvExpertMax(self, v: int) -> None:
        if self._bv_expert_max != v:
            self._bv_expert_max = v
            self.bvExpertMaxChanged.emit()

    # ── BV 分布查询 ──────────────────────────────────────

    @pyqtSlot(int, int, int, result=str)
    def getBvDistribution(self, level: int, mode: int, winsOnly: int) -> str:
        """
        查询 BV 分布数据。

        Args:
            level: 3=初级, 4=中级, 5=高级
            mode: -1=全部, 0=标准, 4=Win7, 5=经典无猜, ...
            winsOnly: 0=全部, 1=仅胜局

        Returns:
            JSON 字符串，如 {"2": 5, "3": 12, ...}
        """
        if self._history is None:
            return "{}"
        try:
            win_states = (
                GameBoardState.Win.value,
                GameBoardState.Win.value,
            )
            extra = []
            extra_params: list[int] = []
            if winsOnly:
                extra.append(
                    f"game_state IN ({', '.join('?' * len(win_states))})")
                extra_params.extend(win_states)
            where, params = build_where(
                level=level,
                mode=None if mode < 0 else mode,
                extra_conditions=extra if extra else None,
            )
            params = params + tuple(extra_params)
            sql = SQL_BV_DISTRIBUTION.format(where=where)
            rows = self._history.raw_query(sql, params)
            result = {str(row["bbbv"]): row["count"] for row in rows}
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
