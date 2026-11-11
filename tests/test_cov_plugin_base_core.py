"""plugin_base.py 覆盖率补测：模块级工厂/枚举、属性、README、配置、GUI 工具。

全部使用轻量 fake/stub，不启动真实线程或 ZMQ。
"""
from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from loguru import logger
from PySide6.QtCore import QCoreApplication, QEvent, Qt, QTimer, QEventLoop
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

import plugin_manager.app_paths as app_paths
import plugin_manager.config_manager as config_manager_mod
import plugin_manager.logging_setup as logging_setup
from plugin_sdk import config_types
from plugin_sdk.plugin_base import (
    BasePlugin,
    LogLevel,
    PluginInfo,
    PluginLifecycle,
    WindowMode,
    _GuiCallHandler,
    _ServiceProxy,
    make_plugin_icon,
)


# ── 局部 fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def app(monkeypatch):
    """offscreen QApplication + 屏蔽真实日志/数据目录副作用。"""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "plugin_manager.logging_setup.get_plugin_logger",
        lambda *args, **kwargs: (logger, None),
    )
    monkeypatch.setattr(
        "plugin_manager.logging_setup.set_plugin_log_level",
        lambda *args, **kwargs: None,
    )
    return instance


class CorePlugin(BasePlugin):
    """最小探针插件：other_info=None 简化构造。"""

    @classmethod
    def plugin_info(cls):
        return PluginInfo(name="cov-core", other_info=None)

    def _setup_subscriptions(self):
        pass


def make_plugin(app, info=None):
    return CorePlugin(info or CorePlugin.plugin_info())


# ── 模块级工厂与枚举 ──────────────────────────────────────────────────────

def test_make_plugin_icon_produces_qicon(app):
    icon = make_plugin_icon("#e65100", "📝", 32)
    assert isinstance(icon, QIcon)
    assert not icon.isNull()
    custom = make_plugin_icon()
    assert isinstance(custom, QIcon)
    assert not custom.isNull()
    # 自定义颜色与默认颜色应产生不同的图像数据（缓存键不同）
    assert icon.cacheKey() != custom.cacheKey()


def test_window_mode_values_and_labels():
    assert WindowMode._values() == ["tab", "detached", "closed"]
    labels = WindowMode.LABELS()
    assert labels[WindowMode.TAB] == "标签页内"
    assert labels[WindowMode.DETACHED] == "独立窗口"
    assert labels[WindowMode.CLOSED] == "不自动加载"
    assert set(labels) == set(WindowMode)


def test_log_level_values_and_labels():
    assert LogLevel._values() == [
        "TRACE", "DEBUG", "INFO", "WARNING", "ERROR",
    ]
    labels = LogLevel.LABELS()
    assert set(labels) == set(LogLevel)
    assert labels[LogLevel.TRACE].startswith("TRACE")
    assert labels[LogLevel.ERROR].startswith("ERROR")


def test_plugin_lifecycle_enum_values():
    assert [s.value for s in PluginLifecycle] == [
        "NEW", "INITIALIZING", "READY", "SHUTTING_DOWN", "STOPPED",
    ]


def test_service_proxy_forwards_and_rejects_kwargs(app):
    plugin = make_plugin(app)
    calls = []
    plugin._call_service = lambda protocol, name, *args, timeout=10.0: (
        calls.append((protocol, name, args, timeout)) or "result"
    )

    class Proto:
        pass

    proxy = _ServiceProxy(plugin, Proto)
    assert repr(proxy) == "<ServiceProxy: Proto>"
    assert proxy.do_it(1, 2, timeout=2.5) == "result"
    assert calls == [(Proto, "do_it", (1, 2), 2.5)]

    with pytest.raises(TypeError, match="keyword arguments is not supported"):
        proxy.do_it(1, value=2)
    assert len(calls) == 1  # kwargs 路径在调用 _call_service 之前就抛错


def test_gui_call_handler_success_and_exception(app, caplog):
    handler = _GuiCallHandler()
    seen = []
    handler.execute(lambda a, b=0: seen.append((a, b)), (3,), {"b": 4})
    assert seen == [(3, 4)]

    def boom():
        raise RuntimeError("gui boom")

    with caplog.at_level(logging.ERROR, logger="plugin_sdk.plugin_base"):
        handler.execute(boom, (), {})  # 异常被吞掉，不应向外抛
    assert any("GUI callback error: gui boom" in r.message for r in caplog.records)


def test_base_plugin_without_plugin_info_raises(app, monkeypatch):
    class MissingInfo(BasePlugin):
        def _setup_subscriptions(self):
            pass

    # 绕过 classmethod 描述符，直接令 type(self).plugin_info 与基类属性
    # 恒等，触发 __init__ 内的抽象检查（bound method 每次取都是新对象，
    # 无法用 is 命中，故用普通对象哨兵模拟「未重写」）。
    import plugin_sdk.plugin_base as plugin_base_mod
    monkeypatch.setattr(BasePlugin, "plugin_info", object())
    with pytest.raises(TypeError, match="without implementing 'plugin_info"):
        MissingInfo(PluginInfo(name="no-info", other_info=None))


def test_plugin_info_defaults_and_custom_fields(app):
    default = PluginInfo(name="defaults")
    assert default.other_info is config_types.OtherInfoBase
    assert default.version == "1.0.0"
    assert default.enabled is True
    assert default.priority == 100
    assert default.show_window is True
    assert default.window_mode is WindowMode.TAB
    assert default.log_level is LogLevel.INFO
    assert default.icon is None
    assert default.required_controls == []

    custom = PluginInfo(
        name="custom", version="9.9", author="me", description="d",
        enabled=False, priority=7, show_window=False,
        window_mode=WindowMode.DETACHED, log_level=LogLevel.ERROR,
        required_controls=[int],
    )
    assert custom.version == "9.9" and custom.author == "me"
    assert custom.enabled is False and custom.priority == 7
    assert custom.window_mode is WindowMode.DETACHED
    assert custom.log_level is LogLevel.ERROR
    assert custom.required_controls == [int]
    assert PluginInfo(name="x").required_controls is not custom.required_controls


# ── 构造与属性 ────────────────────────────────────────────────────────────

def test_constructor_wires_thread_signals_and_state(app):
    info = PluginInfo(
        name="wired", version="2.0", enabled=False,
        log_level=LogLevel.WARNING, other_info=None,
    )
    plugin = CorePlugin(info)
    assert plugin.info is info
    assert plugin.name == "wired"
    assert plugin.is_enabled is False
    assert plugin.lifecycle is PluginLifecycle.NEW
    assert plugin.is_ready is False
    assert plugin.log_level is LogLevel.WARNING
    assert plugin.client is None
    assert plugin.widget is None
    assert plugin._thread.objectName() == "plugin-wired"
    assert not plugin._thread.isRunning()
    assert plugin._gui_handler.thread() is QCoreApplication.instance().thread()
    assert plugin.thread() is plugin._thread
    assert repr(plugin) == "<Plugin wired v2.0 [NEW]>"


def test_abstract_plugin_info_body_is_reachable():
    # 覆盖 @abstractmethod 装饰的基类方法体（docstring 语句）
    assert BasePlugin.plugin_info() is None


def test_simple_properties_and_setters(app):
    plugin = make_plugin(app)
    assert plugin.info.name == "cov-core"
    assert plugin.name == "cov-core"
    assert plugin.is_ready is False
    assert plugin.lifecycle is PluginLifecycle.NEW
    assert plugin.widget is None
    assert plugin.client is None
    assert plugin.log_level is LogLevel.INFO
    assert plugin.config_file_path is None  # other_info=None -> 无配置管理器

    client = object()
    plugin.set_client(client)
    assert plugin.client is client

    dispatcher = object()
    plugin.set_event_dispatcher(dispatcher)
    assert plugin._event_dispatcher is dispatcher

    # other_info 未设置时访问应抛 AttributeError（记录真实行为）
    with pytest.raises(AttributeError):
        _ = plugin.other_info


def test_locked_context_manager_is_reentrant(app):
    plugin = make_plugin(app)
    with plugin.locked():
        with plugin.locked():  # RLock 可重入
            plugin._generation += 1
    assert plugin._generation == 1


def test_data_dir_is_cached_and_uses_app_paths(app, tmp_path, monkeypatch):
    plugin = make_plugin(app)
    calls = []

    def fake(plugin_class):
        calls.append(plugin_class)
        return tmp_path / plugin_class.__name__

    monkeypatch.setattr(app_paths, "get_plugin_data_dir", fake)
    first = plugin.data_dir
    second = plugin.data_dir
    assert first == second == tmp_path / "CorePlugin"
    assert calls == [CorePlugin]  # 只解析一次，之后走缓存


def test_plugin_dir_resolves_from_module_file(app, tmp_path, monkeypatch):
    plugin = make_plugin(app)
    fake_module = SimpleNamespace(__file__=str(tmp_path / "nested" / "plugin.py"))
    monkeypatch.setattr(
        "plugin_sdk.plugin_base.inspect.getmodule", lambda cls: fake_module
    )
    assert plugin.plugin_dir == (tmp_path / "nested").resolve()


def test_plugin_dir_falls_back_to_cwd_when_module_has_no_file(app, monkeypatch):
    plugin = make_plugin(app)
    monkeypatch.setattr(
        "plugin_sdk.plugin_base.inspect.getmodule",
        lambda cls: SimpleNamespace(),  # 无 __file__
    )
    assert plugin.plugin_dir == Path.cwd()


# ── README ────────────────────────────────────────────────────────────────

def _patch_readme_env(monkeypatch, plugin, directory: Path, module_file: str | None):
    """把 plugin_dir 与 inspect.getmodule 固定到临时目录。"""
    monkeypatch.setattr(
        CorePlugin, "plugin_dir",
        property(lambda self: directory),
    )
    monkeypatch.setattr(
        "plugin_sdk.plugin_base.inspect.getmodule",
        lambda cls: SimpleNamespace(__file__=module_file) if module_file else SimpleNamespace(),
    )


def test_get_readme_text_delegates_to_load_READMD(app, monkeypatch):
    plugin = make_plugin(app)
    monkeypatch.setattr(plugin, "load_READMD", lambda: "custom-readme")
    assert plugin.get_readme_text() == "custom-readme"


@pytest.mark.parametrize("filename", ["README.md", "readme.md", "single_README.md"])
def test_load_readmd_all_candidates(app, tmp_path, monkeypatch, filename):
    plugin = make_plugin(app)
    (tmp_path / filename).write_text("hello " + filename, encoding="utf-8")
    _patch_readme_env(
        monkeypatch, plugin, tmp_path,
        str(tmp_path / "single.py") if filename == "single_README.md" else None,
    )
    assert plugin.load_READMD() == "hello " + filename


def test_load_readmd_prioritizes_readme_md_over_single_file_variant(app, tmp_path, monkeypatch):
    plugin = make_plugin(app)
    (tmp_path / "README.md").write_text("CAPS", encoding="utf-8")
    (tmp_path / "single_README.md").write_text("single", encoding="utf-8")
    _patch_readme_env(monkeypatch, plugin, tmp_path, str(tmp_path / "single.py"))
    assert plugin.load_READMD() == "CAPS"


def test_load_readmd_returns_empty_when_no_file(app, tmp_path, monkeypatch):
    plugin = make_plugin(app)
    _patch_readme_env(monkeypatch, plugin, tmp_path, str(tmp_path / "single.py"))
    assert plugin.load_READMD() == ""


def test_load_readmd_returns_empty_on_oserror(app, tmp_path, monkeypatch):
    plugin = make_plugin(app)
    target = tmp_path / "README.md"
    target.write_text("x", encoding="utf-8")
    _patch_readme_env(monkeypatch, plugin, tmp_path, None)
    monkeypatch.setattr(
        Path, "is_file", lambda self: True,
    )
    monkeypatch.setattr(
        Path, "read_text",
        lambda self, *a, **k: (_ for _ in ()).throw(OSError("denied")),
    )
    assert plugin.load_READMD() == ""


# ── 配置 / 图标 / 日志级别 ────────────────────────────────────────────────

class _RealConfig(config_types.OtherInfoBase):
    enabled = config_types.BoolConfig(True, "启用")
    count = config_types.IntConfig(3, "次数", min_value=0, max_value=100)


def test_real_other_info_loads_saves_and_emits_config_changed(
    app, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        app_paths, "get_plugin_data_dir", lambda cls: tmp_path / cls.__name__
    )

    class ConfigPlugin(CorePlugin):
        @classmethod
        def plugin_info(cls):
            return PluginInfo(name="cfg-plugin", other_info=_RealConfig)

    plugin = ConfigPlugin(ConfigPlugin.plugin_info())
    assert isinstance(plugin.other_info, _RealConfig)
    assert plugin.other_info.enabled is True
    assert plugin.other_info.count == 3
    assert plugin._config_manager is not None

    # 配置文件路径由 config_manager 计算（不触发 config_path 缺陷路径）
    expected = plugin._config_manager._config_path("cfg-plugin")
    assert expected.parent == tmp_path / "ConfigPlugin" / "cfg-plugin"

    # 修改配置值 -> 回调转发到 GUI 线程 -> config_changed 信号
    seen = []
    plugin.config_changed.connect(
        lambda name, value: seen.append((name, value)), Qt.DirectConnection
    )
    plugin.other_info.count = 9
    _drain_gui(app)
    assert ("count", 9) in seen

    # 直接覆盖 _emit_config_changed（主线程发射信号的语句）
    seen.clear()
    plugin._emit_config_changed("enabled", False)
    assert seen == [("enabled", False)]

    # save_config 真的写盘并可通过 manager 读回
    plugin.save_config()
    assert expected.is_file()
    reloaded = _RealConfig()
    plugin._config_manager.load("cfg-plugin", reloaded)
    assert reloaded.count == 9


def test_on_config_changed_forwards_via_run_on_gui(app, monkeypatch):
    plugin = make_plugin(app)
    calls = []
    monkeypatch.setattr(
        plugin, "run_on_gui",
        lambda func, *args, **kwargs: calls.append((func, args, kwargs)),
    )
    plugin._on_config_changed("field", 42)
    assert calls == [(plugin._emit_config_changed, ("field", 42), {})]


def test_save_config_noop_without_manager(app):
    plugin = make_plugin(app)  # other_info=None
    assert plugin._config_manager is None
    plugin.save_config()  # 不应抛 AttributeError
    assert plugin.config_file_path is None


def test_set_log_level_accepts_string_and_enum(app, monkeypatch):
    plugin = make_plugin(app)
    recorded = []
    monkeypatch.setattr(
        "plugin_manager.logging_setup.set_plugin_log_level",
        lambda sink, level: recorded.append((sink, level)),
    )
    plugin.set_log_level("warning")
    assert plugin.log_level is LogLevel.WARNING
    assert recorded[-1] == (None, "WARNING")

    plugin.set_log_level(LogLevel.ERROR)
    assert plugin.log_level is LogLevel.ERROR
    assert recorded[-1] == (None, "ERROR")

    with pytest.raises(ValueError):
        plugin.set_log_level("NOT_A_LEVEL")


def test_plugin_icon_custom_and_default(app):
    custom = make_plugin_icon("#123456", "X", 16)
    plugin = CorePlugin(PluginInfo(name="icon-custom", icon=custom, other_info=None))
    assert plugin.plugin_icon is custom

    plain = make_plugin(app)
    generated = plain.plugin_icon
    assert isinstance(generated, QIcon) and not generated.isNull()


def test_plugin_icon_svg_priority_and_invalid_fallback(app, tmp_path, monkeypatch):
    monkeypatch.setattr(CorePlugin, "plugin_dir", property(lambda self: tmp_path))
    custom = make_plugin_icon("#123456", "X", 16)
    plugin = CorePlugin(PluginInfo(name="icon-svg", icon=custom, other_info=None))
    path = tmp_path / "icon.svg"
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
                    '<rect width="16" height="16" fill="#ff0000"/></svg>', encoding="utf-8")
    icon = plugin.plugin_icon
    assert not icon.isNull()
    assert icon.pixmap(16, 16).toImage().pixelColor(8, 8).name() == "#ff0000"
    path.write_text("<invalid>", encoding="utf-8")
    assert plugin.plugin_icon is custom
    path.unlink()
    assert plugin.plugin_icon is custom
    plugin.info.icon = None
    assert not plugin.plugin_icon.isNull()


# ── GUI / widget 工具 ─────────────────────────────────────────────────────

def _drain_gui(app):
    """派发主线程 queued 调用（gui_call 连接的 _GuiCallHandler）。"""
    for _ in range(5):
        QCoreApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_run_on_gui_dispatches_with_args_and_kwargs(app):
    plugin = make_plugin(app)
    seen = []
    plugin.run_on_gui(lambda a, b=0: seen.append((a, b)), 5, b=7)
    _drain_gui(app)
    assert seen == [(5, 7)]


def test_run_on_widget_branches(app):
    plugin = make_plugin(app)
    seen = []

    # 1) widget 为 None -> 直接跳过，不投递
    plugin.run_on_widget(lambda w: seen.append("never"))
    _drain_gui(app)
    assert seen == []

    # 2) 正常执行
    widget = QWidget()
    plugin._widget = widget
    plugin.run_on_widget(lambda w: seen.append(w))
    _drain_gui(app)
    assert seen == [widget]

    # 3) 投递后 widget 被替换 -> 跳过旧回调
    plugin.run_on_widget(lambda w: seen.append("stale"))
    plugin._widget = QWidget()
    _drain_gui(app)
    assert seen == [widget]

    # 4) func 抛 RuntimeError -> 被吞掉
    plugin._widget = widget
    plugin.run_on_widget(lambda w: (_ for _ in ()).throw(RuntimeError("deleted")))
    _drain_gui(app)  # 不应向外抛
    assert seen == [widget]

    widget.deleteLater()
    plugin._widget.deleteLater()
    _drain_gui(app)


def test_ensure_widget_and_close_widget_hooks(app):
    plugin = make_plugin(app)
    created, closed = [], []
    plugin.on_widget_created = created.append
    plugin.on_widget_closed = closed.append

    # 无界面插件：_create_widget 返回 None
    assert plugin.ensure_widget() is None
    assert created == []

    # 已有 widget 时早退，不重复创建
    first = QWidget()
    plugin._widget = first
    assert plugin.ensure_widget() is first
    assert created == []

    # close_widget 早退分支
    plugin._widget = None
    plugin.close_widget()
    assert closed == []

    # 真实创建 + 钩子
    plugin._create_widget = lambda: QWidget()
    new_widget = plugin.ensure_widget()
    assert new_widget is not None and new_widget is plugin.widget
    assert created == [new_widget]

    # 关闭：清空引用、触发钩子、deleteLater
    plugin.close_widget()
    assert plugin.widget is None
    assert closed == [new_widget]
    _drain_gui(app)
    plugin.ensure_widget()
    _drain_gui(app)


def test_default_noop_hooks_are_callable(app):
    plugin = make_plugin(app)
    assert plugin._create_widget() is None
    assert plugin.on_initialized() is None
    assert plugin.validate_config({}) == {}
    assert plugin.on_shutdown() is None
    assert plugin.on_control_auth_changed(int, True) is None
    assert plugin._setup_subscriptions() is None


def test_widget_created_and_closed_base_hooks(app):
    plugin = make_plugin(app)
    widget = QWidget()
    assert plugin.on_widget_created(widget) is None
    assert plugin.on_widget_closed(widget) is None
    widget.deleteLater()
    _drain_gui(app)
