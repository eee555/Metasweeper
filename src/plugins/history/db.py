"""SQLite 连接管理 — 上下文管理器 + 自定义函数注册"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


# ── 模块级自定义函数脚本（由 plugin.py set_custom_script 设置）──────────
_custom_script: str = ""


def set_custom_script(script: str) -> None:
    """设置用户自定义 Python 脚本（供后续连接时注册）"""
    global _custom_script
    _custom_script = script


def get_custom_script() -> str:
    """获取当前自定义脚本"""
    return _custom_script


def _register_custom_functions(conn: sqlite3.Connection) -> None:
    """在连接上注册自定义 Python 函数（仅注册 py_ 前缀的函数，避免与 SQLite 内置冲突）"""
    if not _custom_script:
        return
    import ast

    try:
        tree = ast.parse(_custom_script)
    except SyntaxError:
        return

    namespace: dict = {}
    exec(compile(tree, "<custom_functions>", "exec"), namespace)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            if not node.name.startswith("py_"):
                continue  # 仅注册 py_ 前缀的函数
            func = namespace.get(node.name)
            if func and callable(func):
                num_params = len(node.args.args)
                try:
                    conn.create_function(
                        node.name, num_params, func)  # type: ignore
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
