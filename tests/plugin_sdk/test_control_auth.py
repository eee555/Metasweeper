from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib_zmq_plugins.shared.base import BaseCommand
from plugin_sdk.control_auth import ControlAuthorizationManager


class FirstCommand(BaseCommand, tag="sdk-test-first"):
    pass


class SecondCommand(BaseCommand, tag="sdk-test-second"):
    pass


class UntaggedCommand:
    pass


@pytest.fixture
def manager(monkeypatch, tmp_path):
    monkeypatch.setattr(ControlAuthorizationManager, "_instance", None)
    instance = ControlAuthorizationManager(tmp_path)
    yield instance
    monkeypatch.setattr(ControlAuthorizationManager, "_instance", None)


def test_authorize_reassign_revoke_signals_and_persistence(manager, tmp_path):
    events = []
    manager.authorization_changed.connect(lambda *args: events.append(args))
    assert manager.is_authorized(FirstCommand, "alpha") is False
    assert manager.has_control_auth(FirstCommand) is False
    assert manager.get_authorized_plugin(FirstCommand) is None

    manager.authorize(FirstCommand, "alpha")
    manager.authorize(FirstCommand, "alpha")
    manager.authorize(FirstCommand, "beta")
    assert manager.is_authorized(FirstCommand, "beta")
    assert manager.has_control_auth(FirstCommand)
    assert manager.get_authorized_plugin(FirstCommand) == "beta"
    assert events == [
        ("sdk-test-first", "alpha", True),
        ("sdk-test-first", "alpha", True),
        ("sdk-test-first", "alpha", False),
        ("sdk-test-first", "beta", True),
    ]

    manager.save()
    path = tmp_path / "control_authorization.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {"sdk-test-first": "beta"}
    manager.save()
    assert manager.revoke(FirstCommand) == "beta"
    assert manager.revoke(FirstCommand) is None
    manager.save()
    assert json.loads(path.read_text(encoding="utf-8")) == {}


def test_load_filters_invalid_data_and_recovers_from_corrupt_json(manager, tmp_path):
    path = tmp_path / "control_authorization.json"
    path.write_text(json.dumps({"valid": "plugin", "not-a-plugin": 3, 4: "x"}), encoding="utf-8")
    manager.load()
    assert manager._authorizations == {"valid": "plugin", "4": "x"}
    path.write_text("{", encoding="utf-8")
    manager._authorizations = {"stale": "value"}
    manager.load()
    assert manager._authorizations == {}


def test_validation_status_batch_operations_and_clear(manager):
    manager.authorize(FirstCommand, "loaded")
    manager.authorize(SecondCommand, "missing")
    assert manager.validate_authorizations({"loaded"}) == [("sdk-test-second", "missing")]
    assert manager.get_authorized_plugin(FirstCommand) == "loaded"
    assert manager.get_authorized_plugin(SecondCommand) is None

    manager.set_authorizations({FirstCommand: None, SecondCommand: "next"})
    assert manager.get_authorized_plugin(FirstCommand) is None
    assert manager.get_authorized_plugin(SecondCommand) == "next"
    status = manager.get_authorization_status()
    assert isinstance(status, dict) and status
    assert manager.get_all_control_types()

    events = []
    manager.authorization_changed.connect(lambda *args: events.append(args))
    manager.clear_all()
    assert manager._authorizations == {}
    assert events == [("sdk-test-second", "next", False)]


def test_invalid_command_type_and_failed_save(manager, monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="无法获取命令类型的 tag"):
        manager.authorize(UntaggedCommand, "plugin")
    with pytest.raises(ValueError, match="无法获取命令类型的 tag"):
        manager.is_authorized(UntaggedCommand, "plugin")

    manager.authorize(FirstCommand, "plugin")
    original_write_text = Path.write_text

    def fail_target_write(path, *args, **kwargs):
        if path == manager._file:
            raise OSError("read only")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_target_write)
    manager.save()
    assert manager._dirty is True
