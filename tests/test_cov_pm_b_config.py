"""Coverage tests for plugin_manager.config_manager (PluginConfigManager)."""
from __future__ import annotations

import json
from pathlib import Path

from plugin_manager.config_manager import PluginConfigManager
from plugin_sdk.config_types import (
    BoolConfig, ChoiceConfig, IntConfig, OtherInfoBase, TextConfig,
)


class SampleConfig(OtherInfoBase):
    retries = IntConfig(3, "重试次数", min_value=0, max_value=10)
    enabled = BoolConfig(True, "启用")
    mode = ChoiceConfig("a", "模式", choices=[("a", "A"), ("b", "B")])
    token = TextConfig("secret", "令牌", password=True)
    note = TextConfig("default", "备注", visible=False, description="内部备注")


def _manager(base_dir: Path) -> PluginConfigManager:
    return PluginConfigManager(base_dir)


def test_init_creates_base_dir_and_exposes_config_path(tmp_path):
    base = tmp_path / "nested" / "plugin_data"
    manager = _manager(base)
    assert base.is_dir()
    assert manager.CONFIG_FILENAME == "config.json"
    path = manager.config_path("alpha")
    assert path == base / "alpha" / "config.json"
    assert manager._config_path("alpha") == path
    assert manager.exists("alpha") is False


def test_load_missing_file_returns_same_config_with_defaults(tmp_path):
    manager = _manager(tmp_path)
    config = SampleConfig()
    loaded = manager.load("absent", config)
    assert loaded is config
    assert loaded.retries == 3
    assert loaded.enabled is True
    assert loaded.mode == "a"
    assert loaded.token == "secret"
    assert loaded.note == "default"


def test_save_and_load_round_trip_including_hidden_field(tmp_path):
    manager = _manager(tmp_path)
    config = SampleConfig()
    config.retries = 7
    config.enabled = False
    config.mode = "b"
    config.token = "token-b"
    config.note = "hidden-value"

    manager.save("alpha", config)
    path = manager.config_path("alpha")
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "retries": 7,
        "enabled": False,
        "mode": "b",
        "token": "token-b",
        "note": "hidden-value",
    }
    assert path.read_text(encoding="utf-8").startswith("{\n")

    other = SampleConfig()
    assert manager.load("alpha", other) is other
    assert other.retries == 7
    assert other.enabled is False
    assert other.mode == "b"
    assert other.token == "token-b"
    assert other.note == "hidden-value"


def test_load_non_dict_json_keeps_defaults(tmp_path):
    manager = _manager(tmp_path)
    path = manager.config_path("alpha")
    path.parent.mkdir(parents=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")
    config = SampleConfig()
    assert manager.load("alpha", config) is config
    assert config.retries == 3
    assert config.enabled is True


def test_load_corrupt_json_keeps_defaults(tmp_path):
    manager = _manager(tmp_path)
    path = manager.config_path("alpha")
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    config = SampleConfig()
    assert manager.load("alpha", config) is config
    assert config.to_dict() == SampleConfig().to_dict()


def test_load_invalid_values_fall_back_to_defaults(tmp_path):
    manager = _manager(tmp_path)
    path = manager.config_path("alpha")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "retries": "not-an-int",
        "enabled": None,
        "mode": 123,
        "token": ["a", "b"],
        "note": None,
        "unknown_key": "ignored",
    }), encoding="utf-8")
    config = SampleConfig()
    assert manager.load("alpha", config) is config
    assert config.retries == 3
    assert config.enabled is False
    assert config.mode == "123"
    assert config.token == "['a', 'b']"
    assert config.note == "default"


def test_load_from_dict_type_error_is_caught(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    path = manager.config_path("alpha")
    path.parent.mkdir(parents=True)
    path.write_text('{"mode": 1}', encoding="utf-8")
    config = SampleConfig()

    def boom(_data):
        raise TypeError("bad shape")

    monkeypatch.setattr(config, "from_dict", boom)
    assert manager.load("alpha", config) is config
    assert config.to_dict() == SampleConfig().to_dict()


def test_delete_existing_config_removes_empty_plugin_directory(tmp_path):
    manager = _manager(tmp_path)
    manager.save("alpha", SampleConfig())
    path = manager.config_path("alpha")
    assert manager.exists("alpha") is True

    manager.delete("alpha")
    assert manager.exists("alpha") is False
    assert path.parent.exists() is False


def test_delete_keeps_nonempty_plugin_directory(tmp_path):
    manager = _manager(tmp_path)
    manager.save("alpha", SampleConfig())
    extra = manager.config_path("alpha").parent / "extra.bin"
    extra.write_bytes(b"kept")

    manager.delete("alpha")
    assert manager.exists("alpha") is False
    assert extra.is_file()
    assert extra.parent.is_dir()


def test_delete_missing_config_is_noop(tmp_path):
    manager = _manager(tmp_path)
    manager.delete("alpha")
    assert manager.exists("alpha") is False
    assert tmp_path.is_dir()
