"""生成主程序内建的默认占位音效（44.1kHz / 16bit / 单声道 WAV）。

本脚本只刷新 `media/sounds/*.wav` 这一组**默认资源**。可选音效包由
「皮肤与音效」插件自带并播种到可写数据目录，示例包位于
`src/plugins/skin_manager/sounds/`，不在此脚本职责内。

占位素材只用于打通链路与调参，后续替换为无版权素材即可。所有 wav 统一
做峰值归一化（85% 满量程），保证开箱即可听见。

用法（在 src 目录下，或任意 cwd）：
    python develop_tools/generate_sounds.py
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from utils.path_utils import resource_path

SR = 44100
OUT: Path = resource_path("media") / "sounds"

# 目标峰值占 16bit 满量程的比例。占位音效原先峰值只有 ~4000/32767，
# 再经 SoundManager 的音量增益后几乎听不见；统一归一化到接近满量程。
PEAK_RATIO = 0.85


def _normalize(samples: list[int]) -> list[int]:
    """把整段波形等比放大到目标峰值，统一各 cue 的响度且不削波。"""
    peak = max((abs(s) for s in samples), default=0)
    if peak < 1:
        return samples
    scale = (32767 * PEAK_RATIO) / peak
    return [int(max(-32768, min(32767, s * scale))) for s in samples]


def _env(t: float, dur: float, attack: float = 0.004, release: float = 0.35) -> float:
    """指数衰减包络 + 短 attack / release，避免爆音与咔哒声。"""
    if t < attack:
        return t / attack
    tail = dur - t
    if tail < release:
        return max(0.0, tail / release)
    return math.exp(-3.0 * t / dur)


def _tone(spec: list[tuple[float, float, float, float]], dur: float) -> list[int]:
    """spec: [(起始秒, 结束秒, 频率, 振幅), ...]"""
    n = int(SR * dur)
    frames = bytearray()
    for i in range(n):
        t = i / SR
        s = 0.0
        for t0, t1, freq, amp in spec:
            if t0 <= t < t1:
                # 轻微二次谐波，让音色不至于太单薄
                s += amp * (
                    math.sin(2 * math.pi * freq * t)
                    + 0.18 * math.sin(2 * math.pi * 2 * freq * t)
                )
        s *= _env(t, dur)
        s *= 0.5 * (1.0 + 0.25 * math.sin(2 * math.pi * 7 * t))  # 轻微颤音
        frames += struct.pack("<h", int(max(-1.0, min(1.0, s)) * 18000))
    return [struct.unpack_from("<h", frames, i * 2)[0] for i in range(n)]


def _noise(spec: list[tuple[float, float, float]], dur: float, seed: int = 1) -> list[int]:
    """噪声段（踩雷的闷响）。spec: [(起始秒, 结束秒, 振幅), ...]"""
    n = int(SR * dur)
    state = seed
    frames = bytearray()
    for i in range(n):
        t = i / SR
        amp = 0.0
        for t0, t1, a in spec:
            if t0 <= t < t1:
                amp = a
                break
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        white = (state / 0x7FFFFFFF) * 2.0 - 1.0
        s = amp * white * _env(t, dur)
        frames += struct.pack("<h", int(max(-1.0, min(1.0, s)) * 16000))
    return [struct.unpack_from("<h", frames, i * 2)[0] for i in range(n)]


def _write(name: str, samples: list[int]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    samples = _normalize(samples)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    peak = max((abs(s) for s in samples), default=0)
    print(f"  {str(path.relative_to(OUT)):24s} {len(samples)/SR*1000:6.0f} ms  peak={peak}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"生成占位音效 -> {OUT}")

    # 程序启动就绪：温和的上行双音，比第一击更长、更从容
    _write("ready.wav", _tone([
        (0.00, 0.16, 523, 0.42),
        (0.12, 0.34, 784, 0.40),
    ], 0.34))

    # 第一击 / 开局：原先 330Hz 单音太闷、又容易被鼠标点击声掩蔽，
    # 改为更高更亮的上行双音并适当延长，让「计时开始」这一下清晰可闻。
    _write("start.wav", _tone([
        (0.00, 0.10, 660, 0.50),
        (0.07, 0.22, 990, 0.45),
    ], 0.22))

    # 开格：极短清脆
    _write("open.wav", _tone([(0, 0.075, 880, 0.45)], 0.075))

    # 双击：比开格更厚，两个音叠加
    _write("chord.wav", _tone([
        (0, 0.10, 660, 0.40), (0.0, 0.10, 990, 0.28),
    ], 0.10))

    # 插旗：轻"咔"，上行
    _write("flag_on.wav", _tone([(0, 0.06, 1200, 0.40)], 0.06))

    # 拔旗：下行、更闷
    _write("flag_off.wav", _tone([(0, 0.06, 560, 0.40)], 0.06))

    # 项目默认禁用问号，不再生成 question.wav（QUESTION 事件已移除）

    # 失败：低频 + 噪声闷响
    lose = _tone([(0, 0.22, 150, 0.55)], 0.22)
    noise = _noise([(0, 0.12, 0.45)], 0.22, seed=7)
    _write("lose.wav", [
        int(max(-32768, min(32767, a * 0.7 + b * 0.6))) for a, b in zip(lose, noise)
    ])

    # 胜利：上行小三和弦
    _write("win.wav", _tone([
        (0.00, 0.14, 523, 0.38),
        (0.10, 0.26, 659, 0.38),
        (0.20, 0.42, 784, 0.42),
        (0.30, 0.42, 1047, 0.20),
    ], 0.42))

    # 可选音效包（soft 示例）由插件自带并播种，不在本脚本生成。
    print("完成。")


if __name__ == "__main__":
    main()
