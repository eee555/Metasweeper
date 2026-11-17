from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Timer
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, QUrl, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from plugin_manager.app_paths import get_executable_dir
from .base import ClipboardHandler
from ..replay import MAX_DOWNLOAD_BYTES, play_replay, replay_suffix
from utils.plugin_i18n import PluginTranslate

_translate = PluginTranslate("ClipboardReplay")

if TYPE_CHECKING:
    from loguru import Logger


class ReplayDownloadHandler(ClipboardHandler[str]):
    download_url_template = ""

    def build_download_url(self, video_id: str) -> str:
        return self.download_url_template.format(video_id=video_id)

    def __init__(self, data_dir: Path, logger: Logger, parent: QObject | None = None):
        super().__init__(data_dir, logger, parent)
        self._pending_id: str | None = None
        self._active_id: str | None = None
        self._reply: QNetworkReply | None = None
        self._buffer = bytearray()
        self._download_error = ""
        self._network = QNetworkAccessManager(self)
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._on_timeout)

    def handle(self, match: str) -> None:
        self._pending_id = match
        if self._reply is None:
            self.report(_translate("ClipboardReplay", "识别到录像 {id}").format(id=match), kind="matched", video_id=match)
            self._start_download()
        else:
            self.report(_translate("ClipboardReplay", "录像 {id} 已加入等待，保留最新请求").format(id=match),
                        kind="queued", video_id=match)

    def _start_download(self) -> None:
        if not self.enabled or self._pending_id is None:
            return
        self._active_id = self._pending_id
        self._pending_id = None
        self._buffer.clear()
        self._download_error = ""
        request = QNetworkRequest(QUrl(
            self.build_download_url(self._active_id)))
        request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader,
                          "MetaSweeper-ClipboardReplay/1.0")
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.SameOriginRedirectPolicy)
        request.setTransferTimeout(15000)
        self._reply = self._network.get(request)
        self._reply.readyRead.connect(self._read_download)
        self._reply.downloadProgress.connect(self._on_download_progress)
        self._reply.finished.connect(self._finish_download)
        self._timeout.start(30000)
        self.logger.info(
            f"Downloading {self.display_name} replay {self._active_id}")
        self.report(_translate("ClipboardReplay", "正在下载录像 {id}").format(id=self._active_id), kind="downloading",
                    video_id=self._active_id)

    @Slot(int, int)
    def _on_download_progress(self, received: int, total: int) -> None:
        if max(received, total) > MAX_DOWNLOAD_BYTES:
            self._abort_download(_translate(
                "ClipboardReplay", "录像超过 32 MiB 的下载限制"))

    @Slot()
    def _read_download(self) -> None:
        if self._reply is None:
            return
        chunk = bytes(self._reply.readAll())
        if len(self._buffer) + len(chunk) > MAX_DOWNLOAD_BYTES:
            self._abort_download(_translate(
                "ClipboardReplay", "录像超过 32 MiB 的下载限制"))
            return
        self._buffer.extend(chunk)

    @Slot()
    def _on_timeout(self) -> None:
        self._abort_download(_translate("ClipboardReplay", "录像下载超时"))

    def _abort_download(self, reason: str) -> None:
        self._download_error = reason
        if self._reply is not None:
            self._reply.abort()

    @Slot()
    def _finish_download(self) -> None:
        reply = self._reply
        if reply is None:
            return
        self._timeout.stop()
        self._read_download()
        self._reply = None
        try:
            if not self.enabled or self._pending_id is not None:
                if self.enabled:
                    self.report(_translate("ClipboardReplay", "已跳过旧录像，准备处理最新请求"), kind="skipped")
                return
            if self._download_error:
                raise ValueError(self._download_error)
            if reply.error() != QNetworkReply.NetworkError.NoError:
                raise OSError(reply.errorString())
            status = reply.attribute(
                QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if status != 200:
                raise ValueError(_translate("ClipboardReplay", "Unexpected HTTP status: {status}").format(status=status))
            suffix = replay_suffix(
                bytes(reply.rawHeader("Content-Disposition")
                      ).decode("utf-8", errors="replace"),
                bytes(reply.rawHeader("Content-Type")
                      ).decode("ascii", errors="replace"),
            )
            if not self._buffer:
                raise ValueError(_translate(
                    "ClipboardReplay", "下载的录像为空"))
            temporary = TemporaryDirectory(
                prefix="metasweeper_clipboard_", ignore_cleanup_errors=True)
            path = Path(temporary.name) / \
                f"{self.handler_id}_{self._active_id}{suffix}"
            try:
                path.write_bytes(self._buffer)
                self.report(_translate("ClipboardReplay", "录像下载完成，使用系统临时文件"),
                            kind="downloaded", path=str(path))
                play_replay(path, get_executable_dir())
                cleanup = Timer(10.0, temporary.cleanup)
                cleanup.daemon = True
                cleanup.start()
            except Exception:
                temporary.cleanup()
                raise
            self.logger.info(f"Opened replay: {path}")
            self.report(_translate("ClipboardReplay", "已提交录像播放，临时文件将在 10 秒后清理"),
                        kind="opened", path=str(path))
        except Exception as error:
            self.reset_match()
            self.logger.error(
                f"Cannot open {self.display_name} replay {self._active_id}: {error}")
            self.report(_translate("ClipboardReplay", "录像处理失败：{error}").format(error=error), kind="error")
        finally:
            self._buffer.clear()
            self._active_id = None
            reply.deleteLater()
            self._start_download()

    def cancel(self) -> None:
        active = self._reply is not None or self._pending_id is not None
        self._pending_id = None
        self._timeout.stop()
        self._abort_download(_translate("ClipboardReplay", "录像处理已取消"))
        if active:
            self.report(_translate("ClipboardReplay", "已取消下载"), kind="cancelled")
