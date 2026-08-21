from __future__ import annotations

from plugin_sdk import OtherInfoBase, TextConfig, BoolConfig
from plugins.XianNiUpgrade.config import (
    HEALTH_SERVICE,
    api_url_transport_error,
    is_rank_health_payload,
)
from plugins.XianNiUpgrade.plugin import XianNiUpgradePlugin


def test_non_standard_modes_can_gain_base_xp():
    plugin = XianNiUpgradePlugin.__new__(XianNiUpgradePlugin)

    xp = plugin._calc_xp_base(
        mode=8,
        level=3,
        row=8,
        column=8,
        mine_num=10,
        rtime=30.0,
        bbbv=20,
        cell1=0,
        cell2=0,
        cell3=0,
        cell4=0,
        cell5=0,
        cell6=0,
        cell7=0,
        cell8=0,
        op=0,
        isl=0,
        ioe=0.95,
        nf=True,
    )

    assert xp > 0


def test_api_url_requires_https_except_loopback():
    assert api_url_transport_error("http://evil.example") is not None
    assert api_url_transport_error("https://leixiu-rank.pages.dev") is None
    assert api_url_transport_error("http://127.0.0.1:8788") is None
    assert api_url_transport_error("http://localhost:8788") is None
    assert api_url_transport_error("") is None


def test_health_payload_requires_service_field():
    assert not is_rank_health_payload({"ok": True})
    assert not is_rank_health_payload({"ok": True, "service": "other"})
    assert not is_rank_health_payload({"ok": "true", "service": HEALTH_SERVICE})
    assert is_rank_health_payload({"ok": True, "service": HEALTH_SERVICE})


def test_password_fields_redacted_in_logs_not_storage():
    class Sample(OtherInfoBase):
        name = TextConfig(default="bob", label="n")
        secret = TextConfig(default="", label="s", password=True)
        flag = BoolConfig(default=True, label="f")

    cfg = Sample()
    cfg.secret = "super-secret-token"
    dumped = cfg.to_dict()
    assert dumped["secret"] == "super-secret-token"
    logged = cfg.to_log_dict()
    assert logged["secret"] == "***"
    assert logged["name"] == "bob"
    assert logged["flag"] is True
    assert "super-secret-token" not in repr(cfg)
    cfg.secret = ""
    assert cfg.to_log_dict()["secret"] == ""


def test_maybe_show_rules_dialog_skips_when_seen():
    plugin = XianNiUpgradePlugin.__new__(XianNiUpgradePlugin)

    class FakeConfig:
        rules_dialog_seen = True

    plugin._other_info = FakeConfig()
    plugin._guide_dialog_open = False
    called = {"dialog": False, "save": False}

    class FakeDialog:
        def __init__(self, parent=None):
            called["dialog"] = True

        def exec_(self):
            return 1

    plugin.save_config = lambda: called.__setitem__("save", True)
    plugin.run_on_gui = lambda func, *args, **kwargs: func(*args, **kwargs)
    import plugins.XianNiUpgrade.plugin as plugin_mod

    old_dialog = plugin_mod.RulesDialog
    plugin_mod.RulesDialog = FakeDialog
    try:
        plugin._maybe_show_rules_dialog()
    finally:
        plugin_mod.RulesDialog = old_dialog

    assert not called["dialog"]
    assert not called["save"]


def test_maybe_show_rules_dialog_shows_once_and_marks_seen():
    plugin = XianNiUpgradePlugin.__new__(XianNiUpgradePlugin)

    class FakeConfig:
        rules_dialog_seen = False

    plugin._other_info = FakeConfig()
    plugin._guide_dialog_open = False
    plugin._ui = type("UI", (), {"isVisible": staticmethod(lambda: True)})()
    called = {"dialog": 0, "save": False}

    class FakeDialog:
        def __init__(self, parent=None):
            called["dialog"] += 1

        def exec_(self):
            return 1

    plugin.save_config = lambda: called.__setitem__("save", True)
    plugin.run_on_gui = lambda func, *args, **kwargs: func(*args, **kwargs)
    import plugins.XianNiUpgrade.plugin as plugin_mod

    old_dialog = plugin_mod.RulesDialog
    plugin_mod.RulesDialog = FakeDialog
    try:
        plugin._maybe_show_rules_dialog()
        plugin._maybe_show_rules_dialog()
    finally:
        plugin_mod.RulesDialog = old_dialog

    assert called["dialog"] == 1
    assert called["save"] is True
    assert plugin.other_info.rules_dialog_seen is True


def test_resolve_rank_display_name_uses_service():
    plugin = XianNiUpgradePlugin.__new__(XianNiUpgradePlugin)

    class FakeService:
        def get_rank_display_name(self, identifier: str) -> str:
            assert identifier == "MyIdent"
            return "网内昵称"

    plugin._saolei_service = FakeService()
    assert plugin._resolve_rank_display_name("MyIdent") == "网内昵称"


def test_resolve_rank_display_name_fallback_without_service():
    plugin = XianNiUpgradePlugin.__new__(XianNiUpgradePlugin)
    plugin.logger = type("L", (), {"warning": lambda *a, **k: None})()
    plugin._saolei_service = None
    plugin.wait_for_service = lambda *a, **k: None
    assert plugin._resolve_rank_display_name("FallbackID") == "FallbackID"
