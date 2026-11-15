"""
Loguru 日志初始化模块

配置规则：
|- 插件管理器主日志 → <log_dir>/main.log（所有非插件日志）
|- 每个插件独立日志 → <log_dir>/plugins/<plugin_name>.log
|- 控制台输出带颜色
|- 日志轮转：按大小自动清理（插件可在 PluginInfo 中自定义）

使用方式：
    from plugin_manager.logging_setup import init_logging, get_plugin_logger, LogConfig

    init_logging(log_dir)                    # 启动时调用一次
    logger = get_plugin_logger("game_monitor")  # 插件获取自己的 logger
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import loguru


@dataclass(frozen=True)
class LogConfig:
    """日志轮转配置，插件可通过 PluginInfo.log_config 自定义"""
    rotation: str = "10 MB"   # 单文件最大大小，超出后自动轮转
    retention: int = 5        # 保留的备份文件数（0 = 不删除旧文件）


#: 全局默认配置，插件不声明时使用此值
DEFAULT_LOG_CONFIG = LogConfig()

# 保存控制台 sink ID，用于清理
_console_sink_id: Optional[int] = None

# 按 plugin_name 复用插件文件 sink（#34）：同名插件只 add 一次，避免同一条
# 日志被写多遍。value 为 (sink_id, 日志文件路径, handler 对象引用)。
# 复用时校验 id + 路径 + handler 身份：loguru 会复用 sink_id 整数，仅比对
# 整数可能在 remove 后误指向别的 handler。
_plugin_sinks: dict[str, tuple[int, str, object]] = {}


def init_logging(
    log_dir: Path | str,
    *,
    console: bool = True,
    level: str = "DEBUG",
    log_config: LogConfig | None = None,
) -> None:
    """
    初始化日志系统（仅调用一次）

    Args:
        log_dir: 日志根目录
        console: 是否输出到控制台
        level: 控制台最低级别
        log_config: 日志轮转配置（默认 10MB / 5个备份）
    """
    global _console_sink_id, _plugin_sinks
    _logger = loguru.logger
    cfg = log_config or DEFAULT_LOG_CONFIG

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # 移除 loguru 默认的 stderr sink，避免重复输出；同时作废插件 sink 复用表，
    # 否则表里的 sink_id 会指向已被 remove 的 handler（#34）。
    _logger.remove()
    _plugin_sinks.clear()

    # ── 主日志文件 (main.log) ──
    main_log = log_dir / "main.log"
    _logger.add(
        str(main_log),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {name}:{function}:{line} | {message}",
        rotation=cfg.rotation,
        retention=cfg.retention,
        encoding="utf-8",
    )

    # ── 控制台输出（可选）──
    if console:
        _console_sink_id = _logger.add(
            lambda msg: print(msg, end="", flush=True),
            level=level,
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level:<7}</level> | "
                "<cyan>{name}</cyan>:<dim>{function}</dim> "
                "| {message}"
            ),
            colorize=True,
        )

    # ── 插件日志目录预创建 ──
    (log_dir / "plugins").mkdir(parents=True, exist_ok=True)


def get_plugin_logger(
    plugin_name: str,
    *,
    log_dir: Path | str | None = None,
    log_config: LogConfig | None = None,
) -> tuple["loguru.Logger", int]:
    """
    获取插件的专用 logger（每个插件一个独立日志文件）

    Args:
        plugin_name: 插件名称（如 "game_monitor"）
        log_dir: 可选，覆盖默认的插件日志目录
        log_config: 日志轮转配置，None 使用全局默认值

    Returns:
        (logger, sink_id) 元组，sink_id 用于动态修改日志级别

    同名 plugin_name 复用同一文件 sink（#34）：已存在且仍有效的 sink 直接
    返回其 sink_id，不再重复 add，避免同一条日志被写多遍。

    Usage::

        self.logger, self._log_sink_id = get_plugin_logger(self.name)
        self.logger.info("插件启动了")
    """
    global _plugin_sinks
    if log_dir is None:
        from .app_paths import get_data_dir
        log_dir = get_data_dir() / "logs" / "plugins"
    else:
        log_dir = Path(log_dir) / "plugins"

    cfg = log_config or DEFAULT_LOG_CONFIG

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{plugin_name}.log"
    log_key = str(log_file)

    lg = loguru.logger.bind(plugin=plugin_name)

    # 同名插件且目标文件一致时复用已有 sink；若外部直接 remove(sink_id)
    # 导致 handler 已失效，则清掉记录并重建。
    existing = _plugin_sinks.get(plugin_name)
    if existing is not None:
        sink_id, path, handler_ref = existing
        current = loguru.logger._core.handlers.get(sink_id)
        if current is handler_ref and current is not None and path == log_key:
            return lg, sink_id
        _plugin_sinks.pop(plugin_name, None)

    # 绑定专属文件 sink：只接收该插件的日志
    sink_id = lg.add(
        str(log_file),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {message}",
        rotation=cfg.rotation,
        retention=cfg.retention,
        encoding="utf-8",
        filter=lambda rec, pn=plugin_name: rec["extra"].get("plugin") == pn,
    )
    _plugin_sinks[plugin_name] = (
        sink_id, log_key, loguru.logger._core.handlers.get(sink_id))
    return lg, sink_id


def remove_plugin_logger(sink_id: int) -> None:
    """移除插件日志 sink 并清理复用表（#34）。

    plugin_base.py 不在本批次白名单，故这里只提供清理入口，不强行接线到
    shutdown。调用方在插件卸载时传入 get_plugin_logger 返回的 sink_id 即可；
    重复移除或不存在的 sink_id 均安全（loguru.remove 抛 ValueError 时忽略）。
    """
    global _plugin_sinks
    try:
        loguru.logger.remove(sink_id)
    except ValueError:
        pass
    for name, (sid, _, _) in list(_plugin_sinks.items()):
        if sid == sink_id:
            _plugin_sinks.pop(name, None)


def clear_all_logs(log_dir: Path | str) -> tuple[int, list[str]]:
    """清空日志目录下所有日志文件的内容（含插件日志与轮转备份）。

    日志文件可能正被 loguru 的文件 sink 以追加模式持有：Windows 下无法删除，
    但截断为空是安全的，后续追加写入会从新的文件末尾继续。因此这里一律截断
    而不是删除，保证清理后 sink 仍能正常写入。

    Args:
        log_dir: 日志根目录

    Returns:
        (成功清理的文件数, 清理失败的文件路径列表)
    """
    root = Path(log_dir)
    if not root.is_dir():
        return 0, []

    cleared = 0
    failed: list[str] = []
    # 只处理 .log：日志目录里可能混有截图等其它文件，不能一并清空
    for path in sorted(root.rglob("*.log")):
        if not path.is_file():
            continue
        try:
            with path.open("w", encoding="utf-8"):
                pass
            cleared += 1
        except OSError:
            failed.append(str(path))
    return cleared, failed


def set_plugin_log_level(sink_id: int, level: str = "DEBUG") -> None:
    """
    动态修改某个插件日志 sink 的级别

    Args:
        sink_id: get_plugin_logger 返回的 sink_id
        level: 新的日志级别 ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR")
    """
    config = loguru.logger._core
    handler = config.handlers.get(sink_id)
    if handler is not None:
        # 从 loguru 的 levels 字典获取级别号
        levels = config.levels
        level_info = levels.get(level.upper())
        if level_info is not None:
            handler._levelno = level_info.no  # type: ignore[union-attr]
            handler._levelname = level.upper()  # type: ignore[union-attr]


def set_console_log_level(level: str = "DEBUG") -> None:
    """
    动态修改控制台日志输出的级别

    Args:
        level: 新的日志级别 ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    """
    global _console_sink_id
    if _console_sink_id is None:
        return
    
    config = loguru.logger._core
    handler = config.handlers.get(_console_sink_id)
    if handler is not None:
        levels = config.levels
        level_info = levels.get(level.upper())
        if level_info is not None:
            handler._levelno = level_info.no  # type: ignore[union-attr]
            handler._levelname = level.upper()  # type: ignore[union-attr]
