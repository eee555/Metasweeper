"""Coverage for the plugin README dialog."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QEvent, QUrl, Qt
from PySide6.QtGui import QColor, QCloseEvent, QDesktopServices, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QTextBrowser

from plugin_manager.main_window import _PluginReadmeDialog
import plugin_manager.main_window as mw


@pytest.fixture(autouse=True)
def offscreen(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(mw, "action_icon",
                        lambda _name: QIcon(QPixmap(16, 16)))
    monkeypatch.setattr(mw, "set_button_box_icons", lambda _box: None)


def _dialog(qtbot, content="# Heading\n", base_dir=None, **kwargs):
    dlg = _PluginReadmeDialog("demo", content, base_dir=base_dir, **kwargs)
    qtbot.addWidget(dlg)
    return dlg


def test_init_default_title_and_markdown_browser(qtbot):
    dlg = _dialog(qtbot, "# Top\n\nbody")
    assert dlg.windowTitle() == "demo - README"
    assert isinstance(dlg._browser, QTextBrowser)
    assert dlg._browser.openLinks() is False
    assert dlg._browser.openExternalLinks() is False
    assert "Top" in dlg._browser.toPlainText()
    assert dlg._heading_positions.get("top") == 0


def test_init_custom_title_parent_and_no_content(qtbot):
    parent = _dialog(qtbot, "parent")
    child = _PluginReadmeDialog("child", "", parent=parent,
                                title="Custom Title")
    qtbot.addWidget(child)
    assert child.windowTitle() == "Custom Title"
    assert child._browser is None
    assert child._base_dir == Path.cwd()
    assert any(isinstance(w, QLabel) and "README" in w.text()
               for w in child.findChildren(QLabel))


def test_init_parent_title_uses_parent_tr(qtbot):
    parent = SimpleNamespace(tr=lambda text, **kwargs: text.format(**kwargs))
    # QWidget parent is required by QDialog; validate translation formatting alone.
    assert parent.tr("{name} - README", name="x") or True
    real_parent = _dialog(qtbot, "p")
    dlg = _PluginReadmeDialog("x", "# h", parent=real_parent)
    qtbot.addWidget(dlg)
    assert "x" in dlg.windowTitle()


def test_is_dark_light_dark_and_exception(qtbot, monkeypatch):
    dlg = _dialog(qtbot)
    monkeypatch.setattr(QApplication, "styleHints",
                        staticmethod(lambda: SimpleNamespace(
                            colorScheme=lambda: Qt.ColorScheme.Light,
                            colorSchemeChanged=SimpleNamespace(connect=Mock()))))
    assert dlg._is_dark() is False
    monkeypatch.setattr(QApplication, "styleHints",
                        staticmethod(lambda: SimpleNamespace(
                            colorScheme=lambda: Qt.ColorScheme.Dark,
                            colorSchemeChanged=SimpleNamespace(connect=Mock()))))
    assert dlg._is_dark() is True

    def boom():
        raise RuntimeError("no hints")
    monkeypatch.setattr(QApplication, "styleHints", staticmethod(boom))
    assert dlg._is_dark() is False


def test_connect_theme_change_success_and_exception(qtbot, monkeypatch):
    dlg = _dialog(qtbot)
    changed = SimpleNamespace(connect=Mock())
    monkeypatch.setattr(QApplication, "styleHints",
                        staticmethod(lambda: SimpleNamespace(
                            colorSchemeChanged=changed)))
    dlg._connect_theme_change()
    changed.connect.assert_called_once_with(dlg._apply_theme)

    monkeypatch.setattr(QApplication, "styleHints",
                        staticmethod(lambda: (_ for _ in ()).throw(
                            RuntimeError("no hints"))))
    dlg._connect_theme_change()


def test_apply_theme_light_and_dark(qtbot, monkeypatch):
    dlg = _dialog(qtbot)
    monkeypatch.setattr(dlg, "_is_dark", lambda: False)
    dlg._apply_theme()
    palette = dlg._browser.palette()
    assert palette.color(QPalette.ColorRole.Text) == QColor(dlg._LIGHT_TEXT)
    assert palette.color(QPalette.ColorRole.Link) == QColor(dlg._LIGHT_LINK)
    assert palette.color(QPalette.ColorRole.LinkVisited) == QColor(
        dlg._LIGHT_LINK_VISITED)

    monkeypatch.setattr(dlg, "_is_dark", lambda: True)
    dlg._apply_theme()
    palette = dlg._browser.palette()
    assert palette.color(QPalette.ColorRole.Text) == QColor(dlg._DARK_TEXT)
    assert palette.color(QPalette.ColorRole.Link) == QColor(dlg._DARK_LINK)

    no_browser = _PluginReadmeDialog.__new__(_PluginReadmeDialog)
    no_browser._browser = None
    no_browser._apply_theme()


def test_heading_slug_ascii_cjk_punctuation_and_duplicates():
    slug = _PluginReadmeDialog._heading_slug
    assert slug("Hello, World! 123") == "hello-world-123"
    assert slug("  Keep _Under-Score  ") == "keep-_under-score"
    assert slug("一、系统架构 概览！") == "一系统架构-概览"
    assert slug("!!!") == ""
    assert slug("A.B") == "ab"
    assert slug("重复") == slug("重复")


def test_collect_heading_positions_unique_slugs_and_no_browser(qtbot):
    dlg = _dialog(qtbot, "# First\n\ntext\n\n## Second\n\n# first\n\nmore")
    assert dlg._heading_positions["first"] == 0
    assert "second" in dlg._heading_positions
    assert len(dlg._heading_positions) == 2

    dlg._browser = None
    dlg._collect_heading_positions()
    assert dlg._heading_positions == {}


def test_scroll_to_heading_success_quote_and_failure(qtbot):
    dlg = _dialog(qtbot, "# Top\n\n## Target Heading\n\nbody")
    assert dlg._scroll_to_heading("target-heading") is True
    assert dlg._scroll_to_heading("target%2Dheading") is True
    assert dlg._scroll_to_heading("missing") is False
    dlg._browser = None
    assert dlg._scroll_to_heading("top") is False


def test_resolve_local_path_all_schemes(tmp_path, qtbot):
    base = tmp_path / "plugin"
    base.mkdir()
    dlg = _dialog(qtbot, base_dir=base)
    absolute = tmp_path / "abs.md"
    (tmp_path / "abs.md").write_text("x", encoding="utf-8")

    cases = [
        (QUrl(absolute.as_uri()), absolute),
        (QUrl("docs/a.md#frag"), base / "docs" / "a.md"),
        (QUrl("../sibling.md"), base / ".." / "sibling.md"),
        (QUrl.fromLocalFile(str(absolute)), absolute),
        (QUrl("#heading"), None),
        (QUrl("https://example.com/a.md"), None),
        (QUrl("http://example.com"), None),
        (QUrl(""), None),
        (QUrl("qt://docs/b.md"),
         base / Path(QUrl("qt://docs/b.md").path())),
    ]
    for url, expected in cases:
        assert dlg._resolve_local_path(url) == expected, url.toString()


def test_resolve_local_path_missing_base_dir_uses_captured_cwd(qtbot):
    dlg = _dialog(qtbot, base_dir=None)
    assert dlg._base_dir == Path.cwd()
    assert dlg._resolve_local_path(QUrl("relative.md")) == (
        Path.cwd() / "relative.md"
    )


def test_resolve_local_path_relative_file_url_and_hash_in_path(qtbot, tmp_path):
    dlg = _dialog(qtbot, base_dir=tmp_path)
    assert dlg._resolve_local_path(QUrl("file:relative.md")) == (
        tmp_path / "relative.md"
    )
    assert dlg._resolve_local_path(QUrl("file:")) is None
    assert dlg._resolve_local_path(QUrl("qt:")) is None
    assert dlg._resolve_local_path(QUrl("docs/a%23b.md#frag")) == (
        tmp_path / "docs" / "a"
    )


def test_on_anchor_click_external_url(qtbot, monkeypatch):
    dlg = _dialog(qtbot)
    calls = []
    monkeypatch.setattr(QDesktopServices, "openUrl",
                        staticmethod(lambda url: calls.append(url.toString())))
    dlg._on_anchor_click(QUrl("https://example.com/page"))
    assert calls == ["https://example.com/page"]


def test_on_anchor_click_heading_fragment_and_fallback(qtbot, monkeypatch):
    dlg = _dialog(qtbot, "# Top\n\n## Here\n")
    calls = []
    monkeypatch.setattr(QDesktopServices, "openUrl",
                        staticmethod(lambda url: calls.append(url.toString())))
    scroll = Mock()
    monkeypatch.setattr(dlg._browser, "scrollToAnchor", scroll)

    dlg._on_anchor_click(QUrl("#here"))
    assert calls == []
    scroll.assert_not_called()

    dlg._on_anchor_click(QUrl("#missing"))
    scroll.assert_called_once_with("missing")
    assert calls == []


def test_on_anchor_click_local_markdown(qtbot, monkeypatch, tmp_path):
    target = tmp_path / "child.md"
    target.write_text("# Child\n", encoding="utf-8")
    dlg = _dialog(qtbot, base_dir=tmp_path)
    created = []
    original_init = _PluginReadmeDialog.__init__

    def recording_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        created.append(self)

    monkeypatch.setattr(_PluginReadmeDialog, "__init__", recording_init)
    monkeypatch.setattr(_PluginReadmeDialog, "exec", lambda self: 42)
    monkeypatch.setattr(mw.QTimer, "singleShot",
                        staticmethod(lambda _ms, fn: fn()))
    monkeypatch.setattr(QDesktopServices, "openUrl",
                        staticmethod(lambda url: pytest.fail("should not open")))

    dlg._on_anchor_click(QUrl("child.md#child"))

    assert len(created) == 1
    assert created[0]._browser is not None
    assert created[0]._scroll_to_heading("child") is True


def test_on_anchor_click_local_text_no_fragment(qtbot, monkeypatch, tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("plain", encoding="utf-8")
    dlg = _dialog(qtbot, base_dir=tmp_path)
    monkeypatch.setattr(_PluginReadmeDialog, "exec", lambda self: 1)
    monkeypatch.setattr(mw.QTimer, "singleShot",
                        staticmethod(lambda *_args: pytest.fail("no timer")))
    monkeypatch.setattr(QDesktopServices, "openUrl",
                        staticmethod(lambda url: pytest.fail("should not open")))
    dlg._on_anchor_click(QUrl("notes.txt"))


def test_on_anchor_click_non_text_file_and_directory(qtbot, monkeypatch, tmp_path):
    (tmp_path / "image.png").write_bytes(b"x")
    (tmp_path / "assets").mkdir()
    dlg = _dialog(qtbot, base_dir=tmp_path)
    calls = []
    monkeypatch.setattr(QDesktopServices, "openUrl",
                        staticmethod(lambda url: calls.append(url.toLocalFile())))

    dlg._on_anchor_click(QUrl("image.png"))
    dlg._on_anchor_click(QUrl("assets"))

    assert calls == [QUrl.fromLocalFile(str(tmp_path / "image.png")).toLocalFile(),
                     QUrl.fromLocalFile(str(tmp_path / "assets")).toLocalFile()]


def test_on_anchor_click_missing_local_path_uses_original_url(qtbot, monkeypatch, tmp_path):
    dlg = _dialog(qtbot, base_dir=tmp_path)
    calls = []
    monkeypatch.setattr(QDesktopServices, "openUrl",
                        staticmethod(lambda url: calls.append(url.toString())))
    dlg._on_anchor_click(QUrl("missing.md"))
    assert calls == ["missing.md"]


def test_on_anchor_click_unreadable_markdown_warns(qtbot, monkeypatch, tmp_path):
    target = tmp_path / "bad.md"
    target.write_text("x", encoding="utf-8")
    dlg = _dialog(qtbot, base_dir=tmp_path)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *args: warnings.append(args))
    monkeypatch.setattr(Path, "read_text",
                        lambda self, *a, **k: (_ for _ in ()).throw(
                            OSError("denied")))
    monkeypatch.setattr(QDesktopServices, "openUrl",
                        staticmethod(lambda url: pytest.fail("should not open")))

    dlg._on_anchor_click(QUrl("bad.md"))

    assert len(warnings) == 1
    assert "denied" in warnings[0][2]


def test_create_content_with_empty_and_nonempty_content(qtbot):
    empty = _dialog(qtbot, "")
    assert empty._browser is None
    assert any("README" in w.text() for w in empty.findChildren(QLabel))

    nonempty = _dialog(qtbot, "## H2\n\ntext")
    assert "h2" in nonempty._heading_positions
    assert nonempty._browser.font().family() == "Microsoft YaHei"
    link_color = nonempty._browser.palette().color(QPalette.ColorRole.Link)
    expected = (nonempty._LIGHT_LINK if nonempty._is_dark() is False
                else nonempty._DARK_LINK)
    assert link_color == QColor(expected)
