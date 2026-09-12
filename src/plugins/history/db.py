"""SQLite 连接管理 — 上下文管理器 + 自定义函数注册"""

from __future__ import annotations

import ast
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)


# ── 模块级自定义函数脚本（由 plugin.py set_custom_script 设置）──────────
_custom_script: str = ""

# 按脚本内容缓存的编译结果（脚本未变时跳过 ast.parse + exec）
_script_cache: dict[
    str, tuple[dict[str, Any], list[tuple[str, int]]]] = {}


def set_custom_script(script: str) -> None:
    """设置用户自定义 Python 脚本（供后续连接时注册）"""
    global _custom_script
    _custom_script = script
    # 只保留当前脚本一个条目，避免旧脚本编译结果常驻内存
    _script_cache.clear()


def get_custom_script() -> str:
    """获取当前自定义脚本"""
    return _custom_script


def _compile_custom_script(
    script: str,
) -> tuple[dict[str, Any], list[tuple[str, int]]]:
    """编译用户自定义脚本，按脚本内容缓存编译结果

    Returns:
        (命名空间, [(py_ 函数名, 参数个数), ...])；
        编译/执行失败时返回 (空命名空间, 空列表)，并记录警告日志。
    """
    cached = _script_cache.get(script)
    if cached is not None:
        return cached

    namespace: dict[str, Any] = {}
    funcs: list[tuple[str, int]] = []
    try:
        tree = ast.parse(script)
    except SyntaxError as e:
        logger.warning(f"自定义函数脚本语法错误，已跳过注册: {e}")
        _script_cache[script] = (namespace, funcs)
        return namespace, funcs

    try:
        exec(compile(tree, "<custom_functions>", "exec"), namespace)
    except Exception as e:
        logger.warning(f"自定义函数脚本执行失败，已跳过注册: {e}")
        namespace = {}

    # 收集 py_ 前缀函数签名（仅顶层函数，避免与 SQLite 内置冲突）
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            if not node.name.startswith("py_"):
                continue
            func = namespace.get(node.name)
            if func and callable(func):
                funcs.append((node.name, len(node.args.args)))

    _script_cache[script] = (namespace, funcs)
    return namespace, funcs


def _register_custom_functions(conn: sqlite3.Connection) -> None:
    """在连接上注册自定义 Python 函数（仅注册 py_ 前缀的函数，避免与 SQLite 内置冲突）"""
    if not _custom_script:
        return

    namespace, funcs = _compile_custom_script(_custom_script)
    if not funcs:
        return

    for name, num_params in funcs:
        func = namespace.get(name)
        if func and callable(func):
            try:
                conn.create_function(name, num_params, func)  # type: ignore
            except sqlite3.Error:
                pass


@contextmanager
def db_connection(
    db_path: Path | str,
    *,
    register_custom_functions: bool = True,
) -> Generator[sqlite3.Connection, None, None]:
    """上下文管理器：自动管理连接生命周期 + 可选注册自定义函数

    用法::

        with db_connection(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM history")
            ...
    """
    conn = sqlite3.connect(str(db_path))
    try:
        if register_custom_functions:
            _register_custom_functions(conn)
        yield conn
    finally:
        conn.close()


def delete_record_tx(conn: sqlite3.Connection, replay_id: int) -> bool:
    """删除指定记录（history 元数据 + replay_data 录像数据同一事务）

    供 plugin.delete_record 与 history_table.delete_row 复用；
    不负责 commit，由调用方在同一事务内提交。

    Returns:
        是否删除了 history 中的记录
    """
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history WHERE replay_id = ?", (replay_id,))
    deleted = cursor.rowcount > 0
    # 同步删除 replay_data 子表中的录像数据（极旧库可能无此表）
    try:
        cursor.execute(
            "DELETE FROM replay_data WHERE replay_id = ?", (replay_id,))
    except sqlite3.OperationalError:
        pass  # 子表不存在，无录像数据可删
    return deleted


def ensure_indexes(conn: sqlite3.Connection) -> None:
    """确保查询索引存在（新建库和升级库路径都调用）

    - idx_history_level: WHERE level 过滤 + 按 replay_id 倒序
    - idx_history_start_time: ORDER BY start_time 排序
    - idx_history_game_state: game_state 过滤 + start_time 排序
    - idx_replay_data_compressed: 压缩迁移 worker 扫描未压缩记录
    """
    cursor = conn.cursor()
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_level "
        "ON history (level, replay_id DESC)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_start_time "
        "ON history (start_time)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_game_state "
        "ON history (game_state, start_time)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_replay_data_compressed "
        "ON replay_data (compressed)")
    conn.commit()
