"""Coverage tests for plugin_manager.plugin_info_dialog."""
from __future__ import annotations

import threading
from types import SimpleNamespace

import msgspec
import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGroupBox, QLabel, QListWidget

from plugin_manager import plugin_info_dialog as module
from plugin_manager.event_dispatcher import EventDispatcher, HandlerEntry
from plugin_manager.plugin_info_dialog import (
    _EVENT_TAG_NAMES, PluginInfoDialog, _build_tag_name_map, _get_struct_tag,
)
from shared_types.commands import NewGameCommand, SetSkinCommand
from shared_types.events import EVENT_TYPES, BoardUpdateEvent


@pytest.fixture(autouse=True)
def _offscreen(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")


class PlainCommand:
    """没有 msgspec tag 的普通声明类。"""
    __doc__ = "普通控制命令说明"


class CustomTagged(msgspec.Struct, tag="cov_custom_tag"):
    value: int = 0


class NoTag(msgspec.Struct):
    value: int = 0


class FakeAuth:
    def __init__(self, authorizations):
        self._authorizations = authorizations


class FakePlugin:
    def __init__(self, *, info, dispatcher=None):
        self.info = info
        self.name = info.name
        self._event_dispatcher = dispatcher


def _info(**overrides):
    values = {
        "name": "demo",
        "version": "2.3.4",
        "author": "Alice",
        "description": "演示插件",
        "required_controls": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _auth(monkeypatch, authorizations):
    monkeypatch.setattr(module.ControlAuthorizationManager, "instance",
                        classmethod(lambda cls: FakeAuth(authorizations)))


def _dialog(qtbot, monkeypatch, plugin):
    dialog = PluginInfoDialog(plugin)
    qtbot.addWidget(dialog)
    return dialog


def _texts(lst):
    return [lst.item(i).text() for i in range(lst.count())]


def test_get_struct_tag_and_build_tag_name_map():
    assert _get_struct_tag(BoardUpdateEvent) == "board_update"
    assert _get_struct_tag(CustomTagged) == "cov_custom_tag"
    assert _get_struct_tag(NoTag) is None
    assert _get_struct_tag(PlainCommand) is None
    assert _get_struct_tag(object()) is None

    mapping = _build_tag_name_map([
        BoardUpdateEvent, CustomTagged, NoTag, PlainCommand,
    ])
    assert mapping == {
        "board_update": "BoardUpdateEvent",
        "cov_custom_tag": "CustomTagged",
    }
    assert _EVENT_TAG_NAMES["board_update"] == "BoardUpdateEvent"
    assert len(_EVENT_TAG_NAMES) == len(EVENT_TYPES)


def test_dialog_shows_basic_info_and_empty_lists(qapp, qtbot, monkeypatch):
    _auth(monkeypatch, {"set_skin": "another-plugin"})
    dialog = _dialog(qtbot, monkeypatch, FakePlugin(info=_info(
        author="", description="", required_controls=None)))

    assert dialog.windowTitle().endswith("demo")
    assert not dialog.windowIcon().isNull()
    assert dialog.minimumWidth() == 560 and dialog.minimumHeight() == 540
    labels = [label.text() for label in dialog.findChildren(QLabel)]
    assert "demo" in labels and "2.3.4" in labels
    assert "-" in labels and "暂无描述" in labels
    assert any(box.title() == "基本信息" for box in dialog.findChildren(QGroupBox))
    assert _texts(dialog._events_list) == ["无"]
    assert _texts(dialog._permission_list) == ["无"]
    assert dialog._events_list.item(0).foreground().color() == QColor("#9e9e9e")
    assert dialog._permission_list.item(0).foreground().color() == QColor("#9e9e9e")


def test_make_list_group_is_readonly_and_add_items(qapp, qtbot, monkeypatch):
    _auth(monkeypatch, {})
    dialog = _dialog(qtbot, monkeypatch, FakePlugin(info=_info()))
    lst, box = dialog._make_list_group("额外分组")
    qtbot.addWidget(box)
    assert box.title() == "额外分组"
    assert lst.editTriggers() == QListWidget.EditTrigger.NoEditTriggers
    assert lst.selectionMode() == QListWidget.SelectionMode.NoSelection
    assert lst.maximumHeight() == 120

    dialog._add_items(lst, ["one", "two"])
    assert _texts(lst) == ["one", "two"]
    dialog._add_items(lst, [])
    assert _texts(lst) == ["one", "two", "无"]
    box.deleteLater()


def test_dialog_collects_and_displays_subscribed_events(qapp, qtbot, monkeypatch):
    _auth(monkeypatch, {})
    dispatcher = EventDispatcher()
    plugin = FakePlugin(info=_info(), dispatcher=dispatcher)
    other = FakePlugin(info=_info(name="other"))
    dispatcher.subscribe("board_update", lambda e: None, plugin=plugin)
    dispatcher.subscribe("board_update", lambda e: None, plugin=other, priority=1)
    dispatcher.subscribe("unknown_event", lambda e: None, plugin=plugin)
    dispatcher.subscribe("other_only", lambda e: None, plugin=other)

    dialog = _dialog(qtbot, monkeypatch, plugin)
    assert dialog._collect_subscribed_events() == ["board_update", "unknown_event"]
    assert _texts(dialog._events_list) == [
        "BoardUpdateEvent (board_update)", "unknown_event",
    ]
    assert dialog._display_tag("board_update", _EVENT_TAG_NAMES) == (
        "BoardUpdateEvent (board_update)")
    assert dialog._display_tag("mystery", _EVENT_TAG_NAMES) == "mystery"
    assert dialog._display_tag("board_update", {}) == "board_update"


def test_collect_subscribed_events_without_dispatcher(qapp, qtbot, monkeypatch):
    _auth(monkeypatch, {})
    dialog = _dialog(qtbot, monkeypatch, FakePlugin(info=_info()))
    assert dialog._collect_subscribed_events() == []
    assert _texts(dialog._events_list) == ["无"]


def test_collect_subscribed_events_swallows_registry_errors(qapp, qtbot, monkeypatch):
    _auth(monkeypatch, {})
    broken = SimpleNamespace(
        _lock=threading.RLock(),
        _handlers={"board_update": [SimpleNamespace(plugin=None)]},
    )
    plugin = FakePlugin(info=_info(), dispatcher=broken)
    broken._handlers["board_update"][0].plugin = plugin
    dialog = _dialog(qtbot, monkeypatch, plugin)
    assert dialog._collect_subscribed_events() == ["board_update"]

    class BadDict(dict):
        def items(self):
            raise RuntimeError("registry broken")

    plugin._event_dispatcher = SimpleNamespace(
        _lock=threading.RLock(), _handlers=BadDict())
    assert dialog._collect_subscribed_events() == []


def test_collect_authorized_tags_filters_by_plugin_name_and_handles_error(
        qapp, qtbot, monkeypatch):
    _auth(monkeypatch, {
        "new_random_game": "demo", "set_skin": "demo", "mouse_click": "other",
    })
    dialog = _dialog(qtbot, monkeypatch, FakePlugin(info=_info()))
    assert dialog._collect_authorized_tags() == ["new_random_game", "set_skin"]

    def boom(cls):
        raise RuntimeError("auth unavailable")

    monkeypatch.setattr(module.ControlAuthorizationManager, "instance",
                        classmethod(boom))
    assert dialog._collect_authorized_tags() == []


def test_permission_texts_union_of_declared_and_authorized(qapp, qtbot, monkeypatch):
    _auth(monkeypatch, {
        "new_random_game": "demo", "set_skin": "demo", "unknown_tag": "demo",
        "init_open": "demo", "ghost_no_hint": "demo",
    })
    monkeypatch.setitem(module.COMMAND_LABELS, "ghost_no_hint", "幽灵命令")
    plugin = FakePlugin(info=_info(required_controls=[
        NewGameCommand, SetSkinCommand, PlainCommand, CustomTagged, NoTag,
    ]))
    dialog = _dialog(qtbot, monkeypatch, plugin)

    texts = dialog._permission_texts(plugin.info.required_controls,
                                     set(dialog._collect_authorized_tags()))
    assert len(texts) == 8
    new_game = next(entry for entry in texts if "(new_random_game)" in entry[0])
    assert new_game[1] is True and "NewGameCommand" in new_game[2]
    plain = next(entry for entry in texts if entry[0] == "PlainCommand")
    assert plain[1] is False and "PlainCommand" in plain[2]
    custom = next(entry for entry in texts if "(cov_custom_tag)" in entry[0])
    assert custom[1] is False
    no_tag = next(entry for entry in texts if entry[0] == "NoTag")
    assert no_tag[1] is False
    authorized_only = next(entry for entry in texts if "(init_open)" in entry[0])
    assert authorized_only[1] is True and "初始化翻开" in authorized_only[2]
    unknown = next(entry for entry in texts if entry[0] == "unknown_tag")
    assert unknown == ("unknown_tag", True, "unknown_tag")
    ghost = next(entry for entry in texts if "幽灵命令" in entry[0])
    assert ghost == ("幽灵命令 (ghost_no_hint)", True, "幽灵命令")
    assert all(entry[1] is True for entry in texts[5:])


def test_permission_items_granted_and_not_granted(qapp, qtbot, monkeypatch):
    _auth(monkeypatch, {"new_random_game": "demo"})
    plugin = FakePlugin(info=_info(required_controls=[
        NewGameCommand, SetSkinCommand, PlainCommand,
    ]))
    dialog = _dialog(qtbot, monkeypatch, plugin)

    items = dialog._permission_list
    assert items.count() == 3
    granted = items.item(0)
    assert granted.text().endswith("已授予")
    assert not granted.icon().isNull()
    assert granted.toolTip() and "NewGameCommand" in granted.toolTip()
    assert granted.foreground().color() != QColor("#9e9e9e")

    not_granted = items.item(1)
    assert not_granted.text().endswith("未授予")
    assert not_granted.foreground().color() == QColor("#9e9e9e")
    plain = items.item(2)
    assert plain.text().endswith("未授予")
    assert "类名: PlainCommand" in plain.toolTip()


def test_permission_texts_with_only_unknown_tag_and_no_hint(qapp, qtbot, monkeypatch):
    _auth(monkeypatch, {})
    monkeypatch.setitem(module.COMMAND_LABELS, "label_only", "仅有标签")
    monkeypatch.setitem(module.COMMAND_HINTS, "label_only", "")
    dialog = _dialog(qtbot, monkeypatch, FakePlugin(info=_info()))
    assert dialog._permission_texts([], {"label_only"}) == [
        ("仅有标签 (label_only)", True, "仅有标签"),
    ]


def test_permission_items_empty_when_no_declarations_or_authorizations(
        qapp, qtbot, monkeypatch):
    _auth(monkeypatch, {})
    dialog = _dialog(qtbot, monkeypatch, FakePlugin(info=_info()))
    assert dialog._permission_texts([], set()) == []
    dialog._add_permission_items(dialog._permission_list, [], set())
    assert _texts(dialog._permission_list) == ["无", "无"]


def test_load_data_with_falsey_required_controls_and_authorization_error(
        qapp, qtbot, monkeypatch):
    monkeypatch.setattr(module.ControlAuthorizationManager, "instance",
                        classmethod(lambda cls: (_ for _ in ()).throw(
                            RuntimeError("no auth"))))
    dialog = _dialog(qtbot, monkeypatch, FakePlugin(info=_info(required_controls=[])))
    assert _texts(dialog._events_list) == ["无"]
    assert _texts(dialog._permission_list) == ["无"]


def test_handler_entry_snapshot_is_used_by_dialog(qapp, qtbot, monkeypatch):
    _auth(monkeypatch, {})
    plugin = FakePlugin(info=_info())
    dispatcher = EventDispatcher()
    dispatcher.subscribe("board_update", lambda e: None,
                         plugin=plugin, priority=7)
    plugin._event_dispatcher = dispatcher
    dialog = _dialog(qtbot, monkeypatch, plugin)
    assert isinstance(dispatcher.get_handlers("board_update")[0], HandlerEntry)
    assert _texts(dialog._events_list) == ["BoardUpdateEvent (board_update)"]
