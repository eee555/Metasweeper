from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Generic, TypeVar

from PySide6.QtCore import QObject, Signal
from utils.plugin_i18n import PluginTranslate

_translate = PluginTranslate("ClipboardReplay")

if TYPE_CHECKING:
    from loguru import Logger


MatchT = TypeVar("MatchT")


class ClipboardHandler(QObject, Generic[MatchT]):
    output = Signal(object)
    handler_id = ""
    display_name = ""

    @classmethod
    def config_key(cls) -> str:
        handler_id = cls.handler_id or cls.__name__
        if not handler_id.isidentifier() or handler_id.startswith("_"):
            raise ValueError(f"Invalid clipboard handler ID: {handler_id}")
        return f"enable_handler_{handler_id}"

    def __init__(self, data_dir: Path, logger: Logger, parent: QObject | None = None):
        super().__init__(parent)
        self.data_dir = data_dir
        self.logger = logger
        self._enabled = True
        self._stopped = False
        self._last_match: MatchT | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled and not self._stopped

    def report(self, message: str = "", **details: object) -> None:
        self.output.emit({
            "kind": "log",
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": message,
            "source": self.display_name or self.handler_id or type(self).__name__,
            **details,
        })

    def match(self, text: str) -> MatchT | None:
        """Return a parsed match, or None when this handler does not apply."""
        raise NotImplementedError

    def handle(self, match: MatchT) -> None:
        """Handle a match without blocking the plugin event loop."""
        raise NotImplementedError

    def process(self, text: str) -> bool:
        if not self.enabled:
            return False
        match = self.match(text)
        if match == self._last_match:
            return match is not None
        self._last_match = match
        if match is None:
            return False
        try:
            self.handle(match)
        except Exception:
            self.reset_match()
            raise
        return True

    def reset_match(self) -> None:
        self._last_match = None

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.reset_match()
        if not self.enabled:
            self.cancel()
        self.report(_translate("ClipboardReplay", "已启用") if self.enabled else _translate("ClipboardReplay", "已停用"),
                    kind="state", enabled=self.enabled)

    def cancel(self) -> None:
        """Cancel outstanding work, if this handler has any."""
        pass

    def shutdown(self) -> None:
        self._stopped = True
        self.set_enabled(False)
