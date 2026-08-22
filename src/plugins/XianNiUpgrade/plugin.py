"""
XianNiUpgrade - 修仙升级插件主体

每局扫雷胜利后获得经验，从凡人修炼到一招摧毁108颗修正星的绝世强者，共100级。
"""
from __future__ import annotations

import math
import json
import base64
import hashlib
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Any

from PyQt5.QtCore import QCoreApplication, QTimer, pyqtSignal
from PyQt5.QtWidgets import QWidget, QMessageBox

_translate = QCoreApplication.translate

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

import ms_toollib as ms

from plugin_sdk import BasePlugin, PluginInfo, make_plugin_icon, WindowMode
from shared_types.events import CloseEvent, GameFinishedEvent, LanguageChangeEvent
from plugins.services.saolei_website import SaoleiWebsiteService

from .config import (
    XianNiUpgradeConfig,
    DEFAULT_API_URL,
    DEFAULT_IDENTIFIER,
    VALIDATE_TIMEOUT_SEC,
    api_url_transport_error,
    resolve_api_url,
)
from .widgets import XianNiUpgradeUI, RulesDialog
from .models import get_image_index
from . import distribution as _dist

# 游戏设置默认玩家标识，站点与插件均拒绝以此上传
_ANONYMOUS_IDENTIFIERS = frozenset({
    DEFAULT_IDENTIFIER,
    "匿名玩家",
})
_UPLOAD_TIMEOUT_SEC = 10
_AUTO_UPLOAD_MIN_INTERVAL_SEC = 60
_AUTO_UPLOAD_MAX_INTERVAL_SEC = 600


# 预计算累积分布表（稀有局面用）
_DIST_CUM: dict[str, list[int]] = {}
for _prefix in ('beg', 'int', 'exp'):
    for _field in ('cell1', 'cell2', 'cell3', 'cell4', 'cell5', 'cell6',
                    'cell7', 'cell8', 'bbbv', 'op', 'isl'):
        _key = f'{_prefix}_{_field}'
        _table = getattr(_dist, _key)
        _cum = 0
        _arr: list[int] = []
        for _v in _table:
            _cum += _v
            _arr.append(_cum)
        _DIST_CUM[_key] = _arr
_DIST_TOTAL = 100_000_000
_DIST_PREFIX = {3: 'beg', 4: 'int', 5: 'exp'}

# 模式难度系数
_MODE_K: dict[int, float] = {
    0: 1.0,    # 标准
    4: 0.8,    # Win7
    5: 0.2,    # 经典无猜
    6: 0.25,   # 强无猜
    7: 2.0,    # 弱无猜
}


def _cum_prob(prefix: str, field: str, value: int) -> float:
    """
    双向累积概率 —— 取 P(X<=v) 与 P(X>=v) 中较小者，
    衡量该数值在分布中的罕见程度。
    """
    key = f'{prefix}_{field}'
    arr = _DIST_CUM.get(key)
    if not arr:
        return 1.0
    total = arr[-1]

    if value >= len(arr):
        cum_le = total
        cum_ge = 0
    else:
        cum_le = arr[value]
        cum_ge = total - (arr[value - 1] if value > 0 else 0)

    p_le = max(cum_le, 0.5) / total
    p_ge = max(cum_ge, 0.5) / total
    return min(p_le, p_ge)


# AES-GCM 加密密钥（明文写死，只防无编程知识的人）
_ENCRYPT_KEY = b"f[{gr!%$%^65sr60"




def _encrypt(data: bytes) -> bytes:
    nonce = get_random_bytes(12)
    cipher = AES.new(_ENCRYPT_KEY, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(data)
    return base64.b64encode(nonce + tag + ciphertext)


def _decrypt(data: bytes) -> bytes:
    raw = base64.b64decode(data)
    nonce = raw[:12]
    tag = raw[12:28]
    ciphertext = raw[28:]
    cipher = AES.new(_ENCRYPT_KEY, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)


def _total_xp(level: int) -> int:
    """升到第 level 级所需的累计总经验"""
    return math.floor(
        0.025 * level ** 4.29637
        + 11.37 * level ** 2.13
        + 88.605 * level ** 0.885
    )


class XianNiUpgradePlugin(BasePlugin[XianNiUpgradeConfig]):
    """修仙升级插件"""

    _schedule_pending = pyqtSignal()

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="雷修境界",
            version="1.0.0",
            author="eee555",
            description=_translate("Form", "仙逆背景的修炼体系 - 每局扫雷胜利获得经验，从凡人修炼到一招摧毁108颗修正星的绝世强者"),
            icon=make_plugin_icon("#8E24AA", "仙", 64),
            window_mode=WindowMode.TAB,
            other_info=XianNiUpgradeConfig,
        )

    def _setup_subscriptions(self) -> None:
        self.subscribe(GameFinishedEvent, self._on_game_finished)
        self.subscribe(CloseEvent, self._on_close)
        self.subscribe(LanguageChangeEvent, self._on_language_change)

    def _create_widget(self) -> QWidget:
        self._ui = XianNiUpgradeUI()
        assets_path = Path(__file__).parent
        self._ui.set_image_dir(assets_path)
        self._ui.set_absorb_callbacks(self.validate_replays, self.absorb_replays)
        self._ui.set_save_callbacks(self.validate_save, self.absorb_save)
        self._ui.set_upload_callback(self.upload_ranking)
        self._ui.set_first_visible_callback(self._maybe_show_rules_dialog)
        return self._ui

    def on_initialized(self) -> None:
        self._guide_dialog_open = False
        self._upload_in_progress = False
        self._pending_upload = False
        self._last_upload_attempt = 0.0
        self._auto_upload_fail_count = 0
        self._pending_timer = QTimer(self)
        self._pending_timer.setSingleShot(True)
        self._pending_timer.timeout.connect(self._on_pending_upload_timeout)
        self._schedule_pending.connect(self._start_pending_timer)
        self._load_data()
        self._migrate_config_flags()
        self._saolei_service = self.wait_for_service(SaoleiWebsiteService, timeout=10.0)
        if self._saolei_service is None:
            self.logger.warning("SaoleiWebsiteService 未就绪，排行昵称将回退为游戏标识")
        self._push_ui_update()

    def _migrate_config_flags(self) -> None:
        """rank_upload_guide_seen → rules_dialog_seen；丢弃 display_name。"""
        if not self.other_info:
            return
        path = self.data_dir / "config.json"
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return
        if not isinstance(raw, dict):
            return
        changed = False
        if "rank_upload_guide_seen" in raw and "rules_dialog_seen" not in raw:
            self.other_info.rules_dialog_seen = bool(raw["rank_upload_guide_seen"])
            changed = True
        if "display_name" in raw:
            changed = True
        if changed:
            self.save_config()

    def on_shutdown(self) -> None:
        timer = getattr(self, "_pending_timer", None)
        if timer is not None:
            timer.stop()
        self._save_data()

    def validate_config(self, pending: dict[str, Any]) -> dict[str, str]:
        """令牌与当前游戏标识联网校验；匿名标识禁止开自动上传。"""
        errors: dict[str, str] = {}
        identifier = self._current_identifier()
        token = str(pending.get("upload_token") or "").strip()
        api_url = resolve_api_url(str(pending.get("api_url") or ""))

        if token and not self._is_anonymous_identifier(identifier):
            token_error = self._verify_upload_token(api_url, identifier, token)
            if token_error:
                errors["upload_token"] = token_error

        auto_upload = bool(pending.get("auto_upload", False))
        if auto_upload and identifier in _ANONYMOUS_IDENTIFIERS:
            errors["auto_upload"] = _translate(
                "Form",
                "当前仍是默认匿名标识，请先在游戏设置中修改玩家标识后再开启自动上传。",
            )
        return errors

    def _current_identifier(self) -> str:
        identifiers = getattr(self, "_identifiers", None) or []
        pid = getattr(self, "_current_pid", 0)
        if identifiers and 0 <= pid < len(identifiers):
            return str(identifiers[pid] or "").strip()
        return ""

    @staticmethod
    def _is_anonymous_identifier(identifier: str) -> bool:
        name = (identifier or "").strip()
        return (not name) or name in _ANONYMOUS_IDENTIFIERS

    def _verify_upload_token(self, api_url: str, identifier: str, token: str) -> str | None:
        """
        POST /api/verify。403 视为令牌不匹配；registered:false / 200 通过；
        网络失败返回错误文案。超时约 5 秒。
        """
        transport_error = api_url_transport_error(api_url)
        if transport_error:
            return transport_error

        url = api_url.rstrip("/") + "/api/verify"
        body = json.dumps(
            {"identifier": identifier, "upload_token": token},
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": f"MetaSweeper-XianNiUpgrade/{self.info.version}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=VALIDATE_TIMEOUT_SEC) as resp:
                status = int(getattr(resp, "status", 200))
                resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 403:
                return _translate(
                    "Form",
                    "令牌与当前玩家标识不匹配。请确认上传令牌，或更换玩家标识后重试。",
                )
            return _translate("Form", "无法校验上传令牌（HTTP %1）").replace(
                "%1", str(e.code)
            )
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            self.logger.warning(f"校验上传令牌失败: {e}")
            return _translate("Form", "无法校验上传令牌，请检查网络。")
        except Exception as e:
            self.logger.warning(f"校验上传令牌异常: {e}")
            return _translate("Form", "无法校验上传令牌，请检查网络。")

        if not (200 <= status < 300):
            return _translate("Form", "无法校验上传令牌（HTTP %1）").replace(
                "%1", str(status)
            )
        # registered: false 或其它 200 均通过
        return None

    def _calc_xp(self, event: GameFinishedEvent) -> int:
        """每局获得的经验值"""
        board = ms.Board(event.board)
        ioe = event.bbbv / (event.left + event.right + event.double)
        return self._calc_xp_base(
            event.mode, event.level, event.row, event.column, event.mine_num,
            event.rtime, event.bbbv, board.cell1, board.cell2, board.cell3, board.cell4, board.cell5,
            board.cell6, board.cell7, board.cell8, board.op, board.isl, ioe, event.rce == 0
        )

    def _calc_xp2(self, video: ms.EvfVideo) -> int:
        """通过录像计算经验值"""
        board = ms.Board(video.board)
        return self._calc_xp_base(
            video.mode, video.level, video.row, video.column, video.mine_num,
            video.rtime, video.bbbv, board.cell1, board.cell2, board.cell3, board.cell4, board.cell5,
            board.cell6, board.cell7, board.cell8, board.op, board.isl, video.ioe, video.rce == 0
        )

    def _calc_xp_base(
        self,
        mode: int, level: int, row: int, column: int, mine_num: int,
        rtime: float, bbbv: int, cell1, cell2, cell3, cell4, cell5,
        cell6: int, cell7: int, cell8: int, op: int, isl: int, ioe: float, nf: bool
    ) -> int:
        # ---- 基本经验 ----
        k = _MODE_K.get(mode, 0.0)
        cells = row * column
        long_side = max(row, column)
        short_side = min(row, column)
        if mine_num / cells <= 0.8 and mode in (0, 4, 7) or mine_num / cells <= 0.3 and mode in (5, 6):
            exp_b = k * (1.08 ** (mine_num / cells * 341.0)) * short_side ** 1.2 * long_side ** 1.6 / 17411.0
        else:
            exp_b = 0

        exp_r = 0.0
        exp_t = 0.0
        exp_e = 0.0

        # ---- 稀有局面 & 竞速（仅标准模式·标准难度） ----
        if mode == 0 and level in (3, 4, 5):
            prefix = _DIST_PREFIX[level]

            # 稀有局面
            rare_sum = 0.0
            for field, val in (
                ('bbbv', bbbv), ('op', op), ('isl', isl), ('cell1', cell1), ('cell2', cell2), ('cell3', cell3), ('cell4', cell4), ('cell5', cell5),
                ('cell6', cell6), ('cell7', cell7), ('cell8', cell8),
            ):
                p = _cum_prob(prefix, field, val)
                if 0 <= p <= 1.0:
                    p = max(p, 0.00000001)
                    rare_sum += (0.5 / p) ** 1.2
            exp_r = (cells / 100.0) * rare_sum
            if level == 3:
                exp_r = rare_sum / 100.0
            elif level == 4:
                exp_r = rare_sum / 8.0
            elif level == 5:
                exp_r = rare_sum

            # 竞速
            if level == 3:
                exp_t = (1.0 / 100.0) * ((10.0 / rtime) ** 3.5)
            elif level == 4:
                exp_t = (1.0 / 8.0) * ((60.0 / rtime) ** 3.5)
            elif level == 5:
                exp_t = (240.0 / rtime) ** 3.5

            # 效率经验
            if level == 3:
                if ioe >= 0.95:
                    exp_e = ioe ** 3.5
            elif level == 4:
                if ioe >= 0.9:
                    if nf:
                        exp_e = 20 * ioe ** 5
                    else:
                        exp_e = 10 * ioe ** 4
            elif level == 5:
                if ioe >= 0.8:
                    if nf:
                        exp_e = 1200 * ioe ** 50
                    else:
                        exp_e = 1 * ioe ** 20


        total = int(exp_b + exp_r + exp_t + exp_e)
        total = min(total, 99999)  # 上限经验值，防止极端局面
        # self.logger.info(f"经验计算: 基础 {exp_b:.2f} + 稀有 {exp_r:.2f} + 竞速 {exp_t:.2f} = {total}")
        
        return total

    # ═══════════════════════════════════════════════════════════
    # 数据管理
    # ═══════════════════════════════════════════════════════════

    def _load_data(self):
        path = self.data_dir / "player_data.dat"
        if path.exists():
            try:
                raw = _decrypt(path.read_bytes())
                data = json.loads(raw)
                if "identifiers" in data and "players" in data:
                    self._identifiers = data["identifiers"]
                    self._players = data["players"]
                    self._history = data.get("history", [])
                    self._current_pid = data.get("current_pid", 0)
                    self._imported = set(tuple(v) for v in data.get("imported_videos", []))
                    self.logger.info(f"已加载存档，{len(self._identifiers)} 个玩家")
                    return
                self.logger.info("旧存档格式，忽略")
            except Exception as e:
                self.logger.warning(f"读取存档失败: {e}")

        self._identifiers = []
        self._players = []
        self._history = []
        self._current_pid = 0
        self._imported: set[tuple[str, str]] = set()

    def _save_data(self):
        path = self.data_dir / "player_data.dat"
        data = {
            "identifiers": self._identifiers,
            "players": self._players,
            "history": self._history,
            "current_pid": self._current_pid,
            "imported_videos": [list(v) for v in self._imported],
        }
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        path.write_bytes(_encrypt(raw))

    def _get_or_create_pid(self, identifier: str) -> int:
        identifier = identifier.strip()
        if not identifier:
            identifier = _translate("Form", "匿名玩家")
        try:
            return self._identifiers.index(identifier)
        except ValueError:
            pid = len(self._identifiers)
            self._identifiers.append(identifier)
            self._players.append({"level": 0, "xp": 0})
            return pid

    # ═══════════════════════════════════════════════════════════
    # 吸收灵气（导入其他版本录像获得经验）
    # ═══════════════════════════════════════════════════════════

    def validate_replays(self, exe_path: str, replay_path: str) -> dict | None:
        """校验录像并返回预览数据，失败返回 None"""
        try:
            exe = Path(exe_path)
            if not exe.exists():
                self.logger.error(f"校验程序不存在: {exe_path}")
                return None

            actual_md5 = hashlib.md5(exe.read_bytes()).hexdigest()

            match actual_md5:
                case "3271d11bab9afc8b0a2b9546e13d46cd":
                    return self._validate_metasweeper_3_2_2(exe, replay_path)
                case _:
                    self.logger.error(f"未知法器 MD5: {actual_md5}")
                    return None
        except Exception as e:
            self.logger.error(f"校验失败: {e}")
            return None

    def _validate_metasweeper_3_2_2(self, exe: Path, replay_path: str) -> dict | None:
        """元扫雷 3.2.2 的录像校验与解析"""
        try:
            cmd = [str(exe), "-c", replay_path]
            self.logger.info(f"执行: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode != 0:
                self.logger.error(f"校验程序返回非零: {result.returncode}")
                return None

            out_path = exe.parent / "_internal" / "out.json"
            if not out_path.exists():
                self.logger.error(f"未找到结果文件: {out_path}")
                return None

            report = json.loads(out_path.read_bytes())
            if report.get("error"):
                self.logger.error(f"校验报告错误: {report['error']}")
                return None

            new_files = []
            dup_files = []
            for d in report.get("data", []):
                if d.get("status") != 0:
                    continue
                fp = d["file"]
                try:
                    v = ms.EvfVideo(fp)
                    v.parse()
                    v.analyse()
                    key = (str(v.start_time), v.player_identifier)
                    entry = {
                        "file": fp,
                        "player": v.player_identifier,
                        "start_time": v.start_time,
                        "level": getattr(v, "level", 3),
                        "mode": getattr(v, "mode", 0),
                        "rtime": getattr(v, "rtime", 0.0),
                        "bbbv": getattr(v, "bbbv", 0),
                        "xp": self._calc_xp2(v),
                    }
                    if key in self._imported:
                        dup_files.append(entry)
                    elif entry["xp"] > 0:
                        new_files.append(entry)
                except Exception as e:
                    self.logger.warning(f"解析录像失败 {fp}: {e}")

            return {
                "md5": "3271d11bab9afc8b0a2b9546e13d46cd",
                "new_files": new_files,
                "duplicates": dup_files,
                "total_new_xp": sum(n["xp"] for n in new_files),
            }
        except Exception as e:
            self.logger.error(f"元扫雷 3.2.2 校验失败: {e}")
            return None

    def absorb_replays(self, preview: dict) -> int:
        """根据预览数据实际吸收经验，返回获得的总经验"""
        gained_total = 0

        for entry in preview["new_files"]:
            xp_per = entry.get("xp", 0)
            key = (str(entry["start_time"]), entry["player"])
            self._imported.add(key)

            pid = self._get_or_create_pid(entry["player"])
            self._current_pid = pid
            player = self._players[pid]
            player["xp"] += xp_per
            gained_total += xp_per

            while player["level"] < 100:
                need = _total_xp(player["level"] + 1)
                if player["xp"] < need:
                    break
                player["level"] += 1

            top = _total_xp(100)
            if player["xp"] > top:
                player["xp"] = top

            self._history.append({
                "pid": pid,
                "time": int(datetime.now().timestamp()),
                "level": entry["level"],
                "mode": entry["mode"],
                "rtime": round(entry["rtime"], 2),
                "bbbv": entry["bbbv"],
                "xp": xp_per,
            })

        if len(self._history) > 1000:
            self._history = self._history[-1000:]

        self._save_data()
        self._push_ui_update()
        return gained_total

    # ═══════════════════════════════════════════════════════════
    # 导入道行存档（3.3.1+ 版本之间跨版本累计）
    # ═══════════════════════════════════════════════════════════

    def validate_save(self, dir_path: str) -> dict | None:
        """递归搜索 player_data.dat，解析并去重后返回预览"""
        files = list(Path(dir_path).rglob("player_data.dat"))
        if not files:
            return None

        parsed = []
        for fp in files:
            try:
                raw = _decrypt(fp.read_bytes())
                data = json.loads(raw)
                if "identifiers" in data and "players" in data:
                    parsed.append(data)
            except Exception:
                continue

        if not parsed:
            return None

        # 跨文件去重：同一 identifier 取最高经验
        merged: dict[str, int] = {}
        for data in parsed:
            for identifier, player in zip(data["identifiers"], data["players"]):
                xp = player["xp"]
                if identifier not in merged or xp > merged[identifier]:
                    merged[identifier] = xp

        return {
            "files": parsed,
            "preview": {
                "players": [{"identifier": k, "xp": v} for k, v in merged.items()],
                "total_xp": sum(merged.values()),
                "total_players": len(merged),
            },
        }

    def absorb_save(self, preview: dict) -> int:
        """合并预览中的存档数据到当前玩家"""
        # 第一步：跨文件去重，每个 identifier 取最高经验
        merged: dict[str, int] = {}
        for data in preview["files"]:
            for identifier, player in zip(data["identifiers"], data["players"]):
                xp = player["xp"]
                if identifier not in merged or xp > merged[identifier]:
                    merged[identifier] = xp

        gained_total = 0

        # 第二步：合并玩家经验
        for identifier, import_xp in merged.items():
            pid = self._get_or_create_pid(identifier)
            player = self._players[pid]
            if import_xp > player["xp"]:
                added = import_xp - player["xp"]
                player["xp"] = import_xp
                gained_total += added

            while player["level"] < 100:
                need = _total_xp(player["level"] + 1)
                if player["xp"] < need:
                    break
                player["level"] += 1

            top = _total_xp(100)
            if player["xp"] > top:
                player["xp"] = top

        # 第三步：合并修行日志（按新 pid + 时间去重）
        existing_keys = set((h["pid"], h["time"]) for h in self._history)
        old_idents = []
        old_histories = []
        for data in preview["files"]:
            old_idents.append(data.get("identifiers", []))
            old_histories.append(data.get("history", []))

        for idents, history in zip(old_idents, old_histories):
            for h in history:
                old_pid = h.get("pid", 0)
                identifier = idents[old_pid] if 0 <= old_pid < len(idents) else None
                if identifier is None:
                    continue
                try:
                    new_pid = self._identifiers.index(identifier)
                except ValueError:
                    continue
                key = (new_pid, h["time"])
                if key not in existing_keys:
                    entry = dict(h)
                    entry["pid"] = new_pid
                    self._history.append(entry)
                    existing_keys.add(key)

        if len(self._history) > 1000:
            self._history.sort(key=lambda x: x["time"])
            self._history = self._history[-1000:]

        # 第四步：合并已导入录像集
        for data in preview["files"]:
            self._imported.update(tuple(v) for v in data.get("imported_videos", []))

        self._save_data()
        self._push_ui_update()
        return gained_total

    def _build_update_data(self) -> dict:
        if not self._players:
            return {
                "player_name": "",
                "level": 0,
                "total_xp": 0,
                "xp_curr": 0,
                "xp_need": _total_xp(1),
                "image_index": get_image_index(0),
                "history": [],
            }
        pid = self._current_pid
        if pid >= len(self._players):
            pid = 0
            self._current_pid = 0
        player = self._players[pid]
        level = player["level"]
        xp = player["xp"]
        xp_base = _total_xp(level)
        xp_next = _total_xp(level + 1) if level < 100 else _total_xp(100)
        return {
            "player_name": self._identifiers[pid] if self._identifiers else "",
            "level": level,
            "total_xp": xp,
            "xp_curr": xp - xp_base,
            "xp_need": xp_next - xp_base,
            "image_index": get_image_index(level),
            "history": self._history[::-1][:100],
        }

    # ═══════════════════════════════════════════════════════════
    # 上传排行（仅当前 identifier 的 level + total_xp）
    # ═══════════════════════════════════════════════════════════

    def upload_ranking(self) -> None:
        """由「上传排行」按钮回调。不受 60 秒客户端跳过限制。"""
        if getattr(self, "_upload_in_progress", False):
            ui = getattr(self, "_ui", None)
            if ui is not None:
                ui.set_upload_enabled(True)
            return
        self._start_upload(silent=False, bypass_throttle=True)

    def _maybe_auto_upload(self) -> None:
        """胜利后静默上传；匿名标识直接跳过。"""
        if not self.other_info or not self.other_info.auto_upload:
            self._pending_upload = False
            return
        identifier = self._current_identifier()
        if self._is_anonymous_identifier(identifier):
            self.logger.info("自动上传跳过：当前仍是默认匿名标识")
            self._pending_upload = False
            return
        if getattr(self, "_upload_in_progress", False):
            self._pending_upload = True
            return
        if not self._throttle_allows_upload():
            self._pending_upload = True
            self._start_pending_timer()
            return
        self._start_upload(silent=True, bypass_throttle=False)

    def _throttle_allows_upload(self) -> bool:
        last = getattr(self, "_last_upload_attempt", 0.0)
        if last <= 0:
            return True
        elapsed = time.monotonic() - last
        return elapsed >= self._auto_upload_interval()

    def _auto_upload_interval(self) -> float:
        fails = getattr(self, "_auto_upload_fail_count", 0)
        interval = _AUTO_UPLOAD_MIN_INTERVAL_SEC * (2 ** min(max(fails, 0), 3))
        return float(min(interval, _AUTO_UPLOAD_MAX_INTERVAL_SEC))

    def _start_pending_timer(self) -> None:
        if not getattr(self, "_pending_upload", False):
            return
        timer = getattr(self, "_pending_timer", None)
        if timer is None or timer.isActive():
            return
        last = getattr(self, "_last_upload_attempt", 0.0)
        elapsed = time.monotonic() - last if last > 0 else self._auto_upload_interval()
        remaining_ms = max(0, int((self._auto_upload_interval() - elapsed) * 1000))
        timer.start(remaining_ms)

    def _on_pending_upload_timeout(self) -> None:
        if not getattr(self, "_pending_upload", False):
            return
        self._pending_upload = False
        self._maybe_auto_upload()

    def _start_upload(self, *, silent: bool, bypass_throttle: bool) -> None:
        """准备 payload 并在后台线程 POST。silent 时成功不弹窗、不打开浏览器。"""
        if getattr(self, "_upload_in_progress", False):
            if not silent:
                ui = getattr(self, "_ui", None)
                if ui is not None:
                    self.run_on_gui(ui.set_upload_enabled, True)
            else:
                self._pending_upload = True
            return
        if not bypass_throttle and not self._throttle_allows_upload():
            self._pending_upload = True
            self._start_pending_timer()
            return

        self._upload_in_progress = True
        try:
            data = self._build_update_data()
            identifier = (data.get("player_name") or "").strip()
            if self._is_anonymous_identifier(identifier):
                if silent:
                    self.logger.info("自动上传跳过：当前仍是默认匿名标识")
                    self._upload_in_progress = False
                    return
                self.run_on_gui(
                    self._show_upload_result,
                    False,
                    _translate(
                        "Form",
                        "当前玩家标识为空或仍是默认「匿名玩家」，无法上传排行。请先在游戏设置中修改玩家标识。",
                    ),
                    False,
                )
                return

            api_url = ""
            token = ""
            if self.other_info:
                api_url = resolve_api_url(self.other_info.api_url or "")
                token = (self.other_info.upload_token or "").strip()
            else:
                api_url = DEFAULT_API_URL

            display_name = self._resolve_rank_display_name(identifier)

            transport_error = api_url_transport_error(api_url)
            if transport_error:
                if silent:
                    self.logger.warning(f"自动上传跳过：{transport_error}")
                    self._upload_in_progress = False
                    return
                self.run_on_gui(
                    self._show_upload_result,
                    False,
                    transport_error,
                    False,
                )
                return

            if not token:
                token = secrets.token_urlsafe(32)
                if self.other_info:
                    self.other_info.upload_token = token
                    self.save_config()
                    self.logger.info("已生成并保存上传令牌")

            payload = {
                "identifier": identifier,
                "level": int(data["level"]),
                "total_xp": int(data["total_xp"]),
                "plugin_version": self.info.version,
                "upload_token": token,
                "display_name": display_name,
            }
            self.logger.info(
                f"准备上传排行: identifier={identifier!r} display_name={display_name!r} "
                f"level={payload['level']} total_xp={payload['total_xp']} "
                f"plugin_version={payload['plugin_version']} silent={silent}"
            )

            self._last_upload_attempt = time.monotonic()
            thread = threading.Thread(
                target=self._upload_ranking_worker,
                args=(api_url, payload, silent),
                daemon=True,
                name="xianni-upload",
            )
            thread.start()
        except Exception as e:
            self.logger.error(f"准备上传排行失败: {e}", exc_info=True)
            if silent:
                self._upload_in_progress = False
                self._auto_upload_fail_count = getattr(self, "_auto_upload_fail_count", 0) + 1
                self._schedule_pending_after_result()
                return
            self.run_on_gui(
                self._show_upload_result,
                False,
                _translate("Form", "上传失败: %1").replace("%1", str(e)),
                False,
            )

    def _upload_ranking_worker(self, api_url: str, payload: dict, silent: bool = False) -> None:
        """在后台线程执行 HTTP POST，禁止操作 GUI 控件。"""
        transport_error = api_url_transport_error(api_url)
        if transport_error:
            self.run_on_gui(
                self._show_upload_result, False, transport_error, silent
            )
            return
        url = api_url.rstrip("/") + "/api/upload"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                # urllib 默认 UA 会被 Cloudflare 1010 拦截，表现为假的 403
                "User-Agent": f"MetaSweeper-XianNiUpgrade/{self.info.version}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=_UPLOAD_TIMEOUT_SEC) as resp:
                status = getattr(resp, "status", 200)
                if 200 <= int(status) < 300:
                    self.logger.info("排行上传成功")
                    self.run_on_gui(
                        self._show_upload_result,
                        True,
                        _translate("Form", "排行已上传。"),
                        silent,
                    )
                    return
                self.logger.warning(f"排行上传返回异常状态: {status}")
                self.run_on_gui(
                    self._show_upload_result,
                    False,
                    _translate("Form", "上传失败（HTTP %1）").replace("%1", str(status)),
                    silent,
                )
        except urllib.error.HTTPError as e:
            raw = b""
            try:
                raw = e.read() or b""
            except Exception:
                raw = b""
            text = raw.decode("utf-8", errors="replace")
            self.logger.warning(f"排行上传被拒绝: HTTP {e.code} {text[:500]}")
            self.run_on_gui(
                self._show_upload_result,
                False,
                self._format_upload_http_error(e.code, text),
                silent,
            )
        except urllib.error.URLError as e:
            reason = e.reason
            timed_out = isinstance(reason, TimeoutError) or (
                isinstance(reason, OSError) and "timed out" in str(reason).lower()
            )
            if timed_out:
                self.logger.warning("排行上传超时")
                msg = _translate("Form", "上传超时，请检查网络或排行站地址。")
            else:
                self.logger.warning(f"排行上传无法连接: {reason}")
                msg = _translate("Form", "无法连接排行站，请检查网络或 API 地址。")
            self.run_on_gui(self._show_upload_result, False, msg, silent)
        except TimeoutError:
            self.logger.warning("排行上传超时")
            self.run_on_gui(
                self._show_upload_result,
                False,
                _translate("Form", "上传超时，请检查网络或排行站地址。"),
                silent,
            )
        except Exception as e:
            self.logger.error(f"排行上传异常: {e}", exc_info=True)
            self.run_on_gui(
                self._show_upload_result,
                False,
                _translate("Form", "上传失败: %1").replace("%1", str(e)),
                silent,
            )

    @staticmethod
    def _format_upload_http_error(code: int, body: str = "") -> str:
        err = ""
        if body:
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    err = str(parsed.get("error") or parsed.get("detail") or "")
                    if parsed.get("error_code") == 1010 or parsed.get("error_name") == "browser_signature_banned":
                        return _translate(
                            "Form",
                            "排行站 Cloudflare 拦截了上传（1010）。请在 Pages 项目关闭 Bot Fight Mode 后重试。",
                        )
            except Exception:
                err = ""
        if code == 403:
            if "令牌" in err or "token" in err.lower():
                return _translate(
                    "Form",
                    "令牌不匹配，无法更新该标识。请确认上传令牌，或更换玩家标识后重试。",
                )
            if err:
                return _translate("Form", "上传被拒绝：%1").replace("%1", err)
            return _translate(
                "Form",
                "令牌不匹配，无法更新该标识。请确认上传令牌，或更换玩家标识后重试。",
            )
        if code == 429:
            return _translate("Form", "上传过于频繁，请稍后再试。")
        if code == 400:
            if err:
                return _translate("Form", "服务器拒绝了本次数据：%1").replace("%1", err)
            return _translate("Form", "服务器拒绝了本次数据（校验失败）。")
        return _translate("Form", "上传失败（HTTP %1）").replace("%1", str(code))

    def _schedule_pending_after_result(self) -> None:
        if getattr(self, "_pending_upload", False):
            self._schedule_pending.emit()

    def _show_upload_result(self, success: bool, message: str, silent: bool = False) -> None:
        """在 GUI 线程展示结果并恢复按钮。silent 时只记日志。"""
        self._upload_in_progress = False
        if success:
            self._auto_upload_fail_count = 0
        elif silent:
            self._auto_upload_fail_count = getattr(self, "_auto_upload_fail_count", 0) + 1
        self._schedule_pending_after_result()

        if silent:
            if success:
                self.logger.info("自动上传成功")
            else:
                self.logger.warning(f"自动上传失败: {message}")
            return

        parent = getattr(self, "_ui", None)
        try:
            if success:
                QMessageBox.information(
                    parent, _translate("Form", "上传排行"), message
                )
                self._maybe_open_site()
            else:
                QMessageBox.warning(
                    parent, _translate("Form", "上传排行"), message
                )
        finally:
            if parent is not None:
                parent.set_upload_enabled(True)

    def _maybe_open_site(self) -> None:
        if not self.other_info or not self.other_info.open_site_after_upload:
            return
        url = (self.other_info.api_url or "").strip().rstrip("/")
        if not url:
            return
        try:
            webbrowser.open(url)
        except Exception as e:
            self.logger.warning(f"打开排行页失败: {e}")

    def _on_game_finished(self, event: GameFinishedEvent):
        # self.logger.info(event.game_state)
        # self.logger.info(event)
        if event.game_state != 6 or not event.is_fair:
            return

        pid = self._get_or_create_pid(event.player_identifier)
        self._current_pid = pid
        player = self._players[pid]

        xp_gained = self._calc_xp(event)

        if xp_gained > 0:
            player["xp"] += xp_gained

            while player["level"] < 100:
                need = _total_xp(player["level"] + 1)
                if player["xp"] < need:
                    break
                player["level"] += 1

            top = _total_xp(100)
            if player["xp"] > top:
                player["xp"] = top

            self._history.append({
                "pid": pid,
                "time": int(datetime.now().timestamp()),
                "level": event.level,
                "mode": event.mode,
                "rtime": round(event.rtime, 2),
                "bbbv": event.bbbv,
                "xp": xp_gained,
            })

            if len(self._history) > 1000:
                self._history = self._history[-1000:]

            self._save_data()
            self._push_ui_update()

        self._maybe_auto_upload()

    def _on_close(self, event: CloseEvent):
        self._save_data()

    def _on_language_change(self, event: LanguageChangeEvent) -> None:
        self.run_on_gui(self._ui.retranslateUi)
        self._push_ui_update()

    def _push_ui_update(self):
        self._ui._signal_update.emit(self._build_update_data())

    def _resolve_rank_display_name(self, identifier: str) -> str:
        key = (identifier or "").strip()
        if not key:
            return ""
        service = getattr(self, "_saolei_service", None)
        if service is None:
            service = self.wait_for_service(SaoleiWebsiteService, timeout=2.0)
            if service is not None:
                self._saolei_service = service
        if service is None:
            self.logger.warning("SaoleiWebsiteService 不可用，排行昵称回退为游戏标识")
            return key
        try:
            return service.get_rank_display_name(key)
        except Exception as e:
            self.logger.warning(f"解析开源扫雷网昵称失败，回退为游戏标识: {e}")
            return key

    def _maybe_show_rules_dialog(self) -> None:
        """Tab 首次可见时弹出一次天地法则（经 run_on_gui 投递到 GUI 线程）。"""
        if not self.other_info or self.other_info.rules_dialog_seen:
            return
        if getattr(self, "_guide_dialog_open", False):
            return
        self.run_on_gui(self._show_rules_dialog)

    def _show_rules_dialog(self) -> None:
        """在 GUI 主线程执行模态天地法则；勿在 showEvent 调用栈内同步 exec_()。"""
        if not self.other_info or self.other_info.rules_dialog_seen:
            return
        if getattr(self, "_guide_dialog_open", False):
            return
        ui = getattr(self, "_ui", None)
        if ui is None or not ui.isVisible():
            return
        self._guide_dialog_open = True
        try:
            RulesDialog(parent=ui).exec_()
            self.other_info.rules_dialog_seen = True
            self.save_config()
        finally:
            self._guide_dialog_open = False




