"""
应用路径工具（PyInstaller 兼容）

解决 PyInstaller 打包后的路径问题：
- sys.frozen=True 时运行在 _MEIPASS 临时目录中
- 需要区分：只读资源路径 vs 可写数据路径 vs 插件发现路径
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

import loguru
logger = loguru.logger.bind(name="AppPaths")


# ── 运行环境判断 ──────────────────────────────────────

def is_frozen() -> bool:
    """是否运行在 PyInstaller 打包环境中"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_bundle_dir() -> Path:
    """
    获取应用根目录（只读）

    - 开发模式: src/ 目录
    - 打包模式:   _MEIPASS 临时解压目录
    """
    if is_frozen():
        return Path(sys._MEIPASS)
    # 开发模式：返回 src/ 所在目录（即项目根目录的子目录）
    return Path(__file__).resolve().parent.parent


def get_executable_dir() -> Path:
    """
    获取可执行文件所在目录（可写）

    - 开发模式: 项目根目录
    - 打包模式:   exe 文件所在目录（用户可在此放插件）
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    # 开发模式：src/ 的上级即项目根目录
    return get_bundle_dir().parent


def get_data_dir() -> Path:
    """
    获取可写的数据目录（用于存放状态文件、日志等持久化数据）

    - 开发模式: <project>/src/data/
    - 打包模式:   <exe所在目录>/data/
    """
    base = get_executable_dir()
    data_dir = base / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_log_dir() -> Path:
    """
    获取日志目录（用于 loguru 输出）

    - 开发模式: <project>/src/data/logs/
    - 打包模式:   <exe所在目录>/data/logs/
    """
    log_dir = get_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


# ── 插件路径 ──────────────────────────────────────────

def get_builtin_plugin_dirs() -> list[Path]:
    """
    获取内置插件搜索目录列表

    内置插件随应用一起分发：
    - 开发模式: <project>/src/plugins/
    - 打包模式:   <_MEIPASS>/src/plugins/  （PyInstaller 打包时需用 collect_subdirs 或 Tree 收集）
    """
    bundle = get_bundle_dir()
    plugin_dir = bundle / "plugins"
    if plugin_dir.is_dir():
        return [plugin_dir]
    logger.warning(f"内置插件目录不存在: {plugin_dir}")
    return []


def get_user_plugin_dirs() -> list[Path]:
    """
    获取用户自定义插件目录（外部，用户自行添加的插件）

    - 开发模式: <项目根目录>/src/plugins/, <项目根目录>/src/user_plugins/
    - 打包模式:   <exe所在目录>/plugins/, <exe所在目录>/user_plugins/
    """
    base = get_executable_dir()
    result: list[Path] = []
    for name in ("plugins", "user_plugins"):
        d = base / name
        if d.is_dir():
            result.append(d)
    return result


def get_all_plugin_dirs() -> list[Path]:
    """获取所有插件搜索目录：内置 + 用户自定义"""
    return get_builtin_plugin_dirs() + get_user_plugin_dirs()


def get_plugin_data_dir(plugin_class: type | str) -> Path:
    """
    获取指定插件的专属数据目录（可写）

    根据传入的插件类或名称，在 data/plugin_data/ 下创建对应子目录。
    每个插件拥有独立的数据空间，互不干扰。

    - 开发模式: <project>/data/plugin_data/<plugin_name>/
    - 打包模式:   <exe所在目录>/data/plugin_data/<plugin_name>/

    Args:
        plugin_class: 插件类或插件名称字符串

    Returns:
        插件的专属数据目录路径
    """
    if isinstance(plugin_class, type):
        name = plugin_class.__name__
    else:
        name = str(plugin_class)

    plugin_data_dir = get_data_dir() / "plugin_data" / name
    plugin_data_dir.mkdir(parents=True, exist_ok=True)
    return plugin_data_dir


# ── 环境变量补丁（给子进程使用） ───────────────────────

def patch_sys_path_for_frozen() -> None:
    """
    将 bundle 目录加入 sys.path，确保动态导入能找到模块

    在打包模式下，PyInstaller 只把显式收集的模块放入 _MEIPASS。
    动态导入的插件如果依赖其他内部模块，需要确保这些模块也在 bundle 中，
    且 sys.path 能找到它们。
    """
    if not is_frozen():
        return
    bundle = str(get_bundle_dir())
    if bundle not in sys.path:
        sys.path.insert(0, bundle)
        logger.debug(f"已将 bundle 目录加入 sys.path: {bundle}")


def get_env_for_subprocess(env: dict | None = None) -> dict:
    """
    为启动插件管理器子进程构建环境变量

    确保 PYTHONPATH 包含正确的路径，使子进程中的动态导入正常工作。
    移除 QT_FONT_DPI 以让插件管理器使用独立的高分屏设置。
    """
    if env is None:
        env = dict(os.environ)

    # 移除主程序的 DPI 设置，让插件管理器使用自己的高分屏配置
    env.pop("QT_FONT_DPI", None)

    bundle = str(get_bundle_dir())
    exec_dir = str(get_executable_dir())

    # PYTHONPATH: bundle 目录优先（包含所有打包的代码）
    existing = env.get("PYTHONPATH", "")
    paths = [bundle]
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)

    logger.debug(f"子进程环境: PYTHONPATH={env.get('PYTHONPATH')}")
    return env


# ── 调试辅助 ──────────────────────────────────────────

def debug_dump_paths() -> dict[str, str]:
    """输出当前所有路径信息（调试用）"""
    return {
        "frozen": str(is_frozen()),
        "bundle_dir": str(get_bundle_dir()),
        "executable_dir": str(get_executable_dir()),
        "data_dir": str(get_data_dir()),
        "builtin_plugins": str(get_builtin_plugin_dirs()),
        "user_plugins": str(get_user_plugin_dirs()),
        "sys_executable": sys.executable,
        "_MEIPASS": getattr(sys, "_MEIPASS", "N/A"),
        "__file__": str(Path(__file__).resolve()),
    }
