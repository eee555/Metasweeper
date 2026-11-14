"""Coverage for the control authorization dialog."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QComboBox, QTableWidgetItem

from plugin_manager.main_window import ControlAuthorizationDialog
from shared_types.commands import (
    COMMAND_TYPES,
    MouseClickCommand,
    NewGameCommand,
    SetSkinCommand,
)
import plugin_manager.main_window as mw


class _DupMouseClick:
    __struct_config__ = SimpleNamespace(tag="mouse_click")


class _NoTag:
    pass


class _FakeAuth:
    def __init__(self, types, status=None, bad_tags=()):
        self.types = list(types)
        self.status = dict(status or {})
        self.bad_tags = set(bad_tags)
        self.calls: list[tuple] = []

    @staticmethod
    def instance():
        raise AssertionError("patch _FakeAuth.instance in each test")

    def _get_tag(self, cmd_type):
        cfg = getattr(cmd_type, "__struct_config__", None)
        tag = getattr(cfg, "tag", None) if cfg is not None else None
        if tag is None or tag in self.bad_tags:
            raise ValueError("no tag")
        return str(tag)

    def get_all_control_types(self):
        return list(self.types)

    def get_authorization_status(self):
        return dict(self.status)

    def authorize(self, cmd_type, plugin_name):
        self.calls.append(("authorize", cmd_type, plugin_name))

    def revoke(self, cmd_type):
        self.calls.append(("revoke", cmd_type, None))

    def save(self):
        self.calls.append(("save", None, None))


@pytest.fixture(autouse=True)
def offscreen(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(mw, "get_data_dir", lambda: None)
    monkeypatch.setattr(mw, "action_icon",
                        lambda _name: QIcon(QPixmap(16, 16)))
    monkeypatch.setattr(mw, "set_button_box_icons", lambda _box: None)


def _build(qtbot, monkeypatch, controls, *, types=None, status=None,
           bad_tags=()):
    fake = _FakeAuth(types if types is not None else COMMAND_TYPES,
                     status=status, bad_tags=bad_tags)
    monkeypatch.setattr(mw.ControlAuthorizationManager, "instance",
                        staticmethod(lambda: fake))
    dlg = ControlAuthorizationDialog(controls)
    qtbot.addWidget(dlg)
    return dlg, fake


def test_empty_controls_builds_disabled_combos(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(mw, "get_data_dir", lambda: tmp_path)
    dlg, fake = _build(qtbot, monkeypatch, {})
    assert dlg._table.rowCount() == len(COMMAND_TYPES)
    assert dlg._table.columnCount() == 3
    assert len(dlg._combos) == len(COMMAND_TYPES)
    for row in range(dlg._table.rowCount()):
        combo = dlg._table.cellWidget(row, 1)
        assert isinstance(combo, QComboBox)
        assert combo.isEnabled() is False
        assert combo.currentData() is None
        assert dlg._table.item(row, 2).text() == "无申请"
    assert fake.status == {}


def test_multiple_eligible_plugins_and_existing_authorization(qtbot, monkeypatch):
    controls = {
        "z-plugin": [MouseClickCommand],
        "a-plugin": [_DupMouseClick],
        "other": [NewGameCommand],
    }
    dlg, fake = _build(
        qtbot, monkeypatch, controls,
        types=[MouseClickCommand, NewGameCommand],
        status={"mouse_click": "a-plugin"},
    )
    mouse_combo = dlg._table.cellWidget(0, 1)
    assert mouse_combo.isEnabled() is True
    assert [mouse_combo.itemText(i) for i in range(mouse_combo.count())] == [
        "未授权", "a-plugin", "z-plugin",
    ]
    assert mouse_combo.currentData() == "a-plugin"
    assert "已授权" in dlg._table.item(0, 2).text()
    assert "mouse_click" in dlg._table.item(0, 0).text()
    assert dlg._table.item(0, 0).data(Qt.ItemDataRole.UserRole) is MouseClickCommand

    other_combo = dlg._table.cellWidget(1, 1)
    assert other_combo.count() == 2
    assert other_combo.itemText(1) == "other"
    assert "未授权" in dlg._table.item(1, 2).text()


def test_single_eligible_plugin_without_status_and_combo_change(qtbot, monkeypatch):
    dlg, _ = _build(
        qtbot, monkeypatch, {"solo": [SetSkinCommand]},
        types=[SetSkinCommand], status={"set_skin": None},
    )
    combo = dlg._table.cellWidget(0, 1)
    assert combo.isEnabled()
    assert combo.currentData() is None
    before = dlg._table.item(0, 2).text()

    combo.setCurrentIndex(combo.findData("solo"))
    granted = dlg._table.item(0, 2).text()
    assert granted != before
    combo.setCurrentIndex(0)
    assert dlg._table.item(0, 2).text() == "无申请"


def test_ineligible_existing_plugin_keeps_unauthorized(qtbot, monkeypatch):
    dlg, _ = _build(
        qtbot, monkeypatch, {"solo": [SetSkinCommand]},
        types=[SetSkinCommand], status={"set_skin": "gone"},
    )
    assert dlg._table.cellWidget(0, 1).currentData() is None
    assert dlg._table.item(0, 2).text() != "无申请"


def test_load_authorizations_skips_types_without_tag(qtbot, monkeypatch):
    dlg, _ = _build(
        qtbot, monkeypatch, {}, types=[MouseClickCommand, _NoTag],
    )
    assert dlg._table.rowCount() == 2
    assert dlg._table.item(0, 0) is not None
    assert dlg._table.item(1, 0) is None
    assert len(dlg._combos) == 1


def test_is_same_command_type_by_tag_and_identity_fallback(qtbot, monkeypatch):
    dlg, fake = _build(
        qtbot, monkeypatch, {}, types=[MouseClickCommand],
    )
    assert dlg._is_same_command_type(MouseClickCommand, _DupMouseClick)
    assert not dlg._is_same_command_type(MouseClickCommand, NewGameCommand)

    monkeypatch.setattr(fake, "_get_tag",
                        Mock(side_effect=ValueError("no tag")))
    assert dlg._is_same_command_type(_NoTag, _NoTag)
    assert not dlg._is_same_command_type(_NoTag, object)


def test_update_status_three_branches(qtbot, monkeypatch):
    dlg, _ = _build(qtbot, monkeypatch, {}, types=[MouseClickCommand])
    dlg._update_status(0, None, [])
    assert dlg._table.item(0, 2).text() == "无申请"
    dlg._update_status(0, "alpha", ["alpha"])
    assert "已授权" in dlg._table.item(0, 2).text()
    dlg._update_status(0, None, ["alpha"])
    assert "未授权" in dlg._table.item(0, 2).text()


def test_on_accept_authorizes_revokes_and_saves(qtbot, monkeypatch):
    controls = {"alpha": [MouseClickCommand, SetSkinCommand]}
    dlg, fake = _build(
        qtbot, monkeypatch, controls,
        types=[MouseClickCommand, SetSkinCommand],
        status={"set_skin": "alpha"},
    )
    accepted = []
    dlg.accepted.connect(lambda: accepted.append(True))

    dlg._combos[0].setCurrentIndex(dlg._combos[0].findData("alpha"))
    dlg._combos[1].setCurrentIndex(0)
    dlg._on_accept()

    assert accepted == [True]
    assert fake.calls == [
        ("authorize", MouseClickCommand, "alpha"),
        ("revoke", SetSkinCommand, None),
        ("save", None, None),
    ]


def test_duplicate_command_types_are_deduplicated_by_tag(qtbot, monkeypatch):
    dlg, _ = _build(
        qtbot, monkeypatch,
        {"alpha": [MouseClickCommand, _DupMouseClick, MouseClickCommand]},
        types=[MouseClickCommand],
    )
    combo = dlg._table.cellWidget(0, 1)
    assert combo.count() == 2
    assert combo.itemText(1) == "alpha"


def test_real_manager_instance_is_used_when_not_patched(qtbot, monkeypatch, tmp_path):
    from plugin_sdk.control_auth import ControlAuthorizationManager

    monkeypatch.setattr(mw, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(ControlAuthorizationManager, "_instance", None)
    monkeypatch.setattr(ControlAuthorizationManager, "_initialized", False,
                        raising=False)
    fake = ControlAuthorizationManager(tmp_path)
    monkeypatch.setattr(mw.ControlAuthorizationManager, "instance",
                        staticmethod(lambda: fake))
    dlg = ControlAuthorizationDialog({})
    qtbot.addWidget(dlg)
    assert dlg._auth_manager is fake
    assert dlg._table.rowCount() == len(COMMAND_TYPES)
    monkeypatch.setattr(ControlAuthorizationManager, "_instance", None)
