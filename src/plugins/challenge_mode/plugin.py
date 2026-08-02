"""
challenge_mode - 无猜闯关插件

顺序闯关，共1000关（难度1#0 ~ 难度100#9），不可跳关。
"""
from __future__ import annotations

import json
import base64
from pathlib import Path

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QWidget

_translate = QCoreApplication.translate

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

from plugin_sdk import BasePlugin, PluginInfo, make_plugin_icon, WindowMode
from shared_types.events import CloseEvent, GameFinishedEvent, LanguageChangeEvent
from shared_types.enums import GameMode
from shared_types.commands import NewPresetGameCommand, MouseClickCommand

from .widgets import ChallengeModeUI


_LEVELS_KEY = b"Ch4ll3ng3M0deK3y!2026SecureKey!!"


def _encrypt(data: bytes) -> bytes:
    nonce = get_random_bytes(12)
    cipher = AES.new(_LEVELS_KEY, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(data)
    return base64.b64encode(nonce + tag + ciphertext)


def _decrypt(data: bytes) -> bytes:
    raw = base64.b64decode(data)
    nonce = raw[:12]
    tag = raw[12:28]
    ciphertext = raw[28:]
    cipher = AES.new(_LEVELS_KEY, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)


def _find_center_click(board: list[list[int]]) -> tuple[int, int]:
    rows = len(board)
    cols = len(board[0]) if rows else 0
    cr, cc = rows // 2, cols // 2
    best = None
    best_dist = rows * rows + cols * cols
    for r in range(rows):
        for c in range(cols):
            if board[r][c] == -1:
                continue
            d = (r - cr) ** 2 + (c - cc) ** 2
            if d < best_dist or (d == best_dist and board[r][c] == 0 and (best is None or board[best[0]][best[1]] != 0)):
                best_dist = d
                best = (r, c)
    return best if best else (cr, cc)


class ChallengeModePlugin(BasePlugin):
    """无猜闯关插件"""

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="无猜闯关",
            version="1.0.0",
            author="eee555",
            description=_translate("Form", "顺序闯关模式 - 共1000关，不可跳关"),
            icon=make_plugin_icon("#E65100", "闯", 64),
            window_mode=WindowMode.TAB,
            required_controls=[NewPresetGameCommand, MouseClickCommand],
        )

    def _setup_subscriptions(self) -> None:
        self.subscribe(GameFinishedEvent, self._on_game_finished)
        self.subscribe(CloseEvent, self._on_close)
        self.subscribe(LanguageChangeEvent, self._on_language_change)

    def _create_widget(self) -> QWidget:
        self._ui = ChallengeModeUI()
        self._ui.set_callbacks(
            start_cb=self._on_start_click,
            next_cb=self._on_next_click,
            reset_cb=self._on_reset_click,
        )
        return self._ui

    def on_initialized(self) -> None:
        self._load_levels()
        self._load_save()
        self._push_ui_update()

    def on_shutdown(self) -> None:
        self._save()

    # ═══════════════════════════════════════════════════════════
    # 数据管理
    # ═══════════════════════════════════════════════════════════

    def _load_levels(self):
        path = Path(__file__).parent / "levels.dat"
        if not path.exists():
            self.logger.error(f"levels.dat 不存在: {path}")
            self._levels = []
            return
        try:
            raw = _decrypt(path.read_bytes())
            self._levels = json.loads(raw)
            self.logger.info(f"已加载 {len(self._levels)} 关")
        except Exception as e:
            self.logger.error(f"加载 levels.dat 失败: {e}")
            self._levels = []

    def _load_save(self):
        path = self.data_dir / "save.dat"
        if path.exists():
            try:
                raw = _decrypt(path.read_bytes())
                data = json.loads(raw)
                self._current_level = data.get("current_level", 0)
                self._completed = set(data.get("completed", []))
                self.logger.info(f"已加载存档，当前第 {self._current_level + 1} 关")
                return
            except Exception as e:
                self.logger.warning(f"读取存档失败: {e}")
        self._current_level = 0
        self._completed = set()

    def _save(self):
        path = self.data_dir / "save.dat"
        data = {
            "current_level": self._current_level,
            "completed": sorted(self._completed),
        }
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        path.write_bytes(_encrypt(raw))

    # ═══════════════════════════════════════════════════════════
    # 闯关逻辑
    # ═══════════════════════════════════════════════════════════

    def _start_level(self, index: int):
        if not self._levels or index >= len(self._levels):
            return
        self._current_level = index
        level = self._levels[index]
        board = level["b"]

        if not self.has_control_auth(NewPresetGameCommand):
            self.logger.warning("没有 NewPresetGameCommand 权限")
            return

        self.send_command(NewPresetGameCommand(
            board=board,
            mode=level.get("mode", GameMode.StrictNoGuess.value)
        ))

        r = level.get("x")
        c = level.get("y")
        self.send_command(MouseClickCommand(row=r, col=c, button=0))

        self._save()
        self._push_ui_update()

    def _on_start_click(self):
        self._start_level(self._current_level)

    def _on_next_click(self):
        if self._current_level in self._completed:
            next_idx = self._current_level + 1
            if next_idx < len(self._levels):
                self._start_level(next_idx)

    def _on_reset_click(self):
        self._current_level = 0
        self._completed = set()
        self._save()
        self._push_ui_update()

    # ═══════════════════════════════════════════════════════════
    # 事件处理
    # ═══════════════════════════════════════════════════════════

    def _on_game_finished(self, event: GameFinishedEvent):
        if event.game_state != GameMode.StrictNoGuess.value or not event.is_fair:
            return

        if self._current_level < len(self._levels):
            self._completed.add(self._current_level)
            self._save()
            self._push_ui_update()

            if self._ui and self._ui.is_auto_next():
                next_idx = self._current_level + 1
                if next_idx < len(self._levels):
                    self._start_level(next_idx)

    def _on_close(self, event: CloseEvent):
        self._save()

    def _on_language_change(self, event: LanguageChangeEvent) -> None:
        self.run_on_gui(self._ui.retranslateUi)
        self._push_ui_update()

    def _push_ui_update(self):
        if not self._levels:
            return
        total = len(self._levels)
        idx = self._current_level
        level = self._levels[idx] if idx < total else None
        self._ui._signal_update.emit({
            "current_level": idx,
            "total_levels": total,
            "row": level["r"] if level else 0,
            "col": level["c"] if level else 0,
            "mines": level["m"] if level else 0,
            "completed": idx in self._completed,
            "all_done": len(self._completed) >= total,
        })
