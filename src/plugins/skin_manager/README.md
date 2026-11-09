# 皮肤管理插件

设置页**下拉框选皮肤**，运行时热替换主窗口的图片资源：
**纯内存、即时生效、不写游戏目录、不重启**。主进程退出后自动还原。

内置八套完整皮肤，覆盖冷暖浅色、蓝色、石墨灰、复古绿、霓虹紫与纯色线索：

- **深海蓝**：`skins/deep_ocean/preview.png`
- **石墨夜（黑曜石）**：炭灰与深蓝灰层次，避免纯黑，`skins/graphite_night/preview.png`
- **雾凇白**：冷调灰蓝和霜白凸面，`skins/frost_white/preview.png`
- **奶油暖白**：暖米白和燕麦色，`skins/cream_light/preview.png`
- **复古绿显**：CRT 深绿与荧光绿数码管，`skins/retro_green/preview.png`
- **赛博霓虹**：深紫底、青蓝与洋红点缀，`skins/cyber_neon/preview.png`
- **纯色线索（奶油暖白）**：基于奶油暖白，仅将 `cell1.svg`–`cell8.svg` 数字换成经典颜色圆点，`skins/color_only_light/preview.png`
- **纯色线索（石墨夜）**：基于石墨夜，仅将 `cell1.svg`–`cell8.svg` 数字换成带浅描边的经典颜色圆点，`skins/color_only_dark/preview.png`

所有皮肤都会自动出现在「当前皮肤」下拉框中。主题资源生成脚本：
`develop_tools/generate_graphite_skin.py`（石墨夜）、
`develop_tools/generate_light_skins.py`（两套浅色主题）、
`develop_tools/generate_theme_collection.py`（复古绿显、赛博霓虹）、
`develop_tools/generate_color_only_skins.py`（基于奶油暖白和石墨夜的圆点线索变体）。

两套纯色线索分别沿用奶油暖白和石墨夜的原资源，只替换各自的 `cell1.svg`–`cell8.svg`；
打开格中央绘制彩色圆点表示周围的雷数 1–8，不绘制数字。
棋盘顶部的剩余雷数和计时 LED 仍显示数字，便于读取游戏状态。
颜色顺序采用经典扫雷配色：1 蓝、2 绿、3 红、4 深蓝、5 栗色、6 青、7 黑、8 灰。
石墨夜变体为圆点增加浅色描边，确保圆点在线索格上清楚可见。
这两套继承底图的 `colors.json`（包含 `flag_bg`），但有整幅 `frame.svg` 时，国旗标签运行时设为透明并透出 SVG 背景。

## 使用

1. 启用插件后，在插件管理器里右键插件 → **🔐 一键授权控制权限**
   （`SetSkinCommand` 同一时间只能授权给一个插件，避免多个皮肤插件互相抢）。
2. 右键插件 → **⚙️ 设置...**，在「当前皮肤」下拉框里选择，点确定立即生效。
   选「默认皮肤（不替换）」即还原。
   - 「启动时自动应用」：下次启动自动恢复上次选择（默认开）。
   - 「额外皮肤库目录」：可指向自己的皮肤库，与内置皮肤合并。
3. 插件标签页显示最近一次应用结果，也可点「重新应用」强制重发。

> 下拉框不是手写 UI，而是 `config.py` 在模块导入时扫描皮肤目录、
> 自动注册成 `ChoiceConfig` 选项（与 `clipboard_replay` 的
> `add_handler_fields` 同一套路）。**新增皮肤目录即自动出现在下拉框里**，
> 不需要改任何 Python 代码（新增后需重启插件管理器或重开设置页）。

## 自动注册机制

```
config.py 导入
  → discover_choices() 扫描 skins/*/（跳过 _ 开头目录）
  → 读每目录 skin.json 的 name 作为显示名
  → register_skins() 覆盖 SkinManagerConfig.skin 的 choices
  → 插件设置对话框按 ChoiceConfig 自动生成 QComboBox
```

用户改了「额外皮肤库目录」时，插件的 `_refresh_choices()` 会重新扫描，
并同步刷新已实例化配置对象的 `_fields`，让下次打开设置页看到新选项。

## 皮肤包格式

一个子目录就是一个皮肤，放在 `skins/` 下（或设置里指定的皮肤库目录）：

```
skins/
└─ my_skin/
   ├─ skin.json          # 可选，{"name": "显示名"}
   ├─ celldown.svg       # 已翻开/按下
   ├─ cellup.svg         # 未翻开
   ├─ cell1.svg … cell8.svg
   ├─ cellflag.svg       # 旗子
   ├─ cellquestion.svg   # 问号
   ├─ cellmine.svg       # 白雷
   ├─ blast.svg          # 爆炸雷
   ├─ falsemine.svg      # 标错的雷
   ├─ mine.svg           # 概率叠加用透明雷
   ├─ LED0.png … LED9.png
   ├─ smileface.svg      # 笑脸
   ├─ clickface.svg      # 点击脸
   ├─ lostface.svg       # 失败脸
   ├─ winface.svg        # 胜利脸
   ├─ smilefacedown.svg  # 按下脸
   ├─ frame.svg          # 可选：一张统一的大幅 SVG 窗口背景
   ├─ colors.json        # 可选：主窗口框架配色（见下）
   └─ preview.png        # 可选：预览图（插件不读取，仅供人看）
```

**缺哪个文件就沿用默认资源**，所以可以做「只换数字」「只换笑脸」的轻量皮肤。
最省事的做法：把 `src/media/` 里同名文件整个复制进皮肤目录，再逐张替换。

`frame.svg` 是**一张完整的大图**，铺在现有 `centralwidget` 的背景上。
外框、顶部条、雷区框和底部信息栏等现有控件透明透出这张完整背景；不会
创建背景控件，也不会把 SVG 切成多张控件贴图，更不会覆盖格子、笑脸、计数器
等已有控件。独立计数器窗口也复用同一张完整 SVG，按整个计数器面板缩放，
不切局部贴图；其表格视口和单元格透明。窗口缩放时主窗口重绘背景，计数器
则按当前面板尺寸缩放同一张图。SVG 没有时，继续使用 `colors.json` 的纯色背景。

深海蓝由 `develop_tools/generate_skin.py` 生成；其他内置主题由上方列出的专用脚本生成。

### 规格

| 类别 | 尺寸 | 说明 |
|---|---|---|
| 格子 16 张 | 160×160 SVG | `pixSize` 最大 255，源图需够大 |
| 笑脸 5 张 | 260×260 SVG | 按 `pixSize × 1.5` 缩放 |
| LED 10 张 | 208×368 PNG | 代码按 `208/368` 比例缩放 |

限制：单张 ≤ 512 KB，整套 ≤ 4 MB；解码失败整包拒绝，不会改到一半。

### colors.json（框架配色）

主窗口里那些**不是图片的浅灰区域**（外框、顶部条、底部信息栏、
右下角国旗白底）由 `QPalette` / `QFrame` 原生绘制，单纯换格子贴图会显得很割裂。
`colors.json` 用可逆 QSS + QPalette 一起换掉：

```json
{
  "window":       "#16324F",  // 主窗口 / 中央部件背景（原 #c0c0c0）
  "frame":        "#0E2237",  // 外框、雷区边框、顶部条边框
  "topbar":       "#1B3A5C",  // 顶部条背景
  "infobar":      "#1B3A5C",  // 底部信息栏背景
  "text":         "#CFE4F7",  // 底部信息文字（原黑色）
  "flag_bg":      "#16324F",  // 右下角国旗标签的底色（国旗图案不变）
  "sb_bg":        "#16324F",  // 计数器窗口背景
  "sb_text":      "#CFE4F7",  // 计数器标题 / 表格文字
  "sb_grid":      "#244B6E",  // 计数器表格网格线
  "sb_header":    "#0E2237"   // 计数器表头 / 「+」按钮悬停色
}
```

**菜单栏（背景、文字、下拉菜单）按需求保持系统原样**，没有对应配色键，
换肤时只记录并还原它的原始样式，不会改动。

计数器（计分板）是独立窗口，通过 `ui.score_board_manager.ui` 拿到
`QWidget` / `label_counter` / `tableWidget` / `pushButton_add` 一起换色。
由于 `ui_Form.apply_scale()` 每次滚轮缩放都会重设 `tableWidget` 的
`font-size` 样式表，`gameScoreBoard.apply_scale` 会把皮肤规则一起拼回去，
**缩放后配色不会丢失**。

只写要改的键即可，其余沿用原样式。选「默认皮肤」时会精确还原
换肤前记录的原始 `styleSheet` 与 `QPalette`。

若皮肤提供完整 `frame.svg`，`topbar` / `infobar` 的纯色填充由 SVG 背景接管，
无需再写这些键；它们只用于没有 `frame.svg` 的纯色框架皮肤。内置「深海蓝」
已经移除了这类冗余项，保留 SVG 无法替代的边框色、文字色和计数器配色。

## 覆盖范围

| 换 | 不换 |
|---|---|
| 雷区 16 张格子图 | 窗口图标 `cat.ico`（按要求排除） |
| 顶部 10 张 LED 数字 | 右下角**国旗图案**（按要求排除，只换其底色） |
| 5 张笑脸（含按下态） | 菜单栏背景 / 文字 / 下拉菜单（按要求排除） |
| 主窗口浅灰框架配色（colors.json） | 其它独立对话框里的图标 |
| 计数器（计分板）配色 | `GLOBAL_QSS` 按钮样式、字体 |
| | 游戏逻辑、录像数据、校验 |

## 为什么不会「缩放一下就变回去」

主进程收到皮肤后，把解码后的原图写入 `mineLabel.skin_source`、
`ui.skin_faces` / `skin_leds`、`StatusLabel.skin_face_*`，并重建所有派生缓存。
窗口改大小 (`pixSize` setter)、重开局、切模式时，控件原有的
`importCellPic` / `importLEDPic` / `reloadFace` 会**优先从内存源取原图**，
缺的 key 才回退磁盘，因此皮肤不会闪回默认。

「复制局面为 SVG」也已适配内存源，导出结果与屏幕一致；
PNG 截图走 `render()`，天然跟随新皮肤。
