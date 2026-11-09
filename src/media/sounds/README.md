# 音效包

与 `plugins/skin_manager/skins/` 同构：**一个子目录就是一个音效包**，切换即时生效、不写配置、不重启。

> 游戏音效**默认关闭**。需先在「游戏设置」里勾选「游戏音效」（可选音量和音效包），
> 对应配置项 `DEFAULT/sound_enabled`，默认 `False`。

## 目录结构

```
media/sounds/
├─ ready.wav          # 默认音效（根目录）
├─ start.wav
├─ open.wav
├─ chord.wav
├─ flag_on.wav
├─ flag_off.wav
├─ question.wav
├─ win.wav
├─ lose.wav
├─ _template/         # 以 _ 开头会被扫描跳过，仅作模板
│  └─ sound.json
└─ my_pack/           # 自定义音效包
   ├─ sound.json      # 可选，{"name": "显示名", ...}，仅用于下拉框显示
   ├─ open.wav        # 只替换想要的 cue
   └─ win.wav         # 缺的 cue 自动沿用根目录默认音效
```

**新增目录即自动出现在设置页「当前音效包」下拉框**，无需修改 Python 代码
（新增后需重开设置页）。也可在设置里填「额外音效库目录」指向自己的音效库，
与自带库合并；同名包以自带库为准。

## 事件对照

| 文件 | 事件 | 触发时机 |
|---|---|---|
| `ready.wav` | `READY` | 程序启动、主窗口就绪（`play_ready()`，延迟 350ms 等音频后端） |
| `start.wav` | `START` | 第一次有效左键抬起、埋雷完成（计时开始） |
| `open.wav` | `OPEN` | 单击开格 |
| `chord.wav` | `CHORD` | 双击（chording）展开 |
| `flag_on.wav` | `FLAG_ON` | 插旗 |
| `flag_off.wav` | `FLAG_OFF` | 拔旗 / 取消标记 |
| `question.wav` | `QUESTION` | 问号（当前配置禁用问号，恒不触发；预留） |
| `win.wav` | `WIN` | 胜利 |
| `lose.wav` | `LOSE` | 踩雷 / 失败 |

## 规格建议

44.1kHz / 16bit / 单声道 WAV（也支持 Qt 可解码的其他格式）。
`open` / `flag_*` 建议 < 80ms，`lose` ~200ms，`win` ~400ms。
过长的音效在快速连点时会不断被打断重启，听感发糊。

## 生成占位音效

`python develop_tools/generate_sounds.py` 会用 `wave` 模块合成 9 个默认 cue 的无版权占位 wav
（外加 `soft/` 示例包的 4 个），用于打通链路与调参，可随时用真实素材覆盖。

## 程序接口（`utils/sound_manager.py`）

```python
from utils.sound_manager import SoundManager, SoundEvent, discover_choices

SoundManager.instance().play(SoundEvent.OPEN, intensity=3)   # 播放
SoundManager.instance().set_pack("my_pack")                  # 切包（热生效）
SoundManager.instance().register_sound(SoundEvent.WIN, path) # 覆盖单个 cue
SoundManager.instance().unregister_sound(SoundEvent.WIN)     # 还原
choices = discover_choices(extra_dir=None)                   # [(值, 显示名), ...]
```

后续放给插件时，只需在 `shared_types/commands.py` 加 `SetSoundPackCommand` /
`PlaySoundCommand`，主进程 handler 转调上述 API 即可，游戏逻辑代码无需改动。
