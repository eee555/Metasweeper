"""
统计插件 SQL 查询封装

所有查询通过 HistoryService.raw_query / raw_query_one 执行，
不直接访问数据库，保持插件间解耦。

枚举值直接使用 shared_types.enums 中的 GameBoardState / GameLevel / GameMode。
"""

from __future__ import annotations

from shared_types.enums import GameBoardState, GameLevel, GameMode


# ── 汇总统计 ──────────────────────────────────────────────

SQL_SUMMARY = """
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN game_state = ? THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN game_state = ? THEN 1 ELSE 0 END) AS losses,
    SUM(CASE WHEN game_state IN (?, ?) THEN 1 ELSE 0 END) AS total_wins,
    ROUND(AVG(CASE WHEN game_state = ? THEN rtime END), 3) AS avg_win_time,
    ROUND(MIN(CASE WHEN game_state = ? THEN rtime END), 3) AS best_time,
    ROUND(MAX(CASE WHEN game_state = ? THEN rtime END), 3) AS worst_time,
    ROUND(AVG(CASE WHEN game_state = ? AND bbbv > 0
        THEN CAST(bbbv_solved AS FLOAT) / bbbv END), 4) AS avg_bbbv_pct,
    ROUND(AVG(CASE WHEN game_state = ? AND rtime > 0
        THEN CAST(bbbv AS FLOAT) / rtime END), 2) AS avg_3bvs,
    ROUND(MAX(CASE WHEN game_state = ? AND rtime > 0
        THEN CAST(bbbv AS FLOAT) / rtime END), 2) AS best_3bvs,
    ROUND(MIN(CASE WHEN game_state = ? AND rtime > 0
        THEN CAST(bbbv AS FLOAT) / rtime END), 2) AS worst_3bvs,
    ROUND(AVG(CASE WHEN game_state = ? AND cl > 0
        THEN CAST(bbbv AS FLOAT) / cl END), 2) AS avg_ioe,
    ROUND(MAX(CASE WHEN game_state = ? AND cl > 0
        THEN CAST(bbbv AS FLOAT) / cl END), 2) AS best_ioe,
    ROUND(MIN(CASE WHEN game_state = ? AND cl > 0
        THEN CAST(bbbv AS FLOAT) / cl END), 2) AS worst_ioe,
    ROUND(AVG(CASE WHEN game_state = ? AND ce > 0
        THEN CAST(bbbv AS FLOAT) / ce END), 2) AS avg_thrp,
    ROUND(MAX(CASE WHEN game_state = ? AND ce > 0
        THEN CAST(bbbv AS FLOAT) / ce END), 2) AS best_thrp,
    ROUND(MIN(CASE WHEN game_state = ? AND ce > 0
        THEN CAST(bbbv AS FLOAT) / ce END), 2) AS worst_thrp,
    ROUND(AVG(CASE WHEN game_state = ? AND cl > 0
        THEN CAST(ce AS FLOAT) / cl END), 2) AS avg_corr,
    ROUND(MAX(CASE WHEN game_state = ? AND cl > 0
        THEN CAST(ce AS FLOAT) / cl END), 2) AS best_corr,
    ROUND(MIN(CASE WHEN game_state = ? AND cl > 0
        THEN CAST(ce AS FLOAT) / cl END), 2) AS worst_corr,
    ROUND(AVG(CASE WHEN game_state = ? AND rtime > 0
        THEN CAST(ce AS FLOAT) / rtime END), 2) AS avg_ces,
    ROUND(MAX(CASE WHEN game_state = ? AND rtime > 0
        THEN CAST(ce AS FLOAT) / rtime END), 2) AS best_ces,
    ROUND(MIN(CASE WHEN game_state = ? AND rtime > 0
        THEN CAST(ce AS FLOAT) / rtime END), 2) AS worst_ces,
    ROUND(AVG(CASE WHEN game_state = ? AND rtime > 0
        THEN CAST(cl AS FLOAT) / rtime END), 2) AS avg_cls,
    ROUND(MAX(CASE WHEN game_state = ? AND rtime > 0
        THEN CAST(cl AS FLOAT) / rtime END), 2) AS best_cls,
    ROUND(MIN(CASE WHEN game_state = ? AND rtime > 0
        THEN CAST(cl AS FLOAT) / rtime END), 2) AS worst_cls
FROM history
{where}
"""

SQL_SUMMARY_PARAMS = (
    GameBoardState.Win.value, GameBoardState.Fail.value,
    GameBoardState.Win.value, GameBoardState.Win.value,
    GameBoardState.Win.value, GameBoardState.Win.value,
    GameBoardState.Win.value,
    GameBoardState.Win.value, GameBoardState.Win.value,
    GameBoardState.Win.value, GameBoardState.Win.value,
    GameBoardState.Win.value, GameBoardState.Win.value,
    GameBoardState.Win.value, GameBoardState.Win.value,
    GameBoardState.Win.value, GameBoardState.Win.value,
    GameBoardState.Win.value, GameBoardState.Win.value,
    GameBoardState.Win.value, GameBoardState.Win.value,
    GameBoardState.Win.value, GameBoardState.Win.value,
    GameBoardState.Win.value, GameBoardState.Win.value,    GameBoardState.Win.value,)

# ── TopN 平均查询 ──────────────────────────────────────────
# 用于计算前N名的平均值，{metric_expr} 和 {order} 由调用方填充
# order: "ASC" for rtime (越小越好), "DESC" for others (越大越好)
SQL_TOPN_AVG = """
SELECT ROUND(AVG(metric_val), 2) AS topn_avg FROM (
    SELECT {metric_expr} AS metric_val
    FROM history
    {where_and} game_state = ?
    AND {metric_expr} > 0
    ORDER BY {order}
    LIMIT ?
) sub
"""

SQL_SUMMARY_BY_LEVEL = """
SELECT
    level,
    COUNT(*) AS total,
    SUM(CASE WHEN game_state = ? THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN game_state = ? THEN 1 ELSE 0 END) AS losses,
    ROUND(AVG(CASE WHEN game_state = ? THEN rtime END), 3) AS avg_win_time,
    ROUND(MIN(CASE WHEN game_state = ? THEN rtime END), 3) AS best_time,
    ROUND(AVG(CASE WHEN game_state = ? AND bbbv > 0
        THEN CAST(bbbv_solved AS FLOAT) / bbbv END), 4) AS avg_bbbv_pct,
    ROUND(AVG(CASE WHEN game_state = ? AND rtime > 0
        THEN CAST(bbbv AS FLOAT) / rtime END), 2) AS avg_3bvs
FROM history
{where}
GROUP BY level
ORDER BY level
"""

SQL_SUMMARY_BY_LEVEL_PARAMS = (
    GameBoardState.Win.value, GameBoardState.Fail.value,
    GameBoardState.Win.value, GameBoardState.Win.value,
    GameBoardState.Win.value, GameBoardState.Win.value,
)


# ── 趋势数据 ──────────────────────────────────────────────

SQL_TREND = """
SELECT
    start_time,
    rtime,
    bbbv,
    bbbv_solved,
    game_state,
    level,
    mode,
    nf,
    CASE WHEN bbbv > 0 AND rtime > 0
        THEN ROUND(CAST(bbbv AS FLOAT) / rtime, 2)
        ELSE 0 END AS bbbv_s
FROM history
{where}
ORDER BY start_time DESC
LIMIT ?
"""


# ── 分布数据 ──────────────────────────────────────────────

SQL_TIME_DISTRIBUTION = """
SELECT
    ROUND(rtime, 0) AS time_bucket,
    COUNT(*) AS count
FROM history
WHERE game_state = ? AND rtime > 0
{where_extra}
GROUP BY ROUND(rtime, 0)
ORDER BY time_bucket
"""


# ── 难度分布 ──────────────────────────────────────────────

SQL_LEVEL_DISTRIBUTION = """
SELECT
    level,
    COUNT(*) AS count
FROM history
{where}
GROUP BY level
ORDER BY level
"""


# ── 胜率趋势（按月）──────────────────────────────────────

SQL_WINRATE_MONTHLY = """
SELECT
    CAST(start_time / 1000000 AS INTEGER) AS ts_sec,
    COUNT(*) AS total,
    SUM(CASE WHEN game_state = ? THEN 1 ELSE 0 END) AS wins
FROM history
{where}
GROUP BY CAST(strftime('%Y-%m', datetime(start_time / 1000000, 'unixepoch', 'localtime')) AS TEXT)
ORDER BY ts_sec
"""


# ── 进步历程 ──────────────────────────────────────────────
# 指标定义：key → (SQL表达式, 进步方向 'asc'=越小越好, 'desc'=越大越好, 显示名)
PROGRESS_METRICS = {
    "rtime":   ("rtime",                          "asc",  "用时(s)"),
    "3bvs":    ("CASE WHEN rtime>0 THEN CAST(bbbv AS FLOAT)/rtime ELSE 0 END", "desc", "3BV/s"),
    "ioe":     ("CASE WHEN cl>0 THEN CAST(bbbv AS FLOAT)/cl ELSE 0 END",      "desc", "IOE"),
    "thrp":    ("CASE WHEN ce>0 THEN CAST(bbbv AS FLOAT)/ce ELSE 0 END",      "desc", "thrp"),
    "corr":    ("CASE WHEN cl>0 THEN CAST(ce AS FLOAT)/cl ELSE 0 END",        "desc", "corr"),
    "ces":     ("CASE WHEN rtime>0 THEN CAST(ce AS FLOAT)/rtime ELSE 0 END",  "desc", "ces"),
    "cls":     ("CASE WHEN rtime>0 THEN CAST(cl AS FLOAT)/rtime ELSE 0 END",  "desc", "cls"),
}

# 进步历程 SQL：只保留"创纪录"的局
# 逻辑：按 start_time 排序，用窗口函数算截至当前行的历史最优，
#       只保留 metric_value == running_best 的行
# asc (越小越好): running_best = MIN(metric) OVER (ORDER BY start_time)
# desc (越大越好): running_best = MAX(metric) OVER (ORDER BY start_time)

SQL_PROGRESS_ASC = """
WITH ordered AS (
    SELECT
        replay_id,
        start_time,
        rtime,
        bbbv,
        cl,
        ce,
        {metric_expr} AS metric_value,
        MIN({metric_expr}) OVER (ORDER BY start_time ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_best
    FROM history
    {where_and} game_state = ?
    AND {metric_expr} > 0
)
SELECT
    replay_id,
    CAST(start_time / 1000000 AS INTEGER) AS ts_sec,
    ROUND(metric_value, 4) AS metric_value
FROM ordered
WHERE metric_value = running_best
ORDER BY start_time
"""

SQL_PROGRESS_DESC = """
WITH ordered AS (
    SELECT
        replay_id,
        start_time,
        rtime,
        bbbv,
        cl,
        ce,
        {metric_expr} AS metric_value,
        MAX({metric_expr}) OVER (ORDER BY start_time ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_best
    FROM history
    {where_and} game_state = ?
    AND {metric_expr} > 0
)
SELECT
    replay_id,
    CAST(start_time / 1000000 AS INTEGER) AS ts_sec,
    ROUND(metric_value, 4) AS metric_value
FROM ordered
WHERE metric_value = running_best
ORDER BY start_time
"""


# ── BV 分布 ──────────────────────────────────────────────

SQL_BV_DISTRIBUTION = """
SELECT
    bbbv,
    COUNT(*) AS count
FROM history
{where}
GROUP BY bbbv
ORDER BY bbbv
"""


# ── WHERE 构建器 ──────────────────────────────────────────

def build_where(
    level: int | None = None,
    mode: int | None = None,
    start_us: int | None = None,
    end_us: int | None = None,
    extra_conditions: list[str] | None = None,
) -> tuple[str, tuple]:
    """
    构建 WHERE 子句，返回 (clause, params)。

    start_us / end_us 为微秒时间戳。
    返回的 clause 以 "WHERE" 开头（或空字符串）。
    """
    conditions: list[str] = []
    params: list[int] = []

    if level is not None:
        conditions.append("level = ?")
        params.append(level)
    if mode is not None:
        conditions.append("mode = ?")
        params.append(mode)
    if start_us is not None:
        conditions.append("start_time >= ?")
        params.append(start_us)
    if end_us is not None:
        conditions.append("start_time <= ?")
        params.append(end_us)
    if extra_conditions:
        conditions.extend(extra_conditions)

    if conditions:
        return "WHERE " + " AND ".join(conditions), tuple(params)
    return "", tuple()


# ── 辅助函数 ──────────────────────────────────────────────

LEVEL_NAMES = {m.value: m.display_name for m in GameLevel}
MODE_NAMES = {m.value: m.display_name for m in GameMode}


def level_name(level: int) -> str:
    return LEVEL_NAMES.get(level, f"Level {level}")


def mode_name(mode: int) -> str:
    return MODE_NAMES.get(mode, f"Mode {mode}")
