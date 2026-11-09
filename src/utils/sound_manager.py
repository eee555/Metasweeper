"""
游戏音效管理器（内建，纯表现层）。

设计要点
────────
* 单例，用法与 `GameServerBridge.instance()` 一致：`SoundManager.instance().play(...)`。
* 后端为 `PySide6.QtMultimedia.QSoundEffect`：短音效、预加载、低延迟。
* 快速连点：同一 cue 采用「打断重启」（`stop()` → `play()`），每次真实点击
  都有反馈且不会叠成糊音；18ms 内的重复调用视为同一物理动作的衍生事件而丢弃；
  结局音独占、清场；同时发声的不同 cue 最多 2 个。
* 强度分层：`intensity`（本次开格/标旗数量）映射到音量增益，不额外增加素材。
* 音效包：与 skin_manager 同构 —— 一个子目录就是一个包，`sound.json` 提供显示名，
  缺哪个 wav 就沿用 `media/sounds/` 根目录下的默认资源，切换即时生效、不重启。
* 任何异常（无音频设备、文件缺失、后端未就绪）都静默降级，绝不影响对局与录像。

预留接口（后续放给插件 / 音效包）
──────────────────────────────
* `register_sound(event, path)` / `unregister_sound(event)`：外部替换单个 cue 的素材。
* `set_pack(name)` / `discover_choices()`：外部枚举并切换音效包。
* 插件进程接入时，只需在 `shared_types/commands.py` 加一个
  `SetSoundPackCommand`（或 `PlaySoundCommand`），在主进程 handler 里转调
  `instance().set_pack(...)` / `instance().play(...)` 即可，无需改动任何游戏逻辑文件。
"""
from __future__ import annotations

import json
import time
from enum import Enum
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import QApplication

from utils.app_logger import logger
from utils.path_utils import resource_path


# ── 事件与素材映射 ────────────────────────────────────────────────
class SoundEvent(Enum):
    """游戏性音效事件。新增值只需在此登记 + 放同名 wav，调用点无需改动。"""

    READY = "ready"          # 程序启动、主窗口就绪
    START = "start"          # 第一次有效左键抬起，埋雷完成
    OPEN = "open"            # 单击开格
    CHORD = "chord"          # 双击（chording）展开
    FLAG_ON = "flag_on"      # 插旗
    FLAG_OFF = "flag_off"    # 拔旗 / 取消标记
    QUESTION = "question"    # 问号（当前配置禁用问号，恒不触发；预留）
    WIN = "win"              # 胜利
    LOSE = "lose"            # 踩雷 / 失败


# 事件 -> 固定文件名。与 skin_manager.skins.CELL_FILES 同一套路。
SOUND_FILES: dict[SoundEvent, str] = {
    event: f"{event.value}.wav" for event in SoundEvent
}

# 同一 tick 内多个 cue 只播优先级最高的一个（由反馈层使用）。
SOUND_PRIORITY: dict[SoundEvent, int] = {
    SoundEvent.WIN: 100,
    SoundEvent.LOSE: 100,
    SoundEvent.READY: 90,
    SoundEvent.START: 80,
    SoundEvent.CHORD: 60,
    SoundEvent.OPEN: 40,
    SoundEvent.FLAG_ON: 20,
    SoundEvent.FLAG_OFF: 20,
    SoundEvent.QUESTION: 10,
}

_EXCLUSIVE_EVENTS = frozenset({SoundEvent.WIN, SoundEvent.LOSE})

# ── 音效包 ────────────────────────────────────────────────────────
DEFAULT_PACK = ""                       # 空串 = 使用根目录默认音效
DEFAULT_PACK_LABEL = "默认音效（不替换）"
SOUND_META_FILE = "sound.json"
BUILTIN_SOUNDS_DIR: Path = resource_path("media") / "sounds"

# ── 快速连点参数（表现层审美常量，集中调参）────────────────────────
DEDUP_WINDOW_MS = 18        # 同一 cue 在此窗口内重复调用视为同一动作，丢弃
MERGE_WINDOW_MS = 40        # 并发上限的统计窗口
EXCLUSIVE_WINDOW_MS = 180   # 结局音独占时长，期间压掉其他 cue
MAX_VOICES = 2              # 同时发声的不同 cue 上限


def list_sound_packs(root: Path | str | None) -> list[tuple[str, str]]:
    """扫描音效包目录，返回 [(目录名, 显示名), ...]，按目录名排序。

    跳过 `_` 开头的目录（与 `skin_manager.skins.list_skins` 一致），
    `sound.json` 里的 `name` 作为显示名，读不到就用目录名。
    """
    if root is None:
        return []
    root = Path(root)
    if not root.is_dir():
        return []
    result: list[tuple[str, str]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        display = child.name
        meta = child / SOUND_META_FILE
        if meta.is_file():
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                display = str(data.get("name") or child.name)
            except (OSError, ValueError, TypeError):
                pass
        result.append((child.name, display))
    return result


def discover_choices(extra_dir: Path | str | None = None) -> list[tuple[str, str]]:
    """返回设置页下拉框选项 `[(值, 显示名), ...]`。

    自带音效库与用户「额外音效库目录」合并，同名以自带库为准；
    首个选项固定为「默认音效」。新增包目录即自动出现，无需改 Python 代码。
    """
    choices: dict[str, str] = dict(list_sound_packs(BUILTIN_SOUNDS_DIR))
    if extra_dir:
        extra = Path(str(extra_dir).strip())
        for name, display in list_sound_packs(extra):
            choices.setdefault(name, display)
    return [
        (DEFAULT_PACK, DEFAULT_PACK_LABEL),
        *[(name, choices[name]) for name in sorted(choices)],
    ]


class _Voice:
    """单个 cue 的常驻 QSoundEffect，负责预加载门控与打断重启。"""

    def __init__(self) -> None:
        self.effect = QSoundEffect()
        # `loadedChanged` 在部分 Qt 版本/后端不触发，导致 `_ready` 永远为 False。
        # 改用 statusChanged，并在 play() 时即时读 status 做双重保险。
        self.effect.statusChanged.connect(self._on_status)
        self._path: Path | None = None
        self._valid = False
        self._ready = False
        self._pending_gain: float | None = None

    def set_source(self, path: Path) -> None:
        if self._path == path:
            return
        self._path = path
        self._pending_gain = None
        self._valid = path.is_file()
        self._ready = False
        if not self._valid:
            # 缺文件即静默降级（沿用默认资源由 resolve() 保证，这里只是兜底）
            try:
                self.effect.setSource(QUrl())
            except Exception:
                pass
            return
        try:
            self.effect.setSource(QUrl.fromLocalFile(str(path)))
            self._ready = self.effect.status() == QSoundEffect.Status.Ready
        except Exception as exc:
            logger.warning(f"音效加载失败 {path}: {exc}")
            self._valid = False

    def _on_status(self) -> None:
        try:
            self._ready = self.effect.status() == QSoundEffect.Status.Ready
        except Exception:
            self._ready = False
        if self._ready and self._pending_gain is not None:
            gain, self._pending_gain = self._pending_gain, None
            self._fire(gain)

    def play(self, gain: float) -> None:
        if not self._valid:
            return
        # 即时检查：setSource 可能已经异步加载完毕，但信号未送达。
        if not self._ready:
            try:
                self._ready = self.effect.status() == QSoundEffect.Status.Ready
            except Exception:
                self._ready = False
        if not self._ready:
            # 未就绪时排队，statusChanged 后补播，保证开局第一击不哑。
            self._pending_gain = gain
            return
        self._fire(gain)

    def _fire(self, gain: float) -> None:
        try:
            self.effect.setVolume(max(0.0, min(1.0, gain)))
            self.effect.stop()   # 打断上一段，快速连点不叠音
            self.effect.play()
        except Exception as exc:
            logger.warning(f"音效播放失败: {exc}")

    def stop(self) -> None:
        try:
            self.effect.stop()
        except Exception:
            pass


class SoundManager:
    """音效单例。所有公开方法在音频不可用时都安全静默。"""

    _instance: "SoundManager | None" = None

    def __init__(self) -> None:
        self._enabled = False                    # 默认静音，由设置项显式开启
        self._volume = 0.7                       # 0.0 ~ 1.0
        self._pack = DEFAULT_PACK
        self._extra_dir: Path | None = None
        self._overrides: dict[SoundEvent, Path] = {}
        self._voices: dict[SoundEvent, _Voice] = {}
        self._last_play: dict[SoundEvent, float] = {}
        self._exclusive_until = 0.0
        self._recent: list[tuple[float, SoundEvent]] = []

    @classmethod
    def instance(cls) -> "SoundManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── 配置 ──────────────────────────────────────────────────────
    def configure(
        self,
        enabled: bool = False,
        volume: int = 70,
        pack: str = DEFAULT_PACK,
        extra_dir: Path | str | None = None,
    ) -> None:
        """由 `gameSetting.ini` 的设置项驱动，支持运行时热更新。"""
        self._enabled = bool(enabled)
        self._volume = max(0.0, min(1.0, float(volume) / 100.0))
        self._pack = pack or DEFAULT_PACK
        self._extra_dir = Path(extra_dir) if extra_dir else None
        if not self._enabled:
            self.stop_all()
        self._ensure_voices()
        self._rebuild()

    def set_pack(self, name: str) -> None:
        """切换音效包（公开 API，供后续插件 / 音效包调用）。"""
        self.configure(
            enabled=self._enabled,
            volume=int(self._volume * 100),
            pack=name,
            extra_dir=str(self._extra_dir) if self._extra_dir else None,
        )

    def register_sound(self, event: SoundEvent, path: Path | str) -> None:
        """覆盖单个 cue 的素材路径（公开 API）。传不存在的文件即静音该 cue。"""
        self._overrides[event] = Path(path)
        self._ensure_voices()
        self._rebuild()

    def unregister_sound(self, event: SoundEvent) -> None:
        """撤销 `register_sound`，恢复为当前音效包的资源。"""
        self._overrides.pop(event, None)
        self._rebuild()

    def current_pack(self) -> str:
        return self._pack

    def play_ready(self, delay_ms: int = 350) -> None:
        """程序启动就绪音。

        启动时音频后端 / 预加载可能尚未完成，故延迟一小段时间再播；
        未就绪时 `play()` 内部会排队补播。纯表现层，异常一律静默。
        """
        if not self._enabled or self._volume <= 0:
            return
        try:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(max(0, delay_ms), lambda: self.play(SoundEvent.READY))
        except Exception:
            logger.warning("启动音播放失败，已静默", exc_info=True)

    # ── 播放 ──────────────────────────────────────────────────────
    def play(self, event: SoundEvent, *, intensity: int = 1) -> None:
        """播放一个 cue。

        `intensity` 为本次操作影响到的格子数，映射到音量增益（不额外加载素材）。
        """
        if not self._enabled or self._volume <= 0:
            return
        if not self._ensure_voices():
            return
        now = time.monotonic()

        # 结局音独占：踩雷/获胜时清场，且短时间内的其他 cue 全部压掉。
        if event not in _EXCLUSIVE_EVENTS and now < self._exclusive_until:
            return
        if event in _EXCLUSIVE_EVENTS:
            self._exclusive_until = now + EXCLUSIVE_WINDOW_MS / 1000.0
            self.stop_all(except_event=event)

        # 极短去重：只挡「同一物理动作衍生的重复事件」，不误伤 80ms+ 的连点。
        last = self._last_play.get(event)
        if last is not None and (now - last) * 1000.0 < DEDUP_WINDOW_MS:
            return

        voice = self._voices.get(event)
        if voice is None:
            return
        try:
            level = max(1, int(intensity))
        except (TypeError, ValueError):
            level = 1
        # 基础增益抬高到 0.75：占位音效原先素材振幅偏小，叠加 0.55 基数后
        # 实际响度不足满量程的 10%，在系统音量不高时几乎听不见。
        gain = self._volume * min(1.0, 0.75 + 0.06 * level)
        voice.play(gain)                 # 同 cue 打断重启
        self._last_play[event] = now
        self._limit_voices(now, event)

    def stop_all(self, *, except_event: SoundEvent | None = None) -> None:
        for event, voice in self._voices.items():
            if event != except_event:
                voice.stop()
        if except_event is None:
            self._exclusive_until = 0.0
            self._last_play.clear()
            self._recent.clear()

    # ── 内部 ──────────────────────────────────────────────────────
    def _ensure_voices(self) -> bool:
        """懒初始化：QSoundEffect 必须在 QApplication 存在后创建。"""
        if self._voices:
            return True
        if QApplication.instance() is None:
            return False
        try:
            self._voices = {event: _Voice() for event in SoundEvent}
            return True
        except Exception as exc:
            logger.warning(f"音效后端初始化失败，已静音: {exc}")
            return False

    def _rebuild(self) -> None:
        if not self._voices:
            return
        for event in SoundEvent:
            self._voices[event].set_source(self.resolve(event))

    def _pack_roots(self) -> Iterable[Path]:
        roots = [BUILTIN_SOUNDS_DIR]
        if self._extra_dir and self._extra_dir.is_dir():
            roots.append(self._extra_dir)
        return roots

    def resolve(self, event: SoundEvent) -> Path:
        """按「外部注册 > 当前音效包 > 根目录默认」解析素材路径。

        与皮肤「缺哪个文件就沿用默认资源」完全一致。
        """
        override = self._overrides.get(event)
        if override is not None:
            return override
        if self._pack:
            for root in self._pack_roots():
                candidate = root / self._pack / SOUND_FILES[event]
                if candidate.is_file():
                    return candidate
        return BUILTIN_SOUNDS_DIR / SOUND_FILES[event]

    def _limit_voices(self, now: float, current: SoundEvent) -> None:
        self._recent = [
            (t, e) for t, e in self._recent
            if (now - t) * 1000.0 < MERGE_WINDOW_MS
        ]
        self._recent.append((now, current))
        distinct: list[SoundEvent] = []
        for _, event in self._recent:
            if event not in distinct:
                distinct.append(event)
        if len(distinct) > MAX_VOICES:
            for event in distinct[:len(distinct) - MAX_VOICES]:
                if event != current:
                    voice = self._voices.get(event)
                    if voice is not None:
                        voice.stop()
