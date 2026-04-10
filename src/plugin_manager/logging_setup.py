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
    global _console_sink_id
    _logger = loguru.logger
    cfg = log_config or DEFAULT_LOG_CONFIG

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # 移除 loguru 默认的 stderr sink，避免重复输出
    _logger.remove()

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

    Usage::

        self.logger, self._log_sink_id = get_plugin_logger(self.name)
        self.logger.info("插件启动了")
    """
    if log_dir is None:
        from .app_paths import get_data_dir
        log_dir = get_data_dir() / "logs" / "plugins"
    else:
        log_dir = Path(log_dir) / "plugins"

    cfg = log_config or DEFAULT_LOG_CONFIG

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{plugin_name}.log"

    lg = loguru.logger.bind(plugin=plugin_name)

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
    return lg, sink_id


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
