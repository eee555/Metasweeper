"""插件翻译文件、Qt 线程及语言事件顺序的回归测试。"""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QThread
from PySide6.QtWidgets import QApplication

from plugin_manager.dependency_scan import scan_plugin_dependencies
from plugin_manager.plugin_loader import PluginLoader
from plugin_manager.translations import TranslationManager
from shared_types.events import LanguageChangeEvent, GameFinishedEvent


def compile_catalog(directory: Path, locale: str, messages: list[tuple[str, str, str]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    contexts = "".join(
        f"<context><name>{context}</name><message><source>{source}</source>"
        f"<translation>{translation}</translation></message></context>"
        for context, source, translation in messages
    )
    ts = directory / f"{locale}.ts"
    ts.write_text(f'<?xml version="1.0" encoding="utf-8"?><TS version="2.1" language="{locale}">{contexts}</TS>', encoding="utf-8")
    from tests.plugin_manager.test_menu_layout import find_lrelease
    subprocess.run([str(find_lrelease()), str(ts), "-qm", str(directory / f"{locale}.qm")], check=True, capture_output=True)


def test_loader_package_root_and_single_file_are_independent(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    init = package / "__init__.py"
    init.write_text("", encoding="utf-8")
    single = tmp_path / "single.py"
    single.write_text("", encoding="utf-8")
    loader = PluginLoader([tmp_path])
    loader._dependency_statuses = {
        "package": scan_plugin_dependencies(init, "package"),
        "single": scan_plugin_dependencies(single, "single"),
    }
    loader._plugin_modules = {"exported-submodule-class": "package", "single-plugin": "single"}
    assert loader.get_plugin_translation_dir("exported-submodule-class") == package / "translations"
    assert loader.get_plugin_translation_dir("single-plugin") == tmp_path / "single.translations"
    assert loader.get_plugin_translation_dir("unknown") is None


def test_catalog_switch_shared_context_fallback_and_cleanup(qapp, tmp_path, monkeypatch):
    import plugin_manager.translations as translations

    monkeypatch.setattr(translations, "get_bundle_dir", lambda: tmp_path / "app")
    package, other = tmp_path / "one", tmp_path / "two"
    compile_catalog(package, "en_US", [("MyPluginWidget", "Hello", "Plugin hello"), ("Form", "Common", "Hijacked")])
    compile_catalog(other, "en_US", [("OtherPluginWidget", "Hello", "Other hello")])
    compile_catalog(package, "zh_CN", [("MyPluginWidget", "Hello", "你好")])
    compile_catalog(tmp_path / "app", "en_US", [("Form", "Common", "Core text")])
    (package / "de_DE.qm").write_bytes(b"invalid")
    manager = TranslationManager()
    try:
        manager.set_catalogs({"one": package, "two": other})
        manager.install("en_US", lambda: None)
        translate = QCoreApplication.translate
        assert translate("MyPluginWidget", "Hello") == "Plugin hello"
        assert translate("OtherPluginWidget", "Hello") == "Other hello"
        assert translate("Form", "Common") == "Core text"
        manager.set_catalogs({"two": other})
        assert translate("MyPluginWidget", "Hello") == "Hello"
        assert translate("OtherPluginWidget", "Hello") == "Other hello"
        manager.set_catalogs({"one": package})
        manager.install("de_DE", lambda: None)
        assert translate("MyPluginWidget", "Hello") == "Hello"
        manager.install("../en_US", lambda: None)
        assert translate("MyPluginWidget", "Hello") == "Hello"
        manager.install("en_US", lambda: None)
        manager.install("zh_CN", lambda: None)
        assert translate("MyPluginWidget", "Hello") == "你好"
    finally:
        manager.close()
    assert not manager._translators


def test_worker_language_event_waits_for_gui_and_preserves_event_order(qapp, qtbot, tmp_path, monkeypatch):
    from plugin_manager import plugin_manager as module
    import plugin_manager.translations as translations

    monkeypatch.setattr(translations, "get_bundle_dir", lambda: tmp_path / "app")
    catalog = tmp_path / "catalog"
    compile_catalog(catalog, "en_US", [("ThreadProbe", "Hello", "Translated")])
    installer = TranslationManager()
    installer.set_catalogs({"probe": catalog})
    manager = object.__new__(module.PluginManager)
    manager._events_lock = threading.Lock()
    from collections import deque
    manager._pending_events = deque()
    manager._events_ready = True
    manager._events_draining = False
    manager._shutdown_requested = False
    manager._translator_installer = installer
    seen = []
    class Dispatcher:
        def dispatch(self, tag, event):
            seen.append((type(event), QCoreApplication.translate("ThreadProbe", "Hello"), QThread.currentThread()))
    manager._dispatcher = Dispatcher()
    worker = threading.Thread(target=lambda: (
        manager._queue_zmq_event("language_change", LanguageChangeEvent(language="en_US")),
        manager._queue_zmq_event("game_finished", GameFinishedEvent()),
    ))
    try:
        worker.start()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert seen == []
        qtbot.waitUntil(lambda: len(seen) == 2, timeout=3000)
        assert [row[0] for row in seen] == [LanguageChangeEvent, GameFinishedEvent]
        assert [row[1] for row in seen] == ["Translated", "Translated"]
        assert seen[0][2] == QApplication.instance().thread()
    finally:
        installer.close()


def test_enable_loads_before_window_creation_and_disable_removes(qapp, tmp_path, monkeypatch):
    from plugin_manager import plugin_manager as module
    import plugin_manager.translations as translations

    monkeypatch.setattr(translations, "get_bundle_dir", lambda: tmp_path / "app")
    catalog = tmp_path / "catalog"
    compile_catalog(catalog, "en_US", [("LifecycleWidget", "Hello", "Enabled")])
    installer = TranslationManager()
    installer.install("en_US", lambda: None)
    manager = object.__new__(module.PluginManager)
    manager._plugins_lock = threading.RLock()
    manager._translator_installer = installer
    class Loader:
        def get_plugin_translation_dir(self, name):
            return catalog
    class Plugin:
        is_enabled = False
        def enable(self):
            assert QCoreApplication.translate("LifecycleWidget", "Hello") == "Enabled"
            self.is_enabled = True
        def disable(self):
            self.is_enabled = False
    plugin = Plugin()
    manager._loader = Loader()
    manager._plugins = {"probe": plugin}
    try:
        assert manager.enable_plugin("probe")
        assert QCoreApplication.translate("LifecycleWidget", "Hello") == "Enabled"
        assert manager.disable_plugin("probe")
        assert QCoreApplication.translate("LifecycleWidget", "Hello") == "Hello"
        assert manager.enable_plugin("probe")
    finally:
        installer.close()
