from types import SimpleNamespace

from PySide6.QtCore import Qt

from dialogs.CheckUpdateGui import CheckUpdateGui
from network.githubApi import GitHub, PingThread, SourceManager


def test_close_button_flag_is_preserved(qtbot, monkeypatch):
    monkeypatch.setattr(GitHub, "releases", lambda self: None)
    monkeypatch.setattr(PingThread, "start", lambda self: None)
    github = GitHub(
        SourceManager(
            {"Github": {"url": "https://example.com", "t": ""}},
            "Github",
        ),
        "3.3.4",
        r"(\d+\.\d+\.\d+)",
    )
    dialog = CheckUpdateGui(github, SimpleNamespace(mainWindow=None))
    qtbot.addWidget(dialog)

    assert dialog.windowFlags() & Qt.WindowType.WindowCloseButtonHint
    assert not dialog.windowFlags() & Qt.WindowType.WindowContextHelpButtonHint
