"""游戏音效管理器（内建，纯表现层）。

设计要点
────────
* 单例：`SoundManager.instance().play(...)`。
* 后端为 `PySide6.QtMultimedia.QSoundEffect`：短音效、预加载、低延迟。
* 快速连点：同一 cue「打断重启」（stop → play）；18ms 内重复调用视为同一
  物理动作的衍生事件而丢弃；结局音独占清场；同时发声的不同 cue 最多 2 个，
  超额时按 `SOUND_PRIORITY` 停掉优先级最低者（唯一一套限流机制）。
* 强度分层：`intensity` 映射到音量增益，不额外增加素材。
* 音效包：主程序只提供 `media/sounds/*.wav` 这组默认资源；**包的发现、
  选择与导入完全由「皮肤与音效」插件负责**，通过 `SetSoundCommand` 把包名
  与落地目录传给本模块 `configure()`。缺哪个 wav 就沿用根目录默认资源。
* 任何异常（无音频设备、文件缺失、后端未就绪）都静默降级，绝不影响对局与录像。

事件枚举、素材映射、优先级与资源包扫描统一定义在 `shared_types.sounds`，
主进程与插件进程共用；本模块只负责播放调度。
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QUrl, QTimer
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import QApplication

from utils.app_logger import logger
from utils.path_utils import resource_path
from shared_types.sounds import (
    SoundEvent, SOUND_FILES, SOUND_PRIORITY, EXCLUSIVE_EVENTS,
    DEFAULT_PACK, is_safe_pack_name,
)

# 兼容既有调用点的模块级别名（新代码请直接 import shared_types.sounds）
_EXCLUSIVE_EVENTS = EXCLUSIVE_EVENTS
BUILTIN_SOUNDS_DIR: Path = resource_path("media") / "sounds"

# ── 快速连点参数（表现层审美常量，集中调参）────────────────────────
DEDUP_WINDOW_MS = 18        # 同一 cue 在此窗口内重复调用视为同一动作，丢弃
MERGE_WINDOW_MS = 40        # 并发统计窗口
EXCLUSIVE_WINDOW_MS = 180   # 结局音独占时长，期间压掉其他 cue
MAX_VOICES = 2              # 同时发声的不同 cue 上限
PENDING_TIMEOUT_MS = 2000   # 后端未就绪时补播的超时兜底


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
        self._pending_timer: QTimer | None = None

    def cancel_pending(self) -> None:
        """取消尚未播出的补播请求（静音 / 切配置 / 清场时必须调用）。"""
        self._pending_gain = None
        if self._pending_timer is not None:
            try:
                self._pending_timer.stop()
                self._pending_timer.deleteLater()
            except Exception:
                pass
            self._pending_timer = None

    def set_source(self, path: Path) -> None:
        if self._path == path:
            return
        self.cancel_pending()
        self._path = path
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
            self.cancel_pending()
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
            # 同时挂一个超时兜底：部分 Qt 后端两者信号都不触发，否则该 cue
            # 会永久静音且 _pending_gain 悬挂（此前无超时）。
            self._pending_gain = gain
            if self._pending_timer is None:
                self._pending_timer = QTimer()
                self._pending_timer.setSingleShot(True)
                self._pending_timer.timeout.connect(self._on_pending_timeout)
                self._pending_timer.start(PENDING_TIMEOUT_MS)
            return
        self._fire(gain)

    def _on_pending_timeout(self) -> None:
        if self._pending_gain is None:
            self.cancel_pending()
            return
        # 最后再试一次即时状态；仍不就绪就放弃并告警，避免无限悬挂。
        try:
            self._ready = self.effect.status() == QSoundEffect.Status.Ready
        except Exception:
            self._ready = False
        if self._ready:
            gain, self._pending_gain = self._pending_gain, None
            self._fire(gain)
        else:
            logger.warning("音效后端在超时内未就绪，已放弃补播")
        self.cancel_pending()

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
        self._volume_int = 70                    # 整数音量，避免浮点回读漂移
        self._volume = 0.7                       # 0.0 ~ 1.0，仅用于计算增益
        self._pack = DEFAULT_PACK
        self._extra_dir: Path | None = None
        self._voices: dict[SoundEvent, _Voice] = {}
        self._last_play: dict[SoundEvent, float] = {}
        self._exclusive_until = 0.0
        self._recent: list[tuple[float, SoundEvent]] = []
        self._needs_rebuild = False

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
        """由 `gameSetting.ini` 的设置项驱动，支持运行时热更新。

        `pack` 必须是单层目录名；非法值一律回退默认音效，防止路径穿越。
        `extra_dir` 必须是已存在的目录（相对路径也允许，但拒绝穿越到包外）。
        """
        self._enabled = bool(enabled)
        # 保留整数音量：此前用 int(self._volume * 100) 回写，会让 29/57/58
        # 这类值在「不带 volume 的部分更新命令」里悄悄降 1。
        try:
            self._volume_int = max(0, min(100, int(volume)))
        except (TypeError, ValueError):
            self._volume_int = 70
        self._volume = self._volume_int / 100.0
        self._pack = pack if is_safe_pack_name(pack) else DEFAULT_PACK
        if extra_dir:
            try:
                candidate = Path(extra_dir)
                self._extra_dir = candidate if candidate.is_dir() else None
            except (OSError, TypeError, ValueError):
                self._extra_dir = None
        else:
            self._extra_dir = None
        if not self._enabled:
            self.stop_all()
        if self._ensure_voices():
            self._rebuild()
            self._needs_rebuild = False
        else:
            # QApplication 尚不存在（独立调用/单测）：标记待补建，
            # play() 里补建 voices 后会重新 set_source，避免永久静音。
            self._needs_rebuild = True

    def current_volume(self) -> int:
        """整数音量 0~100，供部分更新命令精确回读。"""
        return self._volume_int

    def current_enabled(self) -> bool:
        return self._enabled

    def current_extra_dir(self) -> str:
        return str(self._extra_dir) if self._extra_dir else ""

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
        created = self._ensure_voices()
        if not created:
            return
        if self._needs_rebuild:
            # configure() 早于 QApplication 时 voices 为空；此处补建后必须
            # 重新 set_source，否则所有 _Voice._valid=False 会永久静音。
            self._rebuild()
            self._needs_rebuild = False
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
                # 静音 / 切配置 / 清场后必须取消未播出的补播，否则
                # statusChanged 抵达时 _fire() 会绕过 _enabled 凭空响一声。
                voice.cancel_pending()
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
        """按「当前音效包 > 根目录默认」解析素材路径。

        `pack` 已在 configure() 中通过 is_safe_pack_name 净化，这里不再拼接
        未经校验的用户输入，避免路径穿越。
        """
        if self._pack:
            for root in self._pack_roots():
                candidate = root / self._pack / SOUND_FILES[event]
                if candidate.is_file():
                    return candidate
        return BUILTIN_SOUNDS_DIR / SOUND_FILES[event]

    def _limit_voices(self, now: float, current: SoundEvent) -> None:
        """同时发声上限：按 SOUND_PRIORITY 停掉优先级最低的 cue。

        此前按 _recent 的**时间序**停掉最早 cue（与 GUI 层的优先级排序
        意图相反），且被停的 cue 仍在 _last_play 里，18ms 内再次请求会被
        去重窗口误杀。现在统一由优先级表决定，并从 _last_play 移除。
        """
        self._recent = [
            (t, e) for t, e in self._recent
            if (now - t) * 1000.0 < MERGE_WINDOW_MS
        ]
        self._recent.append((now, current))
        distinct: list[SoundEvent] = []
        for _, event in self._recent:
            if event not in distinct:
                distinct.append(event)
        if len(distinct) <= MAX_VOICES:
            return
        # 低优先级优先停；同优先级时保留当前 cue。
        ranked = sorted(
            (e for e in distinct if e != current),
            key=lambda e: SOUND_PRIORITY[e],
        )
        for event in ranked[:len(distinct) - MAX_VOICES]:
            voice = self._voices.get(event)
            if voice is not None:
                voice.stop()
                voice.cancel_pending()
            self._last_play.pop(event, None)
            self._recent = [(t, e) for t, e in self._recent if e != event]
