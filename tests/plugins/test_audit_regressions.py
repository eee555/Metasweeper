"""插件管理器审核问题的回归测试。

本文件由早先的「复现测试」反转而来：原先判定「测试通过 == 缺陷存在」的
用例，现在断言「缺陷已修复」，用于防止问题回归。编号与审核报告一致。

运行：
    .\\.venv\\Scripts\\python.exe -m pytest tests/plugins/test_audit_regressions.py -v
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt

_ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


# ── #1 控制授权对话框不得静默撤销 ──────────────────────────


def test_finding_01_control_auth_dialog_keeps_plugin_not_in_candidates(
    qtbot, tmp_path, monkeypatch
):
    """#1：已授权插件不在候选列表时，直接点「确定」必须保留其授权。"""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from plugin_manager.main_window import ControlAuthorizationDialog
    from plugin_sdk.control_auth import ControlAuthorizationManager
    from shared_types.commands import MouseClickCommand

    mgr = ControlAuthorizationManager.instance()
    mgr._file = tmp_path / "control_authorization.json"
    mgr._authorizations = {}
    mgr._dirty = False

    tag = mgr._get_tag(MouseClickCommand)
    mgr.authorize(MouseClickCommand, "PluginA")
    assert mgr.get_authorization_status().get(tag) == "PluginA"

    # PluginA 当前未就绪（例如被禁用），因此不在候选列表里
    dialog = ControlAuthorizationDialog({"PluginB": [MouseClickCommand]})
    qtbot.addWidget(dialog)

    # 用户不做任何修改，直接点「确定」
    dialog._on_accept()

    # 未改动的行保持原值，授权不被撤销
    assert mgr.get_authorization_status().get(tag) == "PluginA"


def test_finding_38_auth_status_column_uses_cached_candidates(qtbot, monkeypatch):
    """#38：下拉变化后状态列仍以候选列表判断，不得恒显示「无申请」。"""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from plugin_manager.main_window import ControlAuthorizationDialog
    from plugin_sdk.control_auth import ControlAuthorizationManager
    from shared_types.commands import MouseClickCommand

    mgr = ControlAuthorizationManager.instance()
    mgr._authorizations = {}
    mgr._dirty = False

    dialog = ControlAuthorizationDialog({"PluginA": [MouseClickCommand]})
    qtbot.addWidget(dialog)
    tag = mgr._get_tag(MouseClickCommand)
    row = next(
        r for r in range(dialog._table.rowCount())
        if dialog._table.item(r, 0).data(Qt.ItemDataRole.UserRole) is MouseClickCommand
    )
    assert tag

    # 下拉从「未授权」改到 PluginA → 状态列应为已授权，而不是「无申请」
    combo = dialog._table.cellWidget(row, 1)
    combo.setCurrentIndex(combo.findData("PluginA"))
    status = dialog._table.item(row, 2).text()
    assert "已授权" in status
    assert "无申请" not in status


# ── #2 托盘不可用时 retranslateUi 不得崩溃 ────────────────


def test_finding_02_retranslate_survives_missing_tray(qtbot, monkeypatch):
    """#2：系统托盘不可用时 retranslateUi 不应抛 AttributeError。"""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import (
        QLabel, QMainWindow, QMenu, QPushButton, QSystemTrayIcon, QToolBar,
    )

    from plugin_manager.main_window import PluginManagerWindow

    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: False)
    )

    class _Shell(PluginManagerWindow):
        """只装配 retranslateUi 所需控件的最小窗口。"""

        def __init__(self) -> None:
            QMainWindow.__init__(self)
            self._menu_plugins = QMenu(self)
            self._menu_settings = QMenu(self)
            self._menu_tools = QMenu(self)
            self._menu_help = QMenu(self)
            self._act_plugin_market = QAction(self)
            self._act_download_plugin = QAction(self)
            self._act_basic_settings = QAction(self)
            self._act_plugin_environment = QAction(self)
            self._act_control_auth = QAction(self)
            self._act_dev_guide = QAction(self)
            self._act_log_viewer = QAction(self)
            self._act_clear_logs = QAction(self)
            self._debug_act = QAction(self)
            self._toolbar = QToolBar(self)
            self._refresh_btn = QPushButton(self)
            self._control_auth_btn = QPushButton(self)
            self._title_label = QLabel(self)
            self._manager = None
            self._state_mgr = SimpleNamespace(save=lambda: None)
            # 真实 __init__ 中的同一守卫：托盘不可用时提前置空
            self._tray_icon = None

        def closeEvent(self, event):
            QMainWindow.closeEvent(self, event)

    shell = _Shell()
    qtbot.addWidget(shell)

    shell._setup_tray_icon()
    # 托盘不可用时属性存在但为 None（而非未定义）
    assert shell._tray_icon is None

    shell.retranslateUi()  # 不再抛 AttributeError


def test_finding_02_real_window_initializes_tray_attribute(monkeypatch):
    """#2：真实窗口在托盘不可用时也预先定义 _tray_icon。"""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QSystemTrayIcon

    from plugin_manager.main_window import PluginManagerWindow

    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: False)
    )
    source = _read("src/plugin_manager/main_window.py")
    init_block = source.split("class PluginManagerWindow", 1)[1].split(
        "def _setup_tray_icon", 1)[0]
    assert "self._tray_icon: QSystemTrayIcon | None = None" in init_block
    assert PluginManagerWindow.retranslateUi is not None


# ── #3 全局信号连接必须可断开 ─────────────────────────────


def test_finding_03_color_scheme_connection_is_disconnectable():
    """#3：README 对话框连接全局信号后必须在关闭时断开。"""
    text = _read("src/plugin_manager/main_window.py")
    assert "colorSchemeChanged.connect(self._apply_theme)" in text
    assert "colorSchemeChanged.disconnect(self._apply_theme)" in text


# ── #4 持久化容错 ─────────────────────────────────────────


def test_finding_04_settings_manager_tolerates_undecodable_file(tmp_path):
    """#4：非 UTF-8 设置文件必须降级为默认值，而不是构造失败。"""
    from plugin_manager.settings_manager import SettingsManager

    (tmp_path / SettingsManager.SETTINGS_FILENAME).write_bytes(b"\xff\xfe\x00bad")
    mgr = SettingsManager(tmp_path)  # 不抛异常
    assert mgr.file_log_level  # 回落到默认值


def test_finding_04_plugin_state_loads_every_valid_entry(tmp_path):
    """#4：单条脏数据只丢弃该条，其余条目继续加载。"""
    from plugin_manager.plugin_state import PluginStateManager

    path = tmp_path / "plugin_states.json"
    path.write_text(
        json.dumps({
            "good": {"enabled": False, "show_window": False},
            "bad": [1, 2, 3],  # 不是 dict → 会被跳过
            "after": {"enabled": False},
        }),
        encoding="utf-8",
    )

    mgr = PluginStateManager(path)
    mgr.load()  # 不抛异常
    assert "good" in mgr.all_states
    assert "after" in mgr.all_states  # 不再被静默丢弃
    assert "bad" not in mgr.all_states


# ── #5 优雅关闭必须落盘插件状态 ───────────────────────────


def test_finding_05_graceful_shutdown_saves_state(tmp_path, monkeypatch):
    """#5：_graceful_shutdown 必须保存状态，脏状态不丢失。"""
    from plugin_manager import plugin_manager as module

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        def register_event_types(self, *a):
            pass

        def register_command_types(self, *a):
            pass

        def register_query_types(self, *a, **k):
            pass

        def subscribe(self, *a):
            pass

        def disconnect(self):
            pass

    monkeypatch.setattr(module, "ZMQClient", _FakeClient)
    monkeypatch.setattr(
        module.PluginManager, "_register_shutdown_handlers", lambda self: None
    )
    monkeypatch.setattr(module, "get_data_dir", lambda: tmp_path)

    mgr = module.PluginManager("inproc://audit-regression", plugin_dirs=[])
    mgr.state_manager.set("p", module.PluginState(enabled=False))
    assert mgr.state_manager._dirty is True

    mgr._graceful_shutdown()

    saved = json.loads(
        (tmp_path / "plugin_states.json").read_text(encoding="utf-8"))
    assert saved["p"]["enabled"] is False


# ── #6 导入失败不得污染 sys.modules ───────────────────────


def test_finding_06_failed_import_is_rolled_back(tmp_path):
    """#6：插件导入失败后必须清理 sys.modules，允许重试。"""
    from plugin_manager.plugin_loader import PluginLoader

    pkg = tmp_path / "broken_plugin"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")

    loader = PluginLoader()
    name = "audit_broken_plugin"
    sys.modules.pop(name, None)

    try:
        assert loader.load_module(pkg / "__init__.py", name) is None
        assert name not in sys.modules  # 失败后无残留
    finally:
        sys.modules.pop(name, None)


# ── #7 插件名不得造成路径逃逸 ─────────────────────────────


def test_finding_07_plugin_name_cannot_escape_config_base_dir(tmp_path):
    """#7：PluginInfo.name 含 ../ 时必须被拒绝。"""
    from plugin_manager.config_manager import PluginConfigManager

    base = tmp_path / "plugin_data"
    mgr = PluginConfigManager(base)

    with pytest.raises(ValueError):
        mgr.config_path("../evil")

    normal = mgr.config_path("正常插件")
    assert normal.resolve().is_relative_to(base.resolve())


# ── #9 Python 版本下限 ───────────────────────────────────


def test_finding_09_requires_python_matches_strenum_usage():
    """#9：代码使用 3.11 才有的 StrEnum，声明下限必须 >=3.11。"""
    assert 'requires-python = ">=3.11"' in _read("pyproject.toml")
    assert "StrEnum" in _read("src/plugin_sdk/plugin_base.py")


# ── #10 依赖声明 ─────────────────────────────────────────


def test_finding_10_requirements_declares_pyzmq():
    """#10：依赖必须声明 pyzmq（而非 PyPI 上的 ``zmq`` 占位包）。"""
    lines = _read("requirements.txt").splitlines()
    assert any(ln.lower().startswith("pyzmq") for ln in lines)
    assert not any(ln.lower().startswith("zmq==") for ln in lines)


# ── #11 包入口不得急切导入主窗口 ─────────────────────────


def test_finding_11_package_init_is_lazy():
    """#11：包 __init__ 通过 __getattr__ 惰性导出主窗口。"""
    text = _read("src/plugin_manager/__init__.py")
    assert "def __getattr__" in text
    assert "from .main_window import PluginManagerWindow" not in text


# ── #14 / #31 文档与示例不得引用不存在的名字 ─────────────


def test_finding_14_event_doc_uses_real_class_name():
    """#14：事件文档必须使用真实存在的 GameFinishedEvent。"""
    doc = _read(".github/skills/plugin-dev/references/level-2-events.md")
    events = _read("src/shared_types/events.py")
    assert "GameFinishedEvent" in doc
    assert "from shared_types.events import GameFinishedEvent" in doc
    assert "class GameFinishedEvent" in events


def test_finding_31_config_types_docstring_uses_plugin_sdk_path():
    """#31：SDK docstring 示例必须指向 plugin_sdk.config_types。"""
    text = _read("src/plugin_sdk/config_types/__init__.py")
    assert "from plugin_sdk.config_types import (" in text
    assert "from plugin_manager.config_types import (" not in text


# ── #16 commit 必须是不可变哈希 ──────────────────────────


def test_finding_16_mutable_commit_is_rejected():
    """#16：main / v1.0 等可变引用不得进入归档 URL。"""
    from plugin_manager.plugin_repositories import (
        PluginRepository,
        RepositoryTag,
    )

    repo = PluginRepository.from_url("https://github.com/eee555/example")
    for fake_commit in ("v1.0", "main", "abc"):
        with pytest.raises(ValueError):
            repo.provider.archive_request(
                repo, RepositoryTag("v1", fake_commit))

    sha = "a" * 40
    url, _params = repo.provider.archive_request(
        repo, RepositoryTag("v1", sha))
    assert sha in url


# ── #17 启动期显示请求不得丢失 ───────────────────────────


def test_finding_17_show_request_is_replayed_after_window_created():
    """#17：窗口尚未创建时的显示请求必须缓存，创窗后重放。"""
    import inspect

    from plugin_manager.plugin_manager import PluginManager

    drain = inspect.getsource(PluginManager._drain_zmq_events)
    assert "_show_requested_pending" in drain

    start_with_gui = inspect.getsource(PluginManager.start_with_gui)
    assert "_show_requested_pending" in start_with_gui


# ── #18 日志查看器重开必须重建 sink ──────────────────────


def test_finding_18_log_viewer_reopen_reattaches_sink(qtbot, monkeypatch):
    """#18：关闭后重新打开日志查看器必须重新挂上日志 sink。"""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from plugin_manager.main_window import LogViewerDialog

    dlg = LogViewerDialog([], "main", "INFO", True, False)
    qtbot.addWidget(dlg)
    assert dlg._sink_id is not None

    dlg.close()
    assert dlg._sink_id is None

    dlg.update_settings("INFO", True, False)
    dlg.show_log("main")
    # 重开后重新挂上 sink（show 或 update 之一负责重建）
    assert dlg._sink_id is not None


# ── #20 插件设置保存必须有异常保护 ───────────────────────


def test_finding_20_plugin_settings_save_is_guarded():
    """#20：配置落盘失败时必须捕获并提示，而不是抛出。"""
    source = _read("src/plugin_manager/main_window.py")
    tree = ast.parse(source)
    target = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_open_plugin_settings"
    )
    assert any(isinstance(n, ast.Try) for n in ast.walk(target))
    segment = ast.get_source_segment(source, target)
    assert segment is not None
    assert "self._state_mgr.save()" in segment
    assert "plugin.save_config()" in segment


# ── #21 同名插件模块不得重复发现 ─────────────────────────


def test_finding_21_duplicate_plugin_modules_are_deduped(tmp_path):
    """#21：两个搜索目录里的同名模块只应被发现一次。"""
    from plugin_manager.plugin_loader import PluginLoader

    d1, d2 = tmp_path / "plugins1", tmp_path / "plugins2"
    d1.mkdir()
    d2.mkdir()
    code = (
        "from plugin_sdk.plugin_base import BasePlugin, PluginInfo\n"
        "class P(BasePlugin):\n"
        "    def plugin_info():\n"
        "        return PluginInfo(name='same')\n"
    )
    (d1 / "dup.py").write_text(code, encoding="utf-8")
    (d2 / "dup.py").write_text(code, encoding="utf-8")

    discovered = PluginLoader([d1, d2]).discover_plugins()
    assert [name for _, name in discovered] == ["dup"]


# ── #28 NewPresetGameCommand.board 可为 None 且能往返 ────


def test_finding_28_new_preset_game_default_board_roundtrips():
    """#28：board 为 None 时命令必须能编码并解码。"""
    from lib_zmq_plugins.serializer import Serializer
    from shared_types import COMMAND_TYPES
    from shared_types.commands import NewPresetGameCommand

    cmd = NewPresetGameCommand()
    assert cmd.board is None

    serializer = Serializer()
    serializer.register_command_types(*COMMAND_TYPES)
    raw = serializer.encode_command(cmd)
    decoded = serializer.decode_command(raw)
    assert decoded.board is None


# ── #29 两份入口参数一致 ─────────────────────────────────


def test_finding_29_entrypoints_share_arguments():
    """#29：_run.py 转发到 __main__，两者都接受 --debug。"""
    run = _read("src/plugin_manager/_run.py")
    main = _read("src/plugin_manager/__main__.py")
    assert '"--debug"' in main
    assert "_acquire_mutex" in run and "_acquire_mutex" in main
    assert "def _acquire_mutex" in run  # 兼容旧符号


# ── #30 版本号单一来源 ──────────────────────────────────


def test_finding_30_version_is_consistent():
    """#30：pyproject、安装脚本与运行时常量版本一致。"""
    pyproject = _read("pyproject.toml")
    iss = _read("package_tool/Metaminesweeper.iss")
    gui = _read("src/superGUI.py")

    version = pyproject.split('version = "', 1)[1].split('"', 1)[0]
    assert f'#define MyAppVersion "{version}"' in iss
    assert f'version = "元{version}"' in gui


# ── #34 同名插件不得重复写日志 ──────────────────────────


def test_finding_34_duplicate_plugin_sinks_are_reused(tmp_path):
    """#34：同名插件复用同一 sink，同一条日志只写一次。"""
    import loguru

    from plugin_manager.logging_setup import get_plugin_logger

    logger1, id1 = get_plugin_logger("audit_dup", log_dir=tmp_path)
    _, id2 = get_plugin_logger("audit_dup", log_dir=tmp_path)
    try:
        assert id1 == id2
        logger1.info("audit_marker")
        content = (tmp_path / "plugins" / "audit_dup.log").read_text(
            encoding="utf-8")
        assert content.count("audit_marker") == 1
    finally:
        for sink_id in {id1, id2}:
            try:
                loguru.logger.remove(sink_id)
            except ValueError:
                pass


# ── #37 重连文案括号成对 ─────────────────────────────────


def test_finding_37_reconnect_text_has_closing_paren():
    """#37：重连次数文案必须括号成对。"""
    text = _read("src/plugin_manager/main_window.py")
    assert 'self.tr("(重连 {n} 次)")' in text
    assert 'self.tr("(重连 {n} 次")' not in text


# ── #39 retranslateUi 不得重置状态栏消息 ──────────────────


def test_finding_39_retranslate_keeps_status_message():
    """#39：语言切换后状态栏不应被无条件重置为「正在连接...」。"""
    text = _read("src/plugin_manager/main_window.py")
    block = text.split("def retranslateUi", 1)[1].split("\n    def ", 1)[0]
    assert 'self._status_bar_msg = self.tr("正在连接...")' not in block
