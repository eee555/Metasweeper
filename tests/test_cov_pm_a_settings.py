"""settings_manager.py 覆盖：defaults / load / save / setters，全部使用 tmp_path。"""
from __future__ import annotations

import json

import pytest

from plugin_manager.settings_manager import BasicSettings, SettingsManager


def test_basic_settings_defaults_and_to_dict():
    s = BasicSettings()
    assert s.to_dict() == {
        "file_log_level": "DEBUG",
        "viewer_log_level": "INFO",
        "viewer_auto_scroll": True,
        "viewer_show_source": False,
    }


def test_basic_settings_from_dict_empty_and_unknown_keys():
    assert BasicSettings.from_dict({}) == BasicSettings()
    assert BasicSettings.from_dict({"bogus": 1, "extra": "x"}) == BasicSettings()


def test_basic_settings_from_dict_partial():
    s = BasicSettings.from_dict({"file_log_level": "ERROR"})
    assert s.file_log_level == "ERROR"
    assert s.viewer_log_level == "INFO"
    assert s.viewer_auto_scroll is True
    assert s.viewer_show_source is False


def test_basic_settings_from_dict_full():
    data = {
        "file_log_level": "TRACE",
        "viewer_log_level": "CRITICAL",
        "viewer_auto_scroll": False,
        "viewer_show_source": True,
    }
    assert BasicSettings.from_dict(data).to_dict() == data


def test_settings_manager_init_creates_data_dir(tmp_path):
    target = tmp_path / "nested" / "data"
    mgr = SettingsManager(target)
    assert target.is_dir()
    assert mgr._settings_path() == target / SettingsManager.SETTINGS_FILENAME
    assert mgr.settings == BasicSettings()


def test_settings_manager_load_valid_json(tmp_path):
    data = {
        "file_log_level": "WARNING",
        "viewer_log_level": "ERROR",
        "viewer_auto_scroll": False,
        "viewer_show_source": True,
    }
    (tmp_path / SettingsManager.SETTINGS_FILENAME).write_text(
        json.dumps(data), encoding="utf-8",
    )
    mgr = SettingsManager(tmp_path)
    assert mgr.settings.to_dict() == data
    assert mgr.file_log_level == "WARNING"
    assert mgr.viewer_log_level == "ERROR"
    assert mgr.viewer_auto_scroll is False
    assert mgr.viewer_show_source is True


def test_settings_manager_load_partial_dict(tmp_path):
    (tmp_path / SettingsManager.SETTINGS_FILENAME).write_text(
        json.dumps({"viewer_log_level": "TRACE"}), encoding="utf-8",
    )
    mgr = SettingsManager(tmp_path)
    assert mgr.file_log_level == "DEBUG"
    assert mgr.viewer_log_level == "TRACE"


def test_settings_manager_load_corrupt_json(tmp_path):
    (tmp_path / SettingsManager.SETTINGS_FILENAME).write_text(
        "{not-json", encoding="utf-8",
    )
    mgr = SettingsManager(tmp_path)
    assert mgr.settings == BasicSettings()


def test_settings_manager_load_non_dict_json(tmp_path):
    (tmp_path / SettingsManager.SETTINGS_FILENAME).write_text(
        json.dumps(["a", "b"]), encoding="utf-8",
    )
    assert SettingsManager(tmp_path).settings == BasicSettings()


def test_settings_manager_load_type_error_is_ignored(tmp_path, monkeypatch):
    (tmp_path / SettingsManager.SETTINGS_FILENAME).write_text(
        json.dumps({"viewer_auto_scroll": 1}), encoding="utf-8",
    )
    # 字段存在且文件可读；显式让 from_dict 抛 TypeError 验证被吞掉。
    mgr = SettingsManager(tmp_path)
    assert mgr.settings == BasicSettings.from_dict({"viewer_auto_scroll": 1})
    monkeypatch.setattr(BasicSettings, "from_dict", classmethod(
        lambda cls, data: (_ for _ in ()).throw(TypeError("bad field")),
    ))
    assert SettingsManager(tmp_path).settings == BasicSettings()


def test_settings_manager_load_key_error_is_ignored(tmp_path, monkeypatch):
    (tmp_path / SettingsManager.SETTINGS_FILENAME).write_text(
        json.dumps({"file_log_level": "INFO"}), encoding="utf-8",
    )
    monkeypatch.setattr(BasicSettings, "from_dict", classmethod(
        lambda cls, data: (_ for _ in ()).throw(KeyError("missing")),
    ))
    assert SettingsManager(tmp_path).settings == BasicSettings()


def test_settings_manager_save_persists_and_reload(tmp_path):
    mgr = SettingsManager(tmp_path)
    mgr.set_file_log_level("CRITICAL")
    path = mgr._settings_path()
    assert json.loads(path.read_text(encoding="utf-8"))["file_log_level"] == "CRITICAL"
    assert SettingsManager(tmp_path).file_log_level == "CRITICAL"


def test_set_file_log_level_valid_and_invalid(tmp_path):
    mgr = SettingsManager(tmp_path)
    mgr.set_file_log_level("TRACE")
    assert mgr.file_log_level == "TRACE"
    mgr.set_file_log_level("NOT_A_LEVEL")
    assert mgr.file_log_level == "TRACE"
    assert json.loads(mgr._settings_path().read_text(encoding="utf-8"))[
        "file_log_level"
    ] == "TRACE"


def test_set_viewer_log_level_valid_and_invalid(tmp_path):
    mgr = SettingsManager(tmp_path)
    mgr.set_viewer_log_level("WARNING")
    assert mgr.viewer_log_level == "WARNING"
    mgr.set_viewer_log_level("bogus")
    assert mgr.viewer_log_level == "WARNING"
    assert SettingsManager(tmp_path).viewer_log_level == "WARNING"


def test_set_viewer_auto_scroll_persists(tmp_path):
    mgr = SettingsManager(tmp_path)
    mgr.set_viewer_auto_scroll(False)
    assert mgr.viewer_auto_scroll is False
    assert json.loads(mgr._settings_path().read_text(encoding="utf-8"))[
        "viewer_auto_scroll"
    ] is False
    assert SettingsManager(tmp_path).viewer_auto_scroll is False


def test_set_viewer_show_source_persists(tmp_path):
    mgr = SettingsManager(tmp_path)
    mgr.set_viewer_show_source(True)
    assert mgr.viewer_show_source is True
    assert json.loads(mgr._settings_path().read_text(encoding="utf-8"))[
        "viewer_show_source"
    ] is True
    assert SettingsManager(tmp_path).viewer_show_source is True


def test_all_setters_together_round_trip(tmp_path):
    mgr = SettingsManager(tmp_path)
    mgr.set_file_log_level("ERROR")
    mgr.set_viewer_log_level("INFO")
    mgr.set_viewer_auto_scroll(False)
    mgr.set_viewer_show_source(True)
    reloaded = SettingsManager(tmp_path)
    assert reloaded.settings == mgr.settings
    assert reloaded.file_log_level == "ERROR"
    assert reloaded.viewer_auto_scroll is False
    assert reloaded.viewer_show_source is True
