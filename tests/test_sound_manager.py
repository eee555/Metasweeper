"""音效管理器单元测试。

设计原则：
* 不再把整个真实 `_Voice`（异步 statusChanged 门控 + 补播超时）mock 掉；
  默认使用轻量 `_FakeVoice` 只替换 QSoundEffect，但额外提供真实 `_Voice`
  的门控用例，覆盖此前完全没测到的路径。
* 断言公开的播放结果，而不是只断言 `_last_play` 私有字典。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from utils import sound_manager as sm_mod  # noqa: E402
from utils.sound_manager import (  # noqa: E402
    SoundManager,
    BUILTIN_SOUNDS_DIR, DEFAULT_PACK, DEDUP_WINDOW_MS, PENDING_TIMEOUT_MS,
)
# 在 fixture 替换 sm_mod._Voice 之前保存真实类，供门控用例直接构造
from utils.sound_manager import _Voice as _RealVoice  # noqa: E402
from shared_types.sounds import (  # noqa: E402
    SoundEvent, SOUND_EVENT_NAMES, SOUND_PRIORITY, SOUND_META_FILE,
    is_safe_pack_name, list_packs, read_meta_name,
)


class _FakeEffect:
    class Status:
        Ready = "Ready"
        Loading = "Loading"
        Null = "Null"
        Error = "Error"

    def __init__(self):
        self.plays = 0
        self.stops = 0
        self.volume = 0.0
        self._path = None
        self.loadedChanged = _FakeSignal()
        self.statusChanged = _FakeSignal()
        self._status = self.Status.Ready

    def setSource(self, url):
        self._path = url

    def status(self):
        return self._status

    def setVolume(self, v):
        self.volume = v

    def stop(self):
        self.stops += 1

    def play(self):
        self.plays += 1


class _FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, cb):
        self.callbacks.append(cb)


class _FakeVoice:
    """只替换音频设备；保留 SoundManager 的调度逻辑。"""

    def __init__(self):
        self.effect = _FakeEffect()
        self.path = None
        self.gains: list[float] = []
        self.played: list[tuple] = []
        self._valid = False
        self._pending_gain = None

    def set_source(self, path):
        self.path = Path(path)
        self._valid = self.path.is_file()
        self.effect.setSource(str(path))

    def play(self, gain):
        if not self._valid:
            return
        self.gains.append(gain)
        self.played.append(gain)
        self.effect.setVolume(gain)
        self.effect.stop()
        self.effect.play()

    def stop(self):
        self.effect.stop()

    def cancel_pending(self):
        self._pending_gain = None


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(sm_mod, "_Voice", _FakeVoice)
    SoundManager._instance = None
    yield
    SoundManager._instance = None


def _m() -> SoundManager:
    mgr = SoundManager.instance()
    mgr.configure(enabled=True, volume=70)
    return mgr


# ── 共享层一致性 ────────────────────────────────────────────────

def test_events_and_names_are_single_source():
    assert SOUND_EVENT_NAMES == tuple(e.value for e in SoundEvent)
    assert len(SOUND_EVENT_NAMES) == 8          # QUESTION 已移除
    assert "question" not in SOUND_EVENT_NAMES


def test_priority_table_is_used_by_manager():
    assert SOUND_PRIORITY[SoundEvent.WIN] > SOUND_PRIORITY[SoundEvent.OPEN]
    assert SOUND_PRIORITY[SoundEvent.OPEN] > SOUND_PRIORITY[SoundEvent.FLAG_ON]
    assert all(e in SOUND_PRIORITY for e in SoundEvent)


def test_pack_name_validation_rejects_traversal():
    assert is_safe_pack_name("soft")
    assert is_safe_pack_name("中文包")
    for bad in ("../..", "C:/x", "a/b", r"a\b", "_tpl", "", "..", "a.b"):
        assert not is_safe_pack_name(bad), bad


def test_read_meta_name_handles_non_dict_json(tmp_path):
    meta = tmp_path / "sound.json"
    for content in ("[]", "null", '"x"', "3", "{bad json"):
        meta.write_text(content, encoding="utf-8")
        assert read_meta_name(meta, "fallback") == "fallback"
    meta.write_text('{"name": "我的包"}', encoding="utf-8")
    assert read_meta_name(meta, "fallback") == "我的包"


# ── 解析与配置 ──────────────────────────────────────────────────

def test_all_events_resolve_to_existing_wav():
    mgr = _m()
    for event in SoundEvent:
        path = mgr.resolve(event)
        assert path.name == f"{event.value}.wav", event
        assert path.is_file(), f"缺少默认音效 {path}"


def test_pack_missing_file_falls_back_to_default(tmp_path):
    """音效包缺 wav 时沿用根目录默认资源（与皮肤同构）。"""
    mgr = _m()
    pack = BUILTIN_SOUNDS_DIR / "testpack"
    pack.mkdir(exist_ok=True)
    try:
        (pack / "open.wav").write_bytes(b"fake")
        mgr.configure(enabled=True, volume=70, pack="testpack")
        assert mgr.resolve(SoundEvent.OPEN) == pack / "open.wav"
        assert mgr.resolve(SoundEvent.WIN) == BUILTIN_SOUNDS_DIR / "win.wav"
    finally:
        (pack / "open.wav").unlink(missing_ok=True)
        pack.rmdir()


def test_configure_rejects_unsafe_pack():
    mgr = _m()
    for bad in ("../..", "C:/Windows", "a/b"):
        mgr.configure(enabled=True, volume=70, pack=bad)
        assert mgr.current_pack() == DEFAULT_PACK, bad


def test_integer_volume_roundtrip_has_no_drift():
    """29 / 57 / 58 曾因 int(0.29*100) 漂移成 28 / 56 / 57。"""
    mgr = _m()
    for v in (29, 57, 58, 0, 100):
        mgr.configure(enabled=True, volume=v)
        assert mgr.current_volume() == v


def test_configure_before_qapplication_marks_rebuild(monkeypatch):
    """QApplication 尚不存在时 configure 不能让音效永久静音。"""
    SoundManager._instance = None
    mgr = SoundManager.instance()
    original = sm_mod.QApplication.instance
    monkeypatch.setattr(
        sm_mod.QApplication, "instance", staticmethod(lambda: None))
    mgr.configure(enabled=True, volume=70)
    assert mgr._needs_rebuild
    monkeypatch.setattr(
        sm_mod.QApplication, "instance", staticmethod(original))
    mgr.play(SoundEvent.OPEN)
    assert not mgr._needs_rebuild
    voice = mgr._voices[SoundEvent.OPEN]
    assert getattr(voice, "path", getattr(voice, "_path", None)) is not None


def test_stop_all_cancels_pending_gain():
    """静音 / 切配置后不能再凭空补播一声。"""
    mgr = _m()
    voice = mgr._voices[SoundEvent.OPEN]
    voice._pending_gain = 0.7
    mgr.stop_all()
    assert voice._pending_gain is None


# ── 播放行为 ────────────────────────────────────────────────────

def test_play_ready_is_silent_when_disabled():
    mgr = _m()
    mgr.configure(enabled=False, volume=70)
    mgr.play_ready(delay_ms=0)
    assert mgr._voices[SoundEvent.READY].effect.plays == 0


def test_disabled_and_zero_volume_are_silent():
    mgr = _m()
    mgr.configure(enabled=False, volume=70)
    mgr.play(SoundEvent.OPEN)
    assert all(v.effect.plays == 0 for v in mgr._voices.values())
    mgr.configure(enabled=True, volume=0)
    mgr.play(SoundEvent.OPEN)
    assert all(v.effect.plays == 0 for v in mgr._voices.values())


def test_play_retriggers_same_cue():
    mgr = _m()
    v = mgr._voices[SoundEvent.OPEN]
    mgr.play(SoundEvent.OPEN)
    mgr._last_play[SoundEvent.OPEN] -= DEDUP_WINDOW_MS / 1000.0 + 0.01
    mgr.play(SoundEvent.OPEN)
    assert v.effect.plays == 2
    assert v.effect.stops == 2


def test_dedup_window_suppresses_duplicate_event():
    mgr = _m()
    v = mgr._voices[SoundEvent.OPEN]
    mgr.play(SoundEvent.OPEN)
    import time
    mgr._last_play[SoundEvent.OPEN] = time.monotonic()
    mgr.play(SoundEvent.OPEN)
    assert v.effect.plays == 1


def test_intensity_maps_to_gain():
    mgr = _m()
    v = mgr._voices[SoundEvent.OPEN]
    mgr.play(SoundEvent.OPEN, intensity=1)
    g1 = v.gains[-1]
    mgr._last_play.clear()
    mgr.play(SoundEvent.OPEN, intensity=12)
    assert v.gains[-1] > g1


def test_win_lose_are_exclusive_and_clear_pending():
    mgr = _m()
    mgr.play(SoundEvent.OPEN, intensity=3)
    open_voice = mgr._voices[SoundEvent.OPEN]
    stops_before = open_voice.effect.stops
    mgr.play(SoundEvent.WIN)
    assert open_voice.effect.stops > stops_before
    mgr.play(SoundEvent.OPEN, intensity=5)
    assert mgr._voices[SoundEvent.OPEN].effect.plays == 1


def test_limit_voices_stops_lowest_priority_not_earliest():
    """40ms 内 OPEN → FLAG_ON → CHORD：应停 FLAG_ON（优先级最低），
    而不是停最早出现的 OPEN。"""
    mgr = _m()
    import time
    now = time.monotonic()
    for e in (SoundEvent.OPEN, SoundEvent.FLAG_ON, SoundEvent.CHORD):
        mgr._recent.append((now, e))
    mgr._limit_voices(now, SoundEvent.CHORD)
    assert SoundEvent.FLAG_ON not in [e for _, e in mgr._recent]
    # 被停的 cue 不应在去重表里造成 18ms 内哑掉
    assert SoundEvent.FLAG_ON not in mgr._last_play


def test_configure_hot_updates_volume():
    mgr = _m()
    mgr.configure(enabled=True, volume=30)
    mgr.play(SoundEvent.OPEN)
    g30 = mgr._voices[SoundEvent.OPEN].gains[-1]
    mgr._last_play.clear()
    mgr.configure(enabled=True, volume=90)
    mgr.play(SoundEvent.OPEN)
    assert mgr._voices[SoundEvent.OPEN].gains[-1] > g30


# ── 真实 _Voice 门控（此前完全被 mock 掉的路径）────────────────

def test_real_voice_defers_until_ready_and_cancel_works(monkeypatch):
    """用假 QSoundEffect 但保留真实 _Voice，验证未就绪排队 + 取消补播。"""
    class _LoadingEffect:
        class Status:
            Ready = "Ready"
            Loading = "Loading"

        def __init__(self):
            self.statusChanged = _FakeSignal()
            self._status = self.Status.Loading
            self.volume = 0.0
            self.plays = 0
            self.stops = 0

        def status(self):
            return self._status

        def setSource(self, url):
            pass

        def setVolume(self, v):
            self.volume = v

        def stop(self):
            self.stops += 1

        def play(self):
            self.plays += 1

    class _FakeTimer:
        def __init__(self):
            self.timeout = _FakeSignal()

        def setSingleShot(self, v):
            pass

        def start(self, ms):
            assert ms == PENDING_TIMEOUT_MS

        def stop(self):
            pass

        def deleteLater(self):
            pass

    monkeypatch.setattr(sm_mod, "QSoundEffect", _LoadingEffect)
    monkeypatch.setattr(sm_mod, "QTimer", _FakeTimer)
    voice = _RealVoice()

    voice.set_source(BUILTIN_SOUNDS_DIR / "open.wav")
    voice.play(0.5)
    assert voice._pending_gain == 0.5, "未就绪应排队补播"
    assert voice._pending_timer is not None, "应挂超时兜底"
    voice.cancel_pending()
    assert voice._pending_gain is None, "取消补播后不得再响"
    assert voice._pending_timer is None


def test_real_voice_status_ready_fires_pending(monkeypatch):
    """statusChanged 变 Ready 后应把排队的 cue 补播出来。"""
    class _DelayedEffect:
        class Status:
            Ready = "Ready"
            Loading = "Loading"

        def __init__(self):
            self.statusChanged = _FakeSignal()
            self._status = self.Status.Loading
            self.volume = 0.0
            self.plays = 0
            self.stops = 0

        def status(self):
            return self._status

        def setSource(self, url):
            pass

        def setVolume(self, v):
            self.volume = v

        def stop(self):
            self.stops += 1

        def play(self):
            self.plays += 1

    class _FakeTimer:
        def __init__(self):
            self.timeout = _FakeSignal()

        def setSingleShot(self, v):
            pass

        def start(self, ms):
            pass

        def stop(self):
            pass

        def deleteLater(self):
            pass

    monkeypatch.setattr(sm_mod, "QSoundEffect", _DelayedEffect)
    monkeypatch.setattr(sm_mod, "QTimer", _FakeTimer)
    voice = _RealVoice()

    voice.set_source(BUILTIN_SOUNDS_DIR / "open.wav")
    voice.play(0.5)
    assert voice._pending_gain == 0.5
    voice.effect._status = _DelayedEffect.Status.Ready
    voice._on_status()
    assert voice.effect.plays == 1
    assert voice._pending_gain is None


# ── 资源包扫描（共享层；主程序不再扫描音效包）──────────────────

def test_default_pack_constant_and_no_main_side_scan():
    """主程序只有默认资源，不再提供 discover_choices / list_sound_packs。"""
    assert not hasattr(sm_mod, "discover_choices")
    assert not hasattr(sm_mod, "list_sound_packs")
    assert DEFAULT_PACK == ""


def test_list_packs_reads_display_name(tmp_path):
    pack = tmp_path / "my_pack"
    pack.mkdir()
    (pack / "sound.json").write_text(
        '{"name": "我的音效包"}', encoding="utf-8")
    assert list_packs(tmp_path, SOUND_META_FILE) == [("my_pack", "我的音效包")]


def test_list_packs_survives_non_dict_meta(tmp_path):
    pack = tmp_path / "bad_pack"
    pack.mkdir()
    (pack / "sound.json").write_text("[]", encoding="utf-8")
    assert list_packs(tmp_path, SOUND_META_FILE) == [("bad_pack", "bad_pack")]


def test_list_packs_survives_unreadable_root(tmp_path):
    assert list_packs(tmp_path / "nonexistent", SOUND_META_FILE) == []
