# Meta Minesweeper (Metasweeper)

**[中文版本在此](README.md)**

* A professional Minesweeper suite featuring 8 gameplay modes, a third-generation replay player, and a high-performance algorithm toolbox.

[![](https://img.shields.io/github/release/eee555/Metasweeper.svg)](https://github.com/eee555/Metasweeper/releases)
[![stars](https://img.shields.io/github/stars/eee555/Metasweeper)](https://github.com/eee555/Metasweeper/stargazers)
[![forks](https://img.shields.io/github/forks/eee555/Metasweeper)](https://github.com/eee555/Metasweeper/forks)
[![](https://img.shields.io/github/downloads/eee555/Metasweeper/total.svg)](https://github.com/eee555/Metasweeper/releases)

## Introduction

**Metasweeper** is developed by experienced professional Minesweeper players and software engineers. It is not a simple clone of traditional Minesweeper, but a complete modernization in **algorithms, performance, extensibility, and tooling**.

Its replay formats are officially recognized by the [Open Minesweeper Network](https://openms.top) and included in international leaderboards.

<div align="center">
<img src="readme_pic/main_screenshot.png" width="700" alt="Main window screenshot"/>
<p align="center"><em>Main window — multi-tab replay player + programmable counter</em></p>
</div>

## Key Advantages & Technical Highlights

### (1) Algorithm & Engine System

Powered by the `ms_toollib` toolbox, Meta Minesweeper’s core strength comes from its highly optimized algorithm components that form a complete intelligent Minesweeper system.

* **Three inference engines**: multi-layered solving strategies from set-based deduction to full enumeration.
* **Unified board state machine**: abstracts the game board into a formal automaton, improving algorithm composability and extensibility.
* **Probability inference engine**: computes the probability of any tile containing a mine, with speed second only to JSMinesweeper.
* **Optical Board Recognition (OBR)**: reconstructs board states from screenshots of *any* Minesweeper application for cross-software intelligent analysis.

<div align="center">
<img src="readme_pic/obr_probability.png" width="600" alt="Probability & OBR"/>
<p align="center"><em>Press Space for per-tile mine probability; Ctrl+Space to OBR from screenshot</em></p>
</div>

---

### (2) Architecture & Tech Stack

Designed for strong performance, safety, and tooling friendliness.

* **Python / PyQt5 + Rust hybrid architecture**

  * Python handles UI and ecosystem extensions.
  * Rust provides high-performance, memory-safe core computation.
* **Complete UI–algorithm separation**, enabling independent iteration.
* Fully open-source toolbox **`ms_toollib` (MIT License)**, installable via `pip install ms_toollib` for use in external projects.

---

### (3) Gameplay Modes & Interaction

One of the most feature-complete and modernized Minesweeper implementations available.

* Supports **all 6 guess-free modes + Standard + Win7 mode**; weak/strong semi-guessable modes are unique implementations.
* **Ctrl + mouse wheel**: freely scale UI size.
* **Space**: compute mine probability for every tile.
* **Ctrl + Space**: screenshot + OBR to compute probabilities for external Minesweeper applications.
* **Board filter**: complex filtering based on custom strategies.
* **Programmable counter**: 30+ built-in metrics (3BV/s, STNB, RQP, pluck, ZiNi, etc.) with **full Python expression syntax** for custom formulas.
* **Drag & drop** replay files directly onto the window to start playback.

<div align="center">
<img src="readme_pic/counter_custom.png" width="500" alt="Programmable counter"/>
<p align="center"><em>Programmable counter — full Python expression syntax for custom metrics</em></p>
</div>

---

### (4) Replay System & Ecosystem Compatibility

Meta Minesweeper is not just a game but a full analysis platform.

* **Multi-tab replay player**: open multiple replays simultaneously, switch freely between tabs, and draw mouse traces during playback.
* Supports **avf / rmv / mvf / [evf](https://github.com/eee555/ms_toollib/blob/main/evf标准.md)** formats.
* Supports **[evfs](https://github.com/eee555/ms_toollib/blob/main/evfs标准.md)** replay-set format with multi-select export to individual evf files.
* Resistant to common cheating methods (e.g., speed-gear tools).
* Internationalization: Chinese, English, German, Polish, Japanese, etc.
* **CLI verification**: use the `-c` flag to batch-verify replay file integrity.

<div align="center">
<img src="readme_pic/replay_player.png" width="700" alt="Multi-tab replay player"/>
<p align="center"><em>Multi-tab replay player — play, switch, and analyze multiple replays simultaneously</em></p>
</div>

---

### (5) Plugin System & Ecosystem

The **Plugin Manager** runs on a ZMQ event bus, fully decoupled from the main process — a plugin can crash without affecting the game.

* **History plugin**: automatically records every game session; right-click to copy any record as JSON; import/export in stats.dat / meta.dat / textstats.csv formats.
* **LLM Controller plugin**: control the game via natural language through a large language model ("open intermediate", "flag this tile", etc.).
* **XianNiUpgrade plugin**: XP / level-up / lottery system that gamifies Minesweeper practice, with intelligent replay absorption.
* **Advanced settings panel**: central management for plugin authorization, event subscriptions, board update security toggles, and more.
* The plugin SDK is fully open — anyone can write custom plugins and hook into the event bus.

<div align="center">
<img src="readme_pic/plugin_manager.png" width="600" alt="Plugin manager"/>
<p align="center"><em>Plugin manager — History, LLM Controller, XianNiUpgrade</em></p>
</div>

---

## Reference Links

* User Guide: [https://openms.top/#/guide/[80.%E6%95%99%E7%A8%8B.%E8%BD%AF%E4%BB%B6]%E5%85%83%E6%89%AB%E9%9B%B7%E4%BD%BF%E7%94%A8%E6%95%99%E7%A8%8B](https://openms.top/#/guide/[80.%E6%95%99%E7%A8%8B.%E8%BD%AF%E4%BB%B6]%E5%85%83%E6%89%AB%E9%9B%B7%E4%BD%BF%E7%94%A8%E6%95%99%E7%A8%8B)
* Algorithm Toolbox: [https://github.com/eee555/ms_toollib](https://github.com/eee555/ms_toollib)
* Toolbox Documentation: [https://docs.rs/ms_toollib](https://docs.rs/ms_toollib)

## Installation

Supported OS: **Windows 10 / Windows 11 only**

### Option 1: Install via Official Download (Recommended)

Find the latest version in the [download section](#download-links), unzip it, and run `main.exe` directly (click “Run anyway” if prompted).
Software installed this way is the **official, fully signed version**, capable of generating valid replay signatures (`metaminesweeper_checksum.pyd` is the small closed-source signing module).

### Option 2: Install via GitHub Actions (Safest)

**Note:** this version **cannot** generate valid replay signatures. Replays created by self-built versions cannot pass validation by the official build. All other features are identical.

Go to [GitHub Actions](https://github.com/eee555/Solvable-Minesweeper/actions), find the latest successful build, download the Artifacts, and run as above.
Provides the newest features and guaranteed clean/no-virus builds, but unreleased builds may be unstable.

### Option 3: Build from Source (Not Recommended)

**Note:** this version also **cannot** produce valid replay signatures.
Users may create custom builds and implement their own secret signature logic if desired.

Requirements:

* Python ≥3.10, ≤3.12 (3.12 recommended)
* Ability to use PowerShell or any CLI

Steps:

```sh
git clone https://github.com/eee555/Solvable-Minesweeper.git
```

Option A: Install Python deps from PyPI (simple, may fail if API changed)

```sh
pip install -r requirements.txt   # Windows
pip3 install -r requirements.txt  # *nix
```

Option B: Install deps from GitHub (nightly ms_toollib; guaranteed to work; requires Rust)

```sh
git clone https://github.com/eee555/ms_toollib.git
cd ms_toollib/python_package
cargo build --release
# Rename ms_toollib.dll → ms_toollib.pyd and copy to Solvable-Minesweeper/src
# Install all remaining requirements except ms_toollib
```

Additional required files (copy from any earlier release):

* `en_US.qm`, `de_DE.qm`, `pl_PL.qm` etc. → Solvable-Minesweeper/
* `params.onnx` model → Solvable-Minesweeper/src/

Run:

```sh
py -3 src/main.py     # Windows
python3 src/main.py   # *nix
```

## Contributing

See [CONTRIBUTING.md](https://github.com/eee555/Solvable-Minesweeper/blob/master/CONTRIBUTING.md)

## License Notice

This project uses **GPLv3 with additional terms**, explicitly prohibiting unauthorized commercial use and defining revenue distribution rules.
See `LICENSE` for details.

## Honors

Featured in Awesome Rust Repositories:
[https://twitter.com/RustRepos/status/1636837781765799940](https://twitter.com/RustRepos/status/1636837781765799940)

Featured on llamasweeper.com (4.5 stars):
[https://llamasweeper.com/#/others](https://llamasweeper.com/#/others)

Official Minesweeper software of OpenMS: [https://openms.top](https://openms.top)

[![Star History Chart](https://api.star-history.com/svg?repos=eee555/Metasweeper\&type=Date)](https://star-history.com/?repos=eee555/Metasweeper#repos=eee555/Metasweeper&Date)

## Sponsorship

Thank you for considering support. Please note in your donation:
**Project name + your nickname + any message**, e.g.
`Meta Minesweeper + Mr. Zhang + please add feature X`.

Per project rules, donations are distributed among contributors proportionally to commit count.

### General Supporter

* One-time donation **¥3+**
* Your name is permanently listed in the contributor table

### Important Supporter

* One-time donation **¥50+**
* All rights of General Supporter
* Regular project progress reports

### Core Supporter

* Total donation **¥1000+**
* All rights of Important Supporter
* Development priorities may be adjusted per your reasonable requests

![](readme_pic/微信收款码.png) ![](readme_pic/支付宝收款码.png)

## Contributor List

| Sponsor | Amount |    Date    | Channel | Distribution |
| :-----: | :----: | :--------: | :-----: | :----------: |
| Unknown Poet | ¥6.00  | 2026-06-16 |  WeChat |    Pending   |
|  *Chang | ¥55.00 | 2024-07-27 |  Alipay |    Pending   |
|  *Song  | ¥72.60 | 2024-04-04 |  WeChat |    Pending   |

## Download Links

### v3.3.3

Uncaught exceptions now show a dialog with full traceback instead of silently crashing. Bug fixes: copying board to matrix produced all-zero data; plugin manager no longer allows multiple instances; file-association replay opening crash; game crash after modifying config via custom menu after starting; double-button mine activation crash.
Links:
[https://gitee.com/ee55/Metasweeper/releases/download/3.3.3/Metasweeper-3.3.3.exe](https://gitee.com/ee55/Metasweeper/releases/download/3.3.3/Metasweeper-3.3.3.exe)
[https://github.com/eee555/Metasweeper/releases/download/3.3.3/Metasweeper-3.3.3.exe](https://github.com/eee555/Metasweeper/releases/download/3.3.3/Metasweeper-3.3.3.exe)

### v3.3.2

Mouse traces can now be drawn during replay playback. Added Ctrl+C to copy .board data as ASCII/emoji rendering; Ctrl+V to quickly enter research mode or paste a copied board. Counter now scales with the main window. Probability algorithm improved ~100× faster. Adjustable guess-free mine-planting algorithm improved for both speed and 100% success rate (16×30/200 mines: single planting ≤200ms). F3 to restart current game. RQP and QG now compute correctly; added max_block_len. History plugin: right-click context menu to copy a game's data as JSON. Import stats.dat from older versions. Export meta.dat, meta.all.dat, textstats.csv. Bug fixes: v3.2.2 MD5 incorrect; counter keys cannot contain uppercase letters; plugin data could attempt writing to unwritable directories; number-key difficulty switching caused crashes; replay controller image resources missing; history plugin showed "0 rows 0 pages" on first open; mine count display incorrect during replay; non-standard modes gave no XP in XianNiUpgrade; weak guessable mode could fail to re-plant mines.
Links:
[https://gitee.com/ee55/Metasweeper/releases/download/3.3.2/Metasweeper-3.3.2.exe](https://gitee.com/ee55/Metasweeper/releases/download/3.3.2/Metasweeper-3.3.2.exe)
[https://github.com/eee555/Metasweeper/releases/download/3.3.2/Metasweeper-3.3.2.exe](https://github.com/eee555/Metasweeper/releases/download/3.3.2/Metasweeper-3.3.2.exe)

### v3.3.1

BoardUpdateEvent is now treated as unsafe; sending it to plugins requires explicit opt-in via Advanced Settings. Experience formula improved.
Links:
[https://gitee.com/ee55/Metasweeper/releases/download/3.3.1/Metasweeper-3.3.1.exe](https://gitee.com/ee55/Metasweeper/releases/download/3.3.1/Metasweeper-3.3.1.exe)
[https://github.com/eee555/Metasweeper/releases/download/3.3.1/Metasweeper-3.3.1.exe](https://github.com/eee555/Metasweeper/releases/download/3.3.1/Metasweeper-3.3.1.exe)

### v3.3.0

Plugin system introduced: built-in History, LLM Controller, and XianNiUpgrade plugins. Runtime language switching (Japanese/Polish/German/English). New ZiNi metric. Replay import from previous versions + CSV export. Advanced settings panel. Bug fixes: installer language selection not applied, plugin-related exceptions, custom mode mine count not auto-adjusting, record dialog interfering with window dragging, ce/s display broken. Auto-restart disabled by default.
(No safe download available; removed)

### v3.2.2

Plugin functionality added. RMV2 replay playback supported. Fixed a critical bug where releasing inside the board after pressing on the border caused incorrect handling; fixed double-click on "cell0" not working. Optimized "About" menu. Completed missing counter operators; removed `checksum_ok` variable. Fixed an evfs security vulnerability. Added command-line replay verification tool. Cursor boundary restriction now always keeps window on top. Added menu options to open replay/settings directory.
Links:
[https://gitee.com/ee55/Metasweeper/releases/download/3.2.2/Metaminesweeper-3.2.2.exe](https://gitee.com/ee55/Metasweeper/releases/download/3.2.2/Metaminesweeper-3.2.2.exe)
[https://github.com/eee555/Metasweeper/releases/download/3.2.2/Metaminesweeper-3.2.2.exe](https://github.com/eee555/Metasweeper/releases/download/3.2.2/Metaminesweeper-3.2.2.exe)

### v3.2.1

Supports saving evfs replay sets, selecting any replay for playback, multi-select → export as evf, new *pluck* metric for luck evaluation, new *lag mode* (`[lag]` prefix), movable sub-windows, improved player with tab switching, updated to evf4, updated landmine algorithms, Enter = OK, precision to 3 decimal places, drag-and-drop replay loading, new log/sin/tan/cos/row/column/minenum functions in counter, improved country dropdown, removed transparency setting, and many bug fixes.
Links:
[https://gitee.com/ee55/Metasweeper/releases/download/3.2.1/Metaminesweeper-3.2.1.exe](https://gitee.com/ee55/Metasweeper/releases/download/3.2.1/Metaminesweeper-3.2.1.exe)
[https://github.com/eee555/Metasweeper/releases/download/3.2.1/Metaminesweeper-3.2.1.exe](https://github.com/eee555/Metasweeper/releases/download/3.2.1/Metaminesweeper-3.2.1.exe)

### v3.2.0

Installer introduced; “Speedrun Guess-free” renamed to “Classic Guess-free”; numerous bug fixes; only one taskbar window; proper blind/flag handling; auto-update module added.
Links:
[https://gitee.com/ee55/Metasweeper/releases/download/3.2.0/Metaminesweeper-3.2.0.exe](https://gitee.com/ee55/Metasweeper/releases/download/3.2.0/Metaminesweeper-3.2.0.exe)
[https://github.com/eee555/Metasweeper/releases/download/3.2.0/Metaminesweeper-3.2.0.exe](https://github.com/eee555/Metasweeper/releases/download/3.2.0/Metaminesweeper-3.2.0.exe)

### v3.1.11

Bug fixes; translatable counter titles; HiDPI support.
Link: [https://openms.top/download/Metaminesweeper-v3.1.11.zip](https://openms.top/download/Metaminesweeper-v3.1.11.zip)

### v3.1.10

Fixes for mode switching constraints, freeze in research mode, mouse settings blocking process, crash on difficulty switch during replay, incorrect probability after mis-flag, incorrect timer behavior, etc. Supports flag display during replay, unique identifier, replay saving, per-difficulty settings, double-click guessing, mouse-range restrictions.
(No safe download available; removed)

### v3.1.9

Fixes for weak guessable mines, layout issues, exception during mode switching, added “is_official” and “is_fair”, improved anti-cheat, evf3 introduced.
Link: [https://openms.top/download/Metaminesweeper-v3.1.9.zip](https://openms.top/download/Metaminesweeper-v3.1.9.zip)

### v3.1.7

Precision-related fixes, new icons, evf2 introduced.
Link: [https://eee555.lanzn.com/iQ4C11p34mqh](https://eee555.lanzn.com/iQ4C11p34mqh)

### v3.1.6

Fix for counter not updating during replay, added German/Polish, improved anti-cheat.
Link: [https://eee555.lanzouw.com/iCNsT1a7qiqj](https://eee555.lanzouw.com/iCNsT1a7qiqj)

### v3.1.5

Many bug fixes; popup system; unique PB popup; Arbiter-like mouse settings; selectable flags; 8 languages; improved screenshot probability calculation; adjustable tile pointer; dynamic constraints; counter UI improvements.
Link: [https://eee555.lanzouw.com/imY6g0w9qfha](https://eee555.lanzouw.com/imY6g0w9qfha)

### v3.1.3

6 bug fixes; internationalization (CN/EN); improved anti-cheat; reorganized directory structure; replay checksum support.
Link: [https://wwwl.lanzouw.com/i36LJ0upglmf](https://wwwl.lanzouw.com/i36LJ0upglmf)

### v3.1.1

8 bug fixes; mvf playback supported; improved anti speed-gear defenses.
Link: [https://wwwl.lanzouw.com/itjCR0p24hdc](https://wwwl.lanzouw.com/itjCR0p24hdc)

### v3.1.0_beta

Bug fixes; in-game counter with full Python syntax; auto save .evf; playback of avf/rmv/evf; guess-free supports arbitrary mine count.
Link: [https://wwwl.lanzouw.com/imdWO0joyzra](https://wwwl.lanzouw.com/imdWO0joyzra)

### v3.0.2

Fixes for 3 major game-breaking bugs.
Link: [https://wwb.lanzouw.com/iuhs904cfj0b](https://wwb.lanzouw.com/iuhs904cfj0b)

### v3.0.1

Bug fixes; Arbiter-compatible avf default-open behavior.
Link: [https://wwb.lanzouw.com/iHaNm02ane7c](https://wwb.lanzouw.com/iHaNm02ane7c)

### v3.0

Bug fixes; renamed from BlackCat Minesweeper to MetaSweeper; first third-generation replay player; avf playback; high-level event extraction; spacebar probability display during replay.
Link: [https://wwb.lanzouw.com/i8ypL026p1za](https://wwb.lanzouw.com/i8ypL026p1za)

### v2.4.2

Major refactor; bug fixes; vector UI; pre-game Ctrl+scroll to zoom; scroll to adjust mine count; preview of 3.0 rename.
Link: [https://wwb.lanzouw.com/i3Bpc01vfsab](https://wwb.lanzouw.com/i3Bpc01vfsab)

### v2.4.1

Bug fixes; UI improvements; OBR support for custom boards.
Link: [https://wwe.lanzoui.com/i5Sswsq0uva](https://wwe.lanzoui.com/i5Sswsq0uva)

### v2.3.1

Bug fixes.
Link: [https://wwe.lanzoui.com/ifH4Cryp3aj](https://wwe.lanzoui.com/ifH4Cryp3aj)

### v2.3

Bug fixes; auto restart; auto popups; post-game flagging; probability via Space; probability via Ctrl+Space + screenshot OBR.
Link: [https://wwe.lanzoui.com/i2axoq686kb](https://wwe.lanzoui.com/i2axoq686kb)

### v2.2.6-alpha

Bug fixes; algorithm improvements (200% faster guess-free 16×16×72); custom mode shortcuts (4/5/6); improved stability and board refreshing.
Links: [https://wwe.lanzoui.com/igPFFo7mwxi](https://wwe.lanzoui.com/igPFFo7mwxi)
[https://wwe.lanzous.com/igPFFo7mwxi](https://wwe.lanzous.com/igPFFo7mwxi)

### v2.2.5

Algorithm improvements (252 boards/s in advanced guess-free); major bug fixes.
Links: [https://wws.lanzoui.com/iS3wImv2y5e](https://wws.lanzoui.com/iS3wImv2y5e)
[https://wws.lanzous.com/iS3wImv2y5e](https://wws.lanzous.com/iS3wImv2y5e)

### v2.2

Algorithm improvements: 37,525 boards/s in advanced mode (~3× Arbiter), 15.7 boards/s guess-free; polar chart for skill metrics; feature cleanup.
Links: [https://wws.lanzoui.com/iq9Ocm8zdtc](https://wws.lanzoui.com/iq9Ocm8zdtc)
[https://wws.lanzous.com/iq9Ocm8zdtc](https://wws.lanzous.com/iq9Ocm8zdtc)

