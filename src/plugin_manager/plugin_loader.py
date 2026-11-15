"""
插件加载器

支持动态导入插件模块，从指定目录发现和加载插件
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import loguru

if TYPE_CHECKING:
    from plugin_sdk.plugin_base import BasePlugin, PluginInfo

logger = loguru.logger.bind(name="PluginLoader")


class PluginLoader:
    """
    插件加载器

    功能：
    - 从目录发现插件模块
    - 动态导入插件
    - 实例化插件类
    """

    def __init__(self, plugin_dirs: list[Path] | None = None):
        self._plugin_dirs: list[Path] = []
        self._added_paths: set[Path] = set()  # 已添加到 sys.path 的目录
        self._loaded_modules: set[str] = set()  # 本加载器成功登记的模块
        if plugin_dirs:
            for d in plugin_dirs:
                self.add_plugin_dir(d)

    def add_plugin_dir(self, path: str | Path) -> None:
        """添加插件搜索目录"""
        p = Path(path)
        if p.is_dir():
            self._plugin_dirs.append(p)
            # 将插件目录的父目录加入 sys.path（支持 from plugins.xxx 导入）。
            # append 而非 insert(0)，避免插件目录抢在标准库之前。
            parent = p.parent
            if parent not in self._added_paths:
                self._added_paths.add(parent)
                parent_str = str(parent)
                if parent_str not in sys.path:
                    sys.path.append(parent_str)
                    logger.debug(f"Added to sys.path: {parent}")
            logger.debug(f"Added plugin directory: {p}")
        else:
            logger.warning(f"Plugin directory not found: {p}")

    def discover_plugins(self) -> list[tuple[Path, str]]:
        """发现所有插件模块（同名模块只保留首次发现）"""
        plugins: list[tuple[Path, str]] = []
        seen: set[str] = set()

        # 排除的目录名（不是插件，但放在 plugins 目录下）
        excluded_dirs = {"services"}

        def add(path: Path, name: str) -> None:
            # 局限：仍使用裸模块名；改成命名空间名会破坏现有 from plugins.xxx 导入。
            if name in seen:
                logger.warning(
                    f"Duplicate plugin module skipped: {name} ({path})")
                return
            seen.add(name)
            plugins.append((path, name))
            logger.debug(f"Discovered plugin module: {path}")

        for plugin_dir in self._plugin_dirs:
            if not plugin_dir.is_dir():
                continue

            # 单文件插件
            for py_file in plugin_dir.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                add(py_file, py_file.stem)

            # 包形式插件
            for pkg_dir in plugin_dir.iterdir():
                if pkg_dir.is_dir() and (pkg_dir / "__init__.py").exists():
                    # 排除 services 等非插件目录
                    if pkg_dir.name.startswith("_") or pkg_dir.name in excluded_dirs:
                        continue
                    add(pkg_dir / "__init__.py", pkg_dir.name)

        return plugins

    def load_module(self, module_path: Path, module_name: str) -> object | None:
        """动态加载模块"""
        try:
            if module_name in sys.modules:
                return sys.modules[module_name]

            spec = importlib.util.spec_from_file_location(
                module_name, module_path)
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create spec for: {module_path}")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except BaseException:
                if sys.modules.get(module_name) is module:
                    sys.modules.pop(module_name, None)
                raise

            # 局限：仍用裸名缓存；改成命名空间名会破坏现有跨包导入。
            self._loaded_modules.add(module_name)
            logger.info(f"Loaded plugin module: {module_name}")
            return module

        except Exception as e:
            logger.error(
                f"Failed to load module {module_path}: {e}", exc_info=True)
            return None

    def get_plugin_classes(self, module: object) -> list[type[BasePlugin]]:
        """从模块中提取插件类"""
        from plugin_sdk.plugin_base import BasePlugin

        plugin_classes: list[type[BasePlugin]] = []

        try:
            names = dir(module)
            module_name = getattr(module, "__name__", None)
        except Exception as e:
            logger.warning(
                f"Skipped unreadable plugin module: {e}")
            return plugin_classes

        for name in names:
            if name.startswith("_"):
                continue

            try:
                obj = getattr(module, name)
                obj_module = getattr(obj, "__module__", None)
                # 排除 from plugins.b import B 这类外部类，同时保留本包
                # __init__.py 通过 .plugin 子模块导出的真实插件类。
                local_module = (
                    obj_module == module_name
                    or (
                        isinstance(module_name, str)
                        and isinstance(obj_module, str)
                        and obj_module.startswith(f"{module_name}.")
                    )
                )
                is_plugin = (
                    isinstance(obj, type)
                    and issubclass(obj, BasePlugin)
                    and obj is not BasePlugin
                    and local_module
                )
            except Exception as e:
                logger.warning(
                    f"Skipped unreadable attribute {name!r} in plugin module "
                    f"{module_name or '<unknown>'}: {e}")
                continue
            if is_plugin:
                plugin_classes.append(obj)
                logger.debug(f"Found plugin class: {obj.__name__}")

        return plugin_classes

    def load_plugins_from_module(
        self,
        module_path: Path,
        module_name: str,
    ) -> list[BasePlugin]:
        """从模块加载所有插件实例"""
        plugins: list[BasePlugin] = []

        module = self.load_module(module_path, module_name)
        if module is None:
            return plugins

        plugin_classes = self.get_plugin_classes(module)

        for plugin_class in plugin_classes:
            try:
                info = self._get_plugin_info(plugin_class)
                plugin = plugin_class(info)
                plugins.append(plugin)
                logger.info(f"Instantiated plugin: {plugin.name}")
            except Exception as e:
                logger.error(
                    f"Failed to instantiate plugin {plugin_class.__name__}: {e}",
                    exc_info=True,
                )

        return plugins

    def _get_plugin_info(self, plugin_class: type[BasePlugin]) -> PluginInfo:
        """获取插件的元信息"""
        return plugin_class.plugin_info()

    def load_all(self) -> list[BasePlugin]:
        """加载所有发现的插件"""
        all_plugins: list[BasePlugin] = []

        discovered = self.discover_plugins()
        for module_path, module_name in discovered:
            try:
                plugins = self.load_plugins_from_module(module_path, module_name)
                all_plugins.extend(plugins)
            except Exception as e:
                logger.error(
                    f"Failed to load plugins from {module_path}: {e}",
                    exc_info=True,
                )

        logger.info(f"Loaded {len(all_plugins)} plugin(s)")
        return all_plugins

    def reload_module(self, module_name: str) -> bool:
        """重新加载模块"""
        if module_name not in self._loaded_modules:
            logger.warning(f"Module not registered by this loader: {module_name}")
            return False
        if module_name not in sys.modules:
            logger.warning(f"Module not loaded: {module_name}")
            return False

        try:
            importlib.reload(sys.modules[module_name])
            logger.info(f"Reloaded module: {module_name}")
            return True
        except Exception as e:
            logger.error(
                f"Failed to reload module {module_name}: {e}", exc_info=True)
            return False
