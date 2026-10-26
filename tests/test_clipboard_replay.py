from __future__ import annotations

import sys
from pathlib import Path
from tempfile import gettempdir
from unittest.mock import Mock
from urllib.parse import parse_qs

import pytest
from PySide6.QtCore import QByteArray, QMimeData, QObject, QThread, Signal, Slot
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QPlainTextEdit, QTabWidget

from plugin_sdk import BasePlugin, BoolConfig, OtherInfoBase
from plugins.clipboard_replay import plugin as plugin_module
from plugins.clipboard_replay.config import ClipboardReplayConfig, add_handler_fields
from plugins.clipboard_replay.handlers.base import ClipboardHandler
from plugins.clipboard_replay.handlers import download as download_module
from plugins.clipboard_replay.handlers.openms.handler import find_video_id
from plugins.clipboard_replay.handlers.saolei.handler import find_video_id as find_saolei_video_id
from plugins.clipboard_replay.handlers.classic95.handler import find_replay_code
from plugins.clipboard_replay.plugin import ClipboardReplayPlugin
from plugins.clipboard_replay.widgets import ClipboardReplayWidget
from plugins.clipboard_replay.replay import (
    MAX_DOWNLOAD_BYTES, playback_command, replay_suffix,
)


@pytest.mark.parametrize(("text", "expected"), [
    ("https://openms.top/api/video/download/1", "1"),
    ("分享：https://openms.top/api/video/download/12。", "12"),
    ("(https://openms.top/api/video/download/3)", "3"),
    ("http://openms.top/api/video/download/001/?token=anything#video", "1"),
    ("HTTPS://OPENMS.TOP/api/video/download/42", "42"),
    ("https://openms.top.evil.test/api/video/download/1", None),
    ("https://openms.top@evil.test/api/video/download/1", None),
    ("https://evil.test/api/video/download/1", None),
    ("https://openms.top/api/video/download/1evil", None),
    ("https://openms.top/api/video/download/1/extra", None),
    ("https://openms.top/api/video/download/0", None),
    ("https://openms.top/api/video/download/-1", None),
    ("not a replay", None),
])
def test_find_video_id(text, expected):
    assert find_video_id(text) == expected


@pytest.mark.parametrize(("text", "expected"), [
    ("https://www.saolei.wang/video/download/345964", "345964"),
    ("分享：https://www.saolei.wang/video/download/345964。", "345964"),
    ("https://www.saolei.wang/video/347628", "347628"),
    ("https://www.saolei.wang/video/000347628/?from=share", "347628"),
    ("https://www.saolei.wang/video/download/347628", "347628"),
    ("http://www.saolei.wang/video/download/000345964/?download=1", "345964"),
    ("https://new.saolei.wang/video/download/345964", None),
    ("https://new.saolei.wang.evil.test/video/download/345964", None),
    ("https://new.saolei.wang@evil.test/video/download/345964", None),
    ("https://new.saolei.wang/video/download/345964evil", None),
    ("https://openms.top/api/video/download/345964", None),
    ("https://www.saolei.wang/video/download/0", None),
    ("https://www.saolei.wang/video/0", None),
    ("https://www.saolei.wang/video/347628/extra", None),
])
def test_find_saolei_video_id(text, expected):
    assert find_saolei_video_id(text) == expected


@pytest.mark.parametrize(("text", "expected"), [
    ("95经典扫雷|79228415-263-107", "79228415-263-107"),
    ("95经典扫雷|79228415-263-81", "79228415-263-81"),
    (" 95经典扫雷 | 79228415 - 263 - 107\n", "79228415-263-107"),
    ("95经典扫雷|0079228415-0263-00107", "79228415-263-107"),
    ("95经典扫雷|" + "-".join(["9" * 20] * 3), "-".join(["9" * 20] * 3)),
    ("95经典扫雷|263-117", None),
    ("95经典扫雷|263-81", None),
    ("79228415-263-107", None),
    ("其他扫雷|79228415-263-107", None),
    ("95精简扫雷|79228415-263-107", None),
    ("95经典扫雷|0-263-107", None),
    ("95经典扫雷|79228415-0-107", None),
    ("95经典扫雷|79228415-263-0", None),
    ("95经典扫雷|-79228415-263-107", None),
    ("95经典扫雷|79228415--263-107", None),
    ("95经典扫雷|79228415-263--107", None),
    ("95经典扫雷|79228415-263-107extra", None),
    ("95经典扫雷|79228415-263-107&uid=81", None),
    ("95经典扫雷|79228415-263-107?id=81", None),
    ("95经典扫雷|79228415-263-107-81", None),
    ("95经典扫雷|-263-107", None),
    ("95经典扫雷|79228415--107", None),
    ("95经典扫雷|79228415-263-", None),
    ("95经典扫雷|xxxx-263-107", None),
    ("95经典扫雷|" + "9" * 21 + "-263-107", None),
    ("95经典扫雷|79228415-" + "9" * 21 + "-107", None),
    ("95经典扫雷|79228415-263-" + "9" * 21, None),
    ("95经典扫雷|79228415-263-107" + " " * 256, None),
])
def test_find_classic95_replay_code(text, expected):
    assert find_replay_code(text) == expected


@pytest.mark.parametrize(("disposition", "expected"), [
    ('attachment; filename="Exp_FL_62.89_MY_Tian.avf"', ".avf"),
    ("attachment; filename*=UTF-8''replay%20one.EVF", ".evf"),
    ('attachment; filename="../../replay.rmv"', ".rmv"),
    ('attachment; filename="replay.mvf"', ".mvf"),
    ('attachment; filename="replay.evfs"', ".evfs"),
])
def test_replay_suffix(disposition, expected):
    assert replay_suffix(disposition, "application/octet-stream") == expected


@pytest.mark.parametrize(("disposition", "content_type"), [
    ("", "application/octet-stream"),
    ('attachment; filename="replay.exe"', "application/octet-stream"),
    ('attachment; filename="replay.avf"', "text/html"),
    ('attachment; filename="replay.avf"', "application/json; charset=utf-8"),
])
def test_reject_non_replay(disposition, content_type):
    with pytest.raises(ValueError):
        replay_suffix(disposition, content_type)


def test_playback_command(tmp_path):
    replay = tmp_path / "video.avf"
    with pytest.raises(FileNotFoundError):
        playback_command(replay, tmp_path)
    executable = tmp_path / "metasweeper.exe"
    executable.touch()
    assert playback_command(replay, tmp_path) == [str(executable), str(replay)]
    main_py = tmp_path / "src" / "main.py"
    main_py.parent.mkdir()
    main_py.touch()
    assert playback_command(replay, tmp_path) == [
        sys.executable, str(main_py), str(replay)]


class FakeClipboard(QObject):
    dataChanged = Signal()

    def __init__(self):
        super().__init__()
        self._mime = QMimeData()

    def mimeData(self):
        return self._mime

    def set_text(self, text):
        self._mime.setText(text)
        self.dataChanged.emit()


class FakeReply(QObject):
    readyRead = Signal()
    downloadProgress = Signal(int, int)
    finished = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.payload = b"replay data"
        self.headers = {
            "Content-Disposition": b'attachment; filename="replay.avf"',
            "Content-Type": b"application/octet-stream",
        }
        self.failure = QNetworkReply.NetworkError.NoError
        self.status = 200
        self.aborted = False

    def readAll(self):
        payload, self.payload = self.payload, b""
        return QByteArray(payload)

    def rawHeader(self, name):
        return QByteArray(self.headers.get(name, b""))

    def error(self):
        return self.failure

    def errorString(self):
        return "simulated network failure"

    def attribute(self, name):
        assert name == QNetworkRequest.Attribute.HttpStatusCodeAttribute
        return self.status

    def abort(self):
        self.aborted = True
        self.failure = QNetworkReply.NetworkError.OperationCanceledError
        self.finished.emit()


class FakeNetwork(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self.requests = []
        self.replies = []

    def get(self, request):
        self.requests.append(request)
        reply = FakeReply(self)
        self.replies.append(reply)
        return reply


class PluginHarness(ClipboardReplayPlugin):
    def __init__(self, data_dir: Path):
        QObject.__init__(self)
        self._other_info = ClipboardReplayConfig()
        self._other_info.set_on_change(self._on_config_changed)
        self._data_dir = data_dir
        self.logger = Mock()

    def run_on_gui(self, function, *args, **kwargs):
        function(*args, **kwargs)


@pytest.fixture
def monitor(tmp_path, monkeypatch, request, qapp):
    application = qapp
    clipboard = FakeClipboard()
    monkeypatch.setattr(plugin_module.QApplication,
                        "clipboard", lambda: clipboard)
    monkeypatch.setattr(download_module, "QNetworkAccessManager", FakeNetwork)
    cleanup_timers = Mock()
    monkeypatch.setattr(download_module, "Timer", cleanup_timers)
    launch = Mock()
    monkeypatch.setattr(download_module, "play_replay", launch)
    plugin = PluginHarness(tmp_path)
    plugin.other_info.from_dict(getattr(request, "param", {}))
    plugin.on_initialized()
    application.processEvents()
    yield plugin, clipboard, launch, application
    plugin.on_shutdown()
    application.processEvents()
    for call in cleanup_timers.call_args_list:
        call.args[1]()


def test_clipboard_download_and_duplicate_suppression(monitor):
    plugin, clipboard, launch, application = monitor
    handler = plugin._handlers[0]
    clipboard.set_text("https://openms.top/api/video/download/1")
    application.processEvents()
    assert len(handler._network.requests) == 1
    assert handler._network.requests[0].url().toString(
    ) == "https://openms.top/api/video/download/1"
    reply = handler._network.replies[0]
    reply.finished.emit()
    path = launch.call_args.args[0]
    assert path.name == "openms_1.avf"
    assert path.is_relative_to(Path(gettempdir()))
    assert not path.is_relative_to(plugin.data_dir)
    assert path.read_bytes() == b"replay data"
    assert not (plugin.data_dir / "downloads").exists()
    launch.assert_called_once()
    clipboard.set_text("same replay: https://openms.top/api/video/download/1")
    application.processEvents()
    assert len(handler._network.requests) == 1
    clipboard.set_text("other content")
    application.processEvents()
    clipboard.set_text("https://openms.top/api/video/download/1")
    application.processEvents()
    assert len(handler._network.requests) == 2


def test_latest_pending_video_wins(monitor):
    plugin, _, launch, _ = monitor
    handler = plugin._handlers[0]
    for video_id in ("1", "2", "3"):
        plugin._on_text_changed(
            f"https://openms.top/api/video/download/{video_id}")
    handler._network.replies[0].finished.emit()
    launch.assert_not_called()
    assert handler._network.requests[-1].url().toString().endswith("/3")
    handler._network.replies[1].finished.emit()
    assert launch.call_args.args[0].name == "openms_3.avf"


def test_saolei_clipboard_download_uses_temporary_file(monitor):
    plugin, clipboard, launch, application = monitor
    openms, saolei = plugin._handlers[:2]
    events = []
    plugin._output.connect(events.append)
    clipboard.set_text("https://www.saolei.wang/video/345964")
    application.processEvents()
    assert not openms._network.requests
    assert saolei._network.requests[0].url().toString() == (
        "https://www.saolei.wang/video/download/345964")
    reply = saolei._network.replies[0]
    reply.headers["Content-Disposition"] = b'attachment; filename="Exp%2071.66s%20replay.avf"'
    reply.finished.emit()
    path = launch.call_args.args[0]
    assert path.name == "saolei_345964.avf"
    assert path.is_relative_to(Path(gettempdir()))
    assert path.read_bytes() == b"replay data"
    assert not (plugin.data_dir / "downloads").exists()
    assert any(event["source"] == "扫雷网录像" and event["kind"]
               == "opened" for event in events)
    download_module.Timer.call_args.args[1]()
    assert not path.parent.exists()


def test_saolei_switch_cancels_only_saolei(monitor):
    plugin, _, launch, _ = monitor
    openms, saolei = plugin._handlers[:2]
    plugin._on_text_changed("https://openms.top/api/video/download/1")
    plugin._on_text_changed("https://www.saolei.wang/video/345964")
    openms_reply = openms._network.replies[0]
    saolei_reply = saolei._network.replies[0]
    plugin.other_info.enable_handler_saolei = False
    assert saolei_reply.aborted
    assert not openms_reply.aborted
    assert openms.enabled
    assert not saolei.enabled
    launch.assert_not_called()


def test_classic95_clipboard_download_and_dedup(monitor):
    plugin, clipboard, launch, application = monitor
    handler = plugin._handlers[2]
    events = []
    plugin._output.connect(events.append)
    assert plugin.other_info.enable_handler_classic95 is True
    clipboard.set_text("95经典扫雷|79228415-263-107")
    application.processEvents()
    assert handler._network.requests[0].url().toString() == (
        "https://mg.xiean.net:6789/v1/replay/open?season=263&id=107&uid=79228415")
    assert parse_qs(handler._network.requests[0].url().query()) == {
        "season": ["263"], "id": ["107"], "uid": ["79228415"]}
    assert all(not other._network.requests for other in plugin._handlers[:2])
    reply = handler._network.replies[0]
    reply.headers["Content-Disposition"] = b'attachment; filename="79228415-263-107.evf"'
    reply.finished.emit()
    path = launch.call_args.args[0]
    assert path.name == "classic95_79228415-263-107.evf"
    assert path.is_relative_to(Path(gettempdir()))
    assert not path.is_relative_to(plugin.data_dir)
    assert path.read_bytes() == b"replay data"
    assert any(event["source"] == "95经典扫雷小程序" and event["kind"] == "opened"
               for event in events)
    assert any(event["kind"] == "downloading" and event["video_id"] == "79228415-263-107"
               for event in events)
    clipboard.set_text("95经典扫雷|0079228415-0263-00107")
    application.processEvents()
    assert len(handler._network.requests) == 1
    clipboard.set_text("95经典扫雷|79228415-264-107")
    application.processEvents()
    assert handler._network.requests[-1].url(
    ).query() == "season=264&id=107&uid=79228415"
    cleanup_timers = download_module.Timer
    assert isinstance(cleanup_timers, Mock)
    assert cleanup_timers.call_args.args[0] == 10.0
    cleanup_timers.call_args.args[1]()
    assert not path.parent.exists()


def test_classic95_different_uids_are_not_duplicates(monitor):
    plugin, clipboard, launch, application = monitor
    handler = plugin._handlers[2]
    paths = []
    for uid in ("79228415", "79228416"):
        clipboard.set_text(f"95经典扫雷|{uid}-263-107")
        application.processEvents()
        assert handler._network.requests[-1].url(
        ).query() == f"season=263&id=107&uid={uid}"
        reply = handler._network.replies[-1]
        reply.headers["Content-Disposition"] = b'attachment; filename="replay.evf"'
        reply.finished.emit()
        paths.append(launch.call_args.args[0])
    assert len(handler._network.requests) == 2
    assert launch.call_count == 2
    assert [path.name for path in paths] == [
        "classic95_79228415-263-107.evf", "classic95_79228416-263-107.evf"]


def test_classic95_old_code_does_not_download(monitor):
    plugin, clipboard, launch, application = monitor
    clipboard.set_text("95经典扫雷|263-117")
    application.processEvents()
    assert all(not handler._network.requests for handler in plugin._handlers)
    launch.assert_not_called()


def test_classic95_switch_and_global_switch_preserve_choice(monitor):
    plugin, _, launch, application = monitor
    openms, _, handler = plugin._handlers[:3]
    plugin._on_text_changed("https://openms.top/api/video/download/1")
    plugin._on_text_changed("95经典扫雷|79228415-263-107")
    reply = handler._network.replies[0]
    plugin.other_info.enable_handler_classic95 = False
    assert reply.aborted
    assert not openms._network.replies[0].aborted
    assert openms.enabled
    assert not handler.enabled
    plugin.other_info.enable_feature = False
    plugin.other_info.enable_feature = True
    application.processEvents()
    assert plugin.other_info.enable_handler_classic95 is False
    assert not handler.enabled
    launch.assert_not_called()


@pytest.mark.parametrize("monitor", [
    {"enable_feature": True, "enable_handler_classic95": True},
    {"enable_feature": True, "enable_handler_classic95": False},
    {"enable_feature": False, "enable_handler_classic95": True},
    {"enable_feature": False, "enable_handler_classic95": False},
], indirect=True)
def test_classic95_saved_switches_control_download(monitor):
    plugin, clipboard, _, application = monitor
    handler = plugin._handlers[2]
    expected = plugin.other_info.enable_feature and plugin.other_info.enable_handler_classic95
    assert handler.enabled == expected
    clipboard.set_text("95经典扫雷|79228415-263-107")
    application.processEvents()
    assert len(handler._network.requests) == int(expected)


@pytest.mark.parametrize("failure", ["html", "empty", "size", "timeout", "network", "status"])
def test_failed_download_does_not_play(monitor, failure):
    plugin, _, launch, _ = monitor
    handler = plugin._handlers[0]
    plugin._on_text_changed("https://openms.top/api/video/download/1")
    reply = handler._network.replies[0]
    if failure == "html":
        reply.headers["Content-Type"] = b"text/html"
    elif failure == "empty":
        reply.payload = b""
    elif failure == "network":
        reply.failure = QNetworkReply.NetworkError.ContentNotFoundError
    elif failure == "status":
        reply.status = 404
    elif failure == "size":
        reply.downloadProgress.emit(0, MAX_DOWNLOAD_BYTES + 1)
    elif failure == "timeout":
        handler._on_timeout()
    if handler._reply is not None:
        reply.finished.emit()
    launch.assert_not_called()
    assert handler._reply is None
    assert not (plugin.data_dir / "downloads").exists()


def test_configuration_forwarding_and_resume(monitor):
    plugin, clipboard, launch, application = monitor
    handler = plugin._handlers[0]
    assert ClipboardReplayPlugin._on_config_changed is BasePlugin._on_config_changed
    plugin.other_info.enable_feature = False
    clipboard.set_text("https://openms.top/api/video/download/1")
    application.processEvents()
    assert not handler._network.requests
    plugin.other_info.enable_feature = True
    application.processEvents()
    assert len(handler._network.requests) == 1
    reply = handler._network.replies[0]
    plugin.other_info.enable_feature = False
    assert reply.aborted
    launch.assert_not_called()


def test_shutdown_cancels_download_and_disconnects_clipboard(monitor):
    plugin, clipboard, launch, application = monitor
    handler = plugin._handlers[0]
    plugin._on_text_changed("https://openms.top/api/video/download/1")
    reply = handler._network.replies[0]
    plugin.on_shutdown()
    application.processEvents()
    assert reply.aborted
    clipboard.set_text("https://openms.top/api/video/download/2")
    application.processEvents()
    assert len(handler._network.requests) == 1
    launch.assert_not_called()


class RecordingHandler(ClipboardHandler[str]):
    handler_id = "recording"
    display_name = "Recording"

    def match(self, text: str) -> str | None:
        return text if text.startswith("record:") else None

    def handle(self, match: str) -> None:
        self.logger.info(match)

    def cancel(self) -> None:
        self.logger.debug("cancelled")


def test_handler_match_dispatch_and_dedup(tmp_path):
    logger = Mock()
    handler = RecordingHandler(tmp_path, logger)
    assert not handler.process("unmatched")
    assert handler.process("record:first")
    assert handler.process("record:first")
    logger.info.assert_called_once_with("record:first")
    assert not handler.process("unmatched")
    assert handler.process("record:first")
    assert logger.info.call_count == 2


def test_handler_disable_and_shutdown(tmp_path):
    logger = Mock()
    handler = RecordingHandler(tmp_path, logger)
    handler.set_enabled(False)
    logger.debug.assert_called_once_with("cancelled")
    assert not handler.process("record:first")
    handler.set_enabled(True)
    assert handler.process("record:first")
    handler.shutdown()
    handler.set_enabled(True)
    assert not handler.process("record:second")
    logger.info.assert_called_once_with("record:first")


def test_all_matching_handlers_run_independently(monitor):
    plugin, _, _, _ = monitor
    first = RecordingHandler(plugin.data_dir, Mock(), parent=plugin)
    second = RecordingHandler(plugin.data_dir, Mock(), parent=plugin)
    plugin._handlers.extend([first, second])
    plugin._on_text_changed("record:first")
    plugin._on_text_changed("record:first")
    first.logger.info.assert_called_once_with("record:first")
    second.logger.info.assert_called_once_with("record:first")


@pytest.mark.parametrize("stage", ["match", "handle"])
def test_handler_failure_does_not_block_other_handlers(monitor, monkeypatch, stage):
    plugin, _, _, _ = monitor
    broken = RecordingHandler(plugin.data_dir, Mock(), parent=plugin)
    following = RecordingHandler(plugin.data_dir, Mock(), parent=plugin)
    monkeypatch.setattr(broken, stage, Mock(
        side_effect=ValueError("broken handler")))
    plugin._handlers.insert(0, broken)
    plugin._handlers.append(following)
    plugin._on_text_changed("record:first")
    following.logger.info.assert_called_once_with("record:first")
    plugin.logger.error.assert_called_once()


def test_settings_and_shutdown_reach_all_handlers(monitor):
    plugin, _, _, application = monitor
    first = RecordingHandler(plugin.data_dir, Mock(), parent=plugin)
    second = RecordingHandler(plugin.data_dir, Mock(), parent=plugin)
    plugin._handlers.extend([first, second])
    plugin.other_info.enable_feature = False
    for handler in (first, second):
        assert not handler.enabled
        handler.logger.debug.assert_called_once_with("cancelled")
    plugin.other_info.enable_feature = True
    application.processEvents()
    assert first.enabled and second.enabled
    plugin.on_shutdown()
    application.processEvents()
    for handler in (first, second):
        assert not handler.enabled
        assert handler.logger.debug.call_count == 2


def test_failed_handle_can_retry_the_same_match(tmp_path, monkeypatch):
    handler = RecordingHandler(tmp_path, Mock())
    execute = Mock(side_effect=[ValueError("temporary failure"), None])
    monkeypatch.setattr(handler, "handle", execute)
    with pytest.raises(ValueError, match="temporary failure"):
        handler.process("record:first")
    assert handler.process("record:first")
    assert execute.call_count == 2


def test_registered_handler_switches_are_generated():
    fields = ClipboardReplayConfig.get_fields()
    assert "enable_feature" in fields
    for handler_type in plugin_module.HANDLER_TYPES:
        field = fields[handler_type.config_key()]
        assert isinstance(field, BoolConfig)
        assert field.default is True
        assert field.label == handler_type.display_name


def test_new_handler_switch_is_persisted_without_manual_field_definition():
    class ExtraConfig(OtherInfoBase):
        enable_feature = BoolConfig(default=True, label="Global")

    add_handler_fields(ExtraConfig, [RecordingHandler])
    config = ExtraConfig()
    assert config.enable_handler_recording is True
    config.enable_feature = False
    config.enable_handler_recording = False
    saved = config.to_dict()
    assert saved == {"enable_feature": False,
                     "enable_handler_recording": False}
    restored = ExtraConfig()
    restored.from_dict(saved)
    assert restored.to_dict() == saved


def test_duplicate_handler_id_is_rejected():
    class ExtraConfig(OtherInfoBase):
        pass

    with pytest.raises(ValueError, match="Duplicate clipboard handler"):
        add_handler_fields(ExtraConfig, [RecordingHandler, RecordingHandler])


@pytest.mark.parametrize("monitor", [
    {"enable_feature": True, "enable_handler_openms": True},
    {"enable_feature": True, "enable_handler_openms": False},
    {"enable_feature": False, "enable_handler_openms": True},
    {"enable_feature": False, "enable_handler_openms": False},
], indirect=True)
def test_saved_global_and_handler_switches_control_startup(monitor):
    plugin, clipboard, _, application = monitor
    handler = plugin._handlers[0]
    expected = plugin.other_info.enable_feature and plugin.other_info.enable_handler_openms
    assert handler.enabled == expected
    clipboard.set_text("https://openms.top/api/video/download/1")
    application.processEvents()
    assert len(handler._network.requests) == int(expected)


def test_disabling_one_handler_cancels_only_its_work(monitor):
    plugin, _, launch, _ = monitor
    openms = plugin._handlers[0]
    recording = RecordingHandler(plugin.data_dir, Mock(), parent=plugin)
    plugin._handlers.append(recording)
    plugin._on_text_changed("https://openms.top/api/video/download/1")
    reply = openms._network.replies[0]
    plugin._on_text_changed("record:first")
    plugin.other_info.enable_handler_openms = False
    assert reply.aborted
    assert not openms.enabled
    assert recording.enabled
    assert plugin.other_info.enable_feature is True
    plugin._on_text_changed("record:first")
    recording.logger.info.assert_called_once_with("record:first")
    recording.logger.debug.assert_not_called()
    launch.assert_not_called()


def test_global_switch_preserves_disabled_handler_and_resume_checks_clipboard(monitor):
    plugin, clipboard, _, application = monitor
    handler = plugin._handlers[0]
    plugin.other_info.enable_handler_openms = False
    clipboard.set_text("https://openms.top/api/video/download/1")
    application.processEvents()
    plugin.other_info.enable_feature = False
    plugin.other_info.enable_feature = True
    application.processEvents()
    assert plugin.other_info.enable_handler_openms is False
    assert not handler.enabled
    assert not handler._network.requests
    plugin.other_info.enable_handler_openms = True
    application.processEvents()
    assert handler.enabled
    assert len(handler._network.requests) == 1


def test_individual_enable_waits_for_global_switch(monitor):
    plugin, clipboard, _, application = monitor
    handler = plugin._handlers[0]
    plugin.other_info.enable_feature = False
    plugin.other_info.enable_handler_openms = False
    clipboard.set_text("https://openms.top/api/video/download/1")
    application.processEvents()
    plugin.other_info.enable_handler_openms = True
    application.processEvents()
    assert not handler.enabled
    assert not handler._network.requests
    plugin.other_info.enable_feature = True
    application.processEvents()
    assert handler.enabled
    assert len(handler._network.requests) == 1


def test_replay_temporary_directory_is_cleaned_after_playback_handoff(monitor):
    plugin, _, launch, _ = monitor
    handler = plugin._handlers[0]
    plugin._on_text_changed("https://openms.top/api/video/download/1")
    handler._network.replies[0].finished.emit()
    path = launch.call_args.args[0]
    assert path.exists()
    assert download_module.Timer.call_args.args[0] == 10.0
    cleanup = download_module.Timer.call_args.args[1]
    plugin.on_shutdown()
    assert path.exists()
    cleanup()
    assert not path.exists()
    assert not path.parent.exists()


def test_failed_player_start_removes_temporary_replay(monitor):
    plugin, _, launch, _ = monitor
    launch.side_effect = OSError("cannot start player")
    handler = plugin._handlers[0]
    plugin._on_text_changed("https://openms.top/api/video/download/1")
    handler._network.replies[0].finished.emit()
    path = launch.call_args.args[0]
    assert not path.exists()
    assert not path.parent.exists()
    download_module.Timer.assert_not_called()
    assert not (plugin.data_dir / "downloads").exists()


def test_single_log_combines_handler_and_system_output(monitor, qtbot):
    plugin, _, _, _ = monitor
    widget = plugin._create_widget()
    qtbot.addWidget(widget)
    recording = RecordingHandler(plugin.data_dir, Mock(), parent=plugin)
    recording.output.connect(plugin._output)
    plugin._report("系统输出")
    plugin._handlers[0].report("录像输出")
    recording.report("<b>自己的文本</b>", kind="error")
    qtbot.waitUntil(lambda: "自己的文本" in widget.log_output.toPlainText())
    output = widget.log_output.toPlainText()
    assert "[系统] 系统输出" in output
    assert "[开源扫雷网录像] 录像输出" in output
    assert "[错误] [Recording] <b>自己的文本</b>" in output
    assert len(widget.findChildren(QPlainTextEdit)) == 1
    assert not widget.findChildren(QTabWidget)


def test_handler_state_does_not_override_global_log_status(monitor, qtbot):
    plugin, _, _, _ = monitor
    widget = plugin._create_widget()
    qtbot.addWidget(widget)
    plugin._report("已启动", kind="state", enabled=True)
    qtbot.waitUntil(lambda: widget.status_label.text() == "监听中")
    plugin.other_info.enable_handler_openms = False
    qtbot.waitUntil(lambda: "已停用" in widget.log_output.toPlainText())
    assert widget.status_label.text() == "监听中"
    plugin.other_info.enable_feature = False
    qtbot.waitUntil(lambda: widget.status_label.text() == "已暂停")


def test_download_milestones_reach_the_shared_log(monitor, qtbot):
    plugin, _, _, _ = monitor
    widget = plugin._create_widget()
    qtbot.addWidget(widget)
    plugin._on_text_changed("https://openms.top/api/video/download/1")
    plugin._handlers[0]._network.replies[0].finished.emit()
    qtbot.waitUntil(lambda: "已提交录像播放" in widget.log_output.toPlainText())
    output = widget.log_output.toPlainText()
    assert "识别到录像 1" in output
    assert "正在下载录像 1" in output
    assert "录像下载完成，使用系统临时文件" in output
    assert "10 秒后清理" in output


def test_worker_output_is_delivered_to_gui_thread(monitor, qtbot):
    plugin, _, _, _ = monitor
    widget = plugin._create_widget()
    qtbot.addWidget(widget)

    class WorkerHandler(RecordingHandler):
        finished = Signal()

        @Slot()
        def run_report(self):
            self.report("工作线程输出")
            self.finished.emit()

    handler = WorkerHandler(plugin.data_dir, Mock())
    thread = QThread()
    handler.moveToThread(thread)
    handler.output.connect(plugin._output)
    thread.started.connect(handler.run_report)
    handler.finished.connect(thread.quit)
    thread.finished.connect(handler.deleteLater)
    try:
        thread.start()
        qtbot.waitUntil(lambda: "工作线程输出" in widget.log_output.toPlainText())
        assert widget.thread() == qtbot._request.getfixturevalue("qapp").thread()
    finally:
        thread.quit()
        assert thread.wait(2000)


def test_log_is_bounded_and_can_be_cleared(qtbot):
    widget = ClipboardReplayWidget()
    qtbot.addWidget(widget)
    for index in range(1100):
        widget.handle_output(
            {"message": f"entry {index}", "source": "Recording"})
    assert widget.log_output.document().blockCount() <= 1000
    assert widget._clear_button.isEnabled()
    widget._clear_button.click()
    assert not widget.log_output.toPlainText()
    assert not widget._clear_button.isEnabled()
