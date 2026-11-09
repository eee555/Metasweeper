# 默认音效资源（主程序）

本目录**只存放主程序的一组默认音效**：每个事件一个 `*.wav`，固定文件名。
游戏音效默认关闭，需在「游戏设置」里勾选（配置项 `DEFAULT/sound_enabled`，
默认 `False`），音量由 `DEFAULT/sound_volume` 控制。

> **音效包的选择不在主程序这里**。所有可选音效包（含示例包 `soft`）都由
> 「皮肤与音效」插件负责发现、选择与导入，位于
> `src/plugins/skin_manager/sounds/`，运行时播种到
> `data/plugin_data/SkinManagerPlugin/sounds/`。插件通过
> `SetSoundCommand(pack=..., extra_dir=...)` 让主进程加载；主程序只在本目录
> 的 wav 缺失某个 cue 时回退到这里。

事件枚举、素材映射与优先级统一定义在 `shared_types/sounds.py`（主进程与插件进程共用）。

## 目录结构

```
media/sounds/
├─ ready.wav          # READY
├─ start.wav         # START
├─ open.wav          # OPEN
├─ chord.wav         # CHORD
├─ flag_on.wav       # FLAG_ON
├─ flag_off.wav      # FLAG_OFF
├─ win.wav           # WIN
└─ lose.wav          # LOSE
```

**不要在这里新建子目录当音效包**：主程序设置页不再扫描或列出音效包。

## 事件对照

| 文件 | 事件 | 触发时机 |
|---|---|---|
| `ready.wav` | `READY` | 程序启动、主窗口就绪（`play_ready()`，延迟 350ms 等音频后端） |
| `start.wav` | `START` | 第一次有效左键抬起、埋雷完成（计时开始） |
| `open.wav` | `OPEN` | 单击开格 |
| `chord.wav` | `CHORD` | 双击（chording）展开；仅左键抬起且鼠标状态为 chording 时 |
| `flag_on.wav` | `FLAG_ON` | 插旗 |
| `flag_off.wav` | `FLAG_OFF` | 拔旗 / 取消标记 |
| `win.wav` | `WIN` | 胜利（真实鼠标操作导致，`_finish()`） |
| `lose.wav` | `LOSE` | 踩雷 / 失败（真实鼠标操作导致，`_finish()`） |

> 项目默认禁用问号（`config.constants` 未登记问号编码），因此不设 `QUESTION` 事件。
>
> `WIN` / `LOSE` 为独占事件：播放时清场，并短暂压掉其他 cue，避免与同帧的
> `START` / `OPEN` 叠加。同时发声的不同 cue 最多 2 个，超额时按
> `SOUND_PRIORITY` 停掉优先级最低者。

## 规格建议

44.1kHz / 16bit / 单声道 WAV（也支持 Qt 可解码的其他格式）。
`open` / `flag_*` 建议 < 80ms，`lose` ~200ms，`win` ~400ms。

## 生成占位音效

`python develop_tools/generate_sounds.py` 会用 `wave` 模块合成本目录默认 cue 的
无版权占位 wav，用于打通链路与调参，可随时用真实素材覆盖。

## 程序接口（`utils/sound_manager.py`）

```python
from utils.sound_manager import SoundManager
from shared_types.sounds import SoundEvent

SoundManager.instance().play(SoundEvent.OPEN, intensity=3)   # 播放
mgr = SoundManager.instance()
mgr.configure(enabled=True, volume=70, pack="soft",
              extra_dir="<plugin data>/sounds")  # 由插件命令驱动
mgr.current_volume()      # 整数音量 0~100
```

插件通过 `SetSoundCommand` 热更新开关 / 音量 / 音效包；主进程 handler 会校验
`pack`（单层目录名）与 `extra_dir`（不含 `..`、必须存在），并复查持久化授权。
