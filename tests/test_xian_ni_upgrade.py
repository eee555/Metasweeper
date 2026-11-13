from __future__ import annotations

from plugin_sdk import OtherInfoBase, TextConfig, BoolConfig
from plugins.XianNiUpgrade.config import (
    HEALTH_SERVICE,
    api_url_transport_error,
    is_rank_health_payload,
)
from plugins.XianNiUpgrade.plugin import XianNiUpgradePlugin
from plugins.XianNiUpgrade.widgets import _scale_xp_parts, _xp_is_capped

import pytest


def test_non_standard_modes_can_gain_base_xp():
    # mode=8 不在 _MODE_K 白名单内，按设计没有难度系数、不计经验。
    # 改用已支持的非标准模式 7（弱无猜）验证「非标准模式同样可获得基础经验」。
    plugin = XianNiUpgradePlugin.__new__(XianNiUpgradePlugin)

    xp = plugin._calc_xp_base(
        mode=7,
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


def test_xp_breakdown_parts_match_total():
    """未触顶时，四个分项原始值之和取整即为最终道行。"""
    plugin = XianNiUpgradePlugin.__new__(XianNiUpgradePlugin)
    parts: list[float] = []
    # 使用分布中常见的一组局面指标，避免极端值直接把经验顶到上限
    xp = plugin._calc_xp_base(
        mode=0,
        level=3,
        row=8,
        column=8,
        mine_num=10,
        rtime=30.0,
        bbbv=17,
        cell1=22,
        cell2=11,
        cell3=3,
        cell4=0,
        cell5=0,
        cell6=0,
        cell7=0,
        cell8=0,
        op=3,
        isl=3,
        ioe=0.95,
        nf=False,
        parts=parts,
    )

    assert len(parts) == 4
    assert all(v > 0 for v in parts)  # 基础 / 稀有 / 竞速 / 效率
    assert xp == int(sum(parts))
    assert xp < 99999  # 未触发上限，可检出系数/封顶口径回归


def test_xp_breakdown_scales_with_final_total():
    """公式若对分项整体乘系数，展示值仍应合计为最终道行，且不应误判封顶。"""
    raw_parts = [30000.0, 60000.0, 21000.0, 9000.0]  # 原始合计 120000
    total = 54000  # 例如 k=0.45 时的 int(k * sum(parts))

    scaled = _scale_xp_parts(raw_parts, total)
    assert sum(scaled) == pytest.approx(total)
    assert scaled == pytest.approx([13500.0, 27000.0, 9450.0, 4050.0])
    assert _xp_is_capped(total) is False


def test_xp_cap_boundary():
    assert _xp_is_capped(99998) is False
    assert _xp_is_capped(99999) is True
    assert sum(_scale_xp_parts([1.0, 2.0, 3.0, 4.0], 99999)) == pytest.approx(99999)
    assert _scale_xp_parts([0.0, 0.0, 0.0, 0.0], 0) == [0.0] * 4


def test_api_url_requires_https_except_loopback():
    assert api_url_transport_error("http://evil.example") is not None
    assert api_url_transport_error("https://leixiu-rank.pages.dev") is None
    assert api_url_transport_error("http://127.0.0.1:8788") is None
    assert api_url_transport_error("http://localhost:8788") is None
    assert api_url_transport_error("") is None


def test_health_payload_requires_service_field():
    assert not is_rank_health_payload({"ok": True})
    assert not is_rank_health_payload({"ok": True, "service": "other"})
    assert not is_rank_health_payload(
        {"ok": "true", "service": HEALTH_SERVICE})
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

        def exec(self):
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

        def exec(self):
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
