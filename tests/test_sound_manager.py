"""音效管理器单元测试。

用假 QSoundEffect 替换真实后端，纯逻辑验证，不依赖音频设备。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from utils import sound_manager as sm_mod  # noqa: E402
from utils.sound_manager import (  # noqa: E402
    SoundEvent, SoundManager, discover_choices, list_sound_packs,
    BUILTIN_SOUNDS_DIR, DEFAULT_PACK, DEDUP_WINDOW_MS,
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

    def isPlaying(self):
        return False


class _FakeSignal:
    def connect(self, *a, **kw):
        pass


class _FakeVoice:
    def __init__(self):
        self.effect = _FakeEffect()
        self.path = None
        self.gains: list[float] = []
        self._valid = False

    def set_source(self, path):
        self.path = Path(path)
        # 与真实 _Voice 一致：缺文件即静音
        self._valid = self.path.is_file()
        self.effect.setSource(str(path))

    def play(self, gain):
        if not self._valid:
            return
        self.gains.append(gain)
        self.effect.setVolume(gain)
        self.effect.stop()
        self.effect.play()

    def stop(self):
        self.effect.stop()


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    # 用假 voice 替换 QSoundEffect 依赖，避免真实音频设备
    monkeypatch.setattr(sm_mod, "_Voice", _FakeVoice)
    SoundManager._instance = None
    yield
    SoundManager._instance = None


def _m() -> SoundManager:
    mgr = SoundManager.instance()
    mgr.configure(enabled=True, volume=70)
    return mgr


def test_all_events_resolve_to_existing_wav():
    mgr = _m()
    for event in SoundEvent:
        path = mgr.resolve(event)
        assert path.name == f"{event.value}.wav", event
        assert path.is_file(), f"缺少默认音效 {path}"


def test_ready_event_exists_and_has_priority():
    from utils.sound_manager import SOUND_PRIORITY
    assert SoundEvent.READY.value == "ready"
    # 就绪音只低于结局音，高于开局音
    assert SOUND_PRIORITY[SoundEvent.READY] > SOUND_PRIORITY[SoundEvent.START]
    assert SOUND_PRIORITY[SoundEvent.READY] < SOUND_PRIORITY[SoundEvent.WIN]


def test_play_ready_is_silent_when_disabled():
    mgr = _m()
    mgr.configure(enabled=False, volume=70)
    mgr.play_ready(delay_ms=0)
    # 延迟回调尚未执行也不应创建 voice；开启时才会排队播放
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
    # 模拟 >18ms 后的下一次真实点击（快速连点），不去重
    mgr._last_play[SoundEvent.OPEN] -= DEDUP_WINDOW_MS / 1000.0 + 0.01
    mgr.play(SoundEvent.OPEN)
    # 每次都打断重启：stop 与 play 各两次
    assert v.effect.plays == 2
    assert v.effect.stops == 2


def test_dedup_window_suppresses_duplicate_event():
    mgr = _m()
    v = mgr._voices[SoundEvent.OPEN]
    mgr.play(SoundEvent.OPEN)
    mgr._last_play[SoundEvent.OPEN] = __import__("time").monotonic()
    mgr.play(SoundEvent.OPEN)
    assert v.effect.plays == 1, "18ms 内的重复调用应被去重"


def test_intensity_maps_to_gain():
    mgr = _m()
    v = mgr._voices[SoundEvent.OPEN]
    mgr.play(SoundEvent.OPEN, intensity=1)
    g1 = v.gains[-1]
    mgr._last_play.clear()
    mgr.play(SoundEvent.OPEN, intensity=12)
    g12 = v.gains[-1]
    assert g12 > g1


def test_win_lose_are_exclusive_and_clear_pending():
    mgr = _m()
    mgr.play(SoundEvent.OPEN, intensity=3)
    open_voice = mgr._voices[SoundEvent.OPEN]
    stops_before = open_voice.effect.stops
    mgr.play(SoundEvent.WIN)
    # 结局音会停掉其他在响的 cue
    assert open_voice.effect.stops > stops_before
    # 独占窗口内的普通 cue 全被压掉
    mgr.play(SoundEvent.OPEN, intensity=5)
    assert mgr._voices[SoundEvent.OPEN].effect.plays == 1


def test_configure_hot_updates_volume():
    mgr = _m()
    mgr.configure(enabled=True, volume=30)
    mgr.play(SoundEvent.OPEN)
    g30 = mgr._voices[SoundEvent.OPEN].gains[-1]
    mgr._last_play.clear()
    mgr.configure(enabled=True, volume=90)
    mgr.play(SoundEvent.OPEN)
    g90 = mgr._voices[SoundEvent.OPEN].gains[-1]
    assert g90 > g30


def test_register_sound_override_and_unrestore():
    mgr = _m()
    custom = BUILTIN_SOUNDS_DIR / "custom_override.wav"
    mgr.register_sound(SoundEvent.WIN, custom)
    assert mgr.resolve(SoundEvent.WIN) == custom
    mgr.unregister_sound(SoundEvent.WIN)
    assert mgr.resolve(SoundEvent.WIN).name == "win.wav"


def test_pack_missing_file_falls_back_to_default(tmp_path):
    """音效包缺 wav 时沿用根目录默认资源（与皮肤同构）。"""
    mgr = _m()
    pack = BUILTIN_SOUNDS_DIR / "_testpack"
    pack.mkdir(exist_ok=True)
    try:
        (pack / "open.wav").write_bytes(b"fake")
        mgr.configure(enabled=True, volume=70, pack="_testpack")
        assert mgr.resolve(SoundEvent.OPEN) == pack / "open.wav"
        assert mgr.resolve(SoundEvent.WIN) == BUILTIN_SOUNDS_DIR / "win.wav"
    finally:
        (pack / "open.wav").unlink(missing_ok=True)
        pack.rmdir()


def test_set_pack_public_api():
    mgr = _m()
    mgr.set_pack("nonexistent_pack")
    assert mgr.current_pack() == "nonexistent_pack"
    # 不存在的包所有 cue 都回退到默认，不抛异常
    assert all(mgr.resolve(e).is_file() for e in SoundEvent)


def test_discover_choices_default_first():
    choices = discover_choices()
    assert choices[0][0] == DEFAULT_PACK
    assert len(choices) >= 1
    # _ 开头的模板目录不被扫描
    assert all(not name.startswith("_") for name, _ in choices[1:])


def test_list_sound_packs_reads_display_name(tmp_path):
    pack = tmp_path / "my_pack"
    pack.mkdir()
    (pack / "sound.json").write_text(
        '{"name": "我的音效包"}', encoding="utf-8")
    assert list_sound_packs(tmp_path) == [("my_pack", "我的音效包")]


def test_missing_wav_is_silent_not_raising(tmp_path):
    mgr = _m()
    mgr.register_sound(SoundEvent.OPEN, tmp_path / "nope.wav")
    mgr.play(SoundEvent.OPEN)
    assert mgr._voices[SoundEvent.OPEN].effect.plays == 0
