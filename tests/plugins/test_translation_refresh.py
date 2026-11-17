"""Language switches must refresh plugin views and preserve existing filters."""

import subprocess
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QTranslator

from plugins.clipboard_replay.widgets import ClipboardReplayWidget
from plugins.history.models import CompareSymbol, LogicSymbol
from plugins.llm_minesweeper_controller.widgets import McpControlWidget


class ExampleTranslator(QTranslator):
    def isEmpty(self):
        return False

    def translate(self, context, sourceText, disambiguation=None, n=-1):
        return {
            ("HistoryPlugin", "与"): "and",
            ("HistoryPlugin", "等于"): "equals",
            ("MinesweeperMcp", "监听端口"): "Port",
            ("MinesweeperMcp", "启动MCP"): "Start MCP",
            ("ClipboardReplay", "运行日志"): "Activity log",
            ("ClipboardReplay", "系统"): "System",
            ("ClipboardReplay", "监听中"): "Listening",
            ("ClipboardReplay", "已暂停"): "Paused",
        }.get((context, sourceText))


def test_language_switch_refreshes_widgets_and_preserves_filter_values(qapp, qtbot):
    clipboard = ClipboardReplayWidget()
    mcp = McpControlWidget()
    qtbot.addWidget(clipboard)
    qtbot.addWidget(mcp)
    clipboard.show()
    mcp.show()
    old_logic = LogicSymbol.display_names()[0]
    old_compare = CompareSymbol.display_names()[0]
    clipboard.handle_output({"kind": "state", "enabled": True, "message": "ready"})

    translator = ExampleTranslator()
    assert QCoreApplication.installTranslator(translator)
    try:
        qtbot.waitUntil(lambda: clipboard.status_label.text() == "Listening")
        qtbot.waitUntil(lambda: mcp.action_button.text() == "Start MCP")
        assert clipboard._log_label.text() == "Activity log"
        assert mcp._port_label.text() == "Port"
        assert LogicSymbol.display_names()[0] == "and"
        assert CompareSymbol.display_names()[0] == "equals"
        assert LogicSymbol.from_display_name(old_logic).to_sql == "and"
        assert CompareSymbol.from_display_name(old_compare).to_sql == "="
        clipboard.handle_output({"kind": "state", "enabled": False, "message": "stop"})
        assert clipboard.status_label.text() == "Paused"
        assert "[System] stop" in clipboard.log_output.toPlainText()
    finally:
        QCoreApplication.removeTranslator(translator)


@pytest.mark.parametrize(("locale", "expected"), [
    ("en_US", "Activity log"),
    ("de_DE", "Aktivitätsprotokoll"),
    ("ja_JP", "動作ログ"),
    ("pl_PL", "Dziennik aktywności"),
])
def test_clipboard_catalog_loads_in_qt(qapp, qtbot, tmp_path, locale, expected):
    root = Path(__file__).resolve().parents[2]
    catalog = root / "src" / "plugins" / "clipboard_replay" / "translations" / f"{locale}.ts"
    qm = tmp_path / f"{locale}.qm"
    from tests.plugin_manager.test_menu_layout import find_lrelease

    try:
        compiler = find_lrelease()
    except (StopIteration, FileNotFoundError):
        pytest.skip("pyside6-lrelease is not available")
    subprocess.run([str(compiler), str(catalog), "-qm", str(qm)], check=True)
    translator = QTranslator()
    assert translator.load(str(qm))
    assert QCoreApplication.installTranslator(translator)
    try:
        widget = ClipboardReplayWidget()
        qtbot.addWidget(widget)
        assert widget._log_label.text() == expected
    finally:
        QCoreApplication.removeTranslator(translator)
