"""Built-in plugin catalogs stay isolated, complete, and loadable at runtime."""
from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QTranslator

from plugin_manager.translations import _PUBLIC_CONTEXTS
from utils.plugin_i18n import PluginText, translated

ROOT = Path(__file__).resolve().parents[2]
LOCALES = ("en_US", "de_DE", "ja_JP", "pl_PL")
PLUGINS = {
    "challenge_mode": "ChallengeMode",
    "SaoleiWebsite": "SaoleiWebsite",
    "skin_manager": "SkinManagerPlugin",
    "XianNiUpgrade": "XianNiUpgrade",
}


def catalog(plugin: str, locale: str) -> Path:
    return ROOT / "src" / "plugins" / plugin / "translations" / f"{locale}.ts"


@pytest.mark.parametrize("plugin", PLUGINS)
@pytest.mark.parametrize("locale", LOCALES)
def test_catalog_is_complete_and_uses_one_private_context(plugin, locale):
    tree = ET.parse(catalog(plugin, locale))
    contexts = {node.findtext("name") for node in tree.findall(".//context")}
    assert contexts == {PLUGINS[plugin]}
    assert PLUGINS[plugin] not in _PUBLIC_CONTEXTS
    for message in tree.findall(".//message"):
        translation = message.find("translation")
        assert translation is not None, message.findtext("source")
        assert translation.get("type") not in ("unfinished", "vanished", "obsolete")
        assert "".join(translation.itertext()).strip(), message.findtext("source")


def test_plugin_sources_do_not_use_shared_contexts():
    for plugin in PLUGINS:
        for source in (ROOT / "src" / "plugins" / plugin).rglob("*.py"):
            text = source.read_text(encoding="utf-8")
            assert 'translate("Form"' not in text, source
            assert 'translate("SkinManager"' not in text, source


def test_plugin_text_keeps_source_and_operations():
    text = PluginText("HistoryPlugin", "共%1行,%2页").replace("%1", "3").replace("%2", "1")
    assert text == "共3行,1页"
    assert translated(text) == "共3行,1页"
    assert text.source == "共%1行,%2页"


@pytest.mark.parametrize(("locale", "expected"), [
    ("en_US", "Level 1"),
    ("de_DE", "Level 1"),
    ("ja_JP", "ステージ 1"),
    ("pl_PL", "Poziom 1"),
])
def test_challenge_catalog_loads_in_qt(qapp, qtbot, locale, expected):
    from plugins.challenge_mode.widgets import ChallengeModeUI

    translator = QTranslator()
    assert translator.load(str(catalog("challenge_mode", locale).with_suffix(".qm")))
    assert QCoreApplication.installTranslator(translator)
    try:
        widget = ChallengeModeUI()
        qtbot.addWidget(widget)
        assert widget._level_label.text() == expected
    finally:
        QCoreApplication.removeTranslator(translator)


def test_open_plugin_views_refresh_on_language_change(qapp, qtbot):
    class Translator(QTranslator):
        def isEmpty(self):
            return False

        def translate(self, context, source, disambiguation=None, n=-1):
            return {
                ("SkinManagerPlugin", "皮肤管理"): "Skin manager",
                ("XianNiUpgrade", "修行日志"): "Cultivation log",
            }.get((context, source))

    from plugins.skin_manager.widgets import SkinManagerWidget
    from plugins.XianNiUpgrade.widgets import XianNiUpgradeUI

    skin = SkinManagerWidget()
    xianni = XianNiUpgradeUI()
    for widget in (skin, xianni):
        qtbot.addWidget(widget)
        widget.show()
    translator = Translator()
    assert QCoreApplication.installTranslator(translator)
    try:
        qtbot.waitUntil(lambda: skin.findChildren(type(skin._status))[0].text() == "Skin manager")
        qtbot.waitUntil(lambda: xianni._log_group.title() == "Cultivation log")
    finally:
        QCoreApplication.removeTranslator(translator)


def test_compiled_catalogs_are_current():
    from tests.plugin_manager.test_menu_layout import find_lrelease

    try:
        compiler = find_lrelease()
    except (StopIteration, FileNotFoundError):
        pytest.skip("pyside6-lrelease is not available")
    for plugin in PLUGINS:
        for locale in LOCALES:
            source = catalog(plugin, locale)
            qm = source.with_suffix(".qm")
            assert qm.is_file(), qm
            assert qm.stat().st_mtime >= source.stat().st_mtime, qm
            result = subprocess.run(
                [str(compiler), str(source), "-qm", str(qm), "-nounfinished"],
                capture_output=True, text=True, check=True)
            assert "0 unfinished" in result.stdout
