# Meta Minesweeper (Metasweeper)

**[中文版本在此](README.md)**

* A professional Minesweeper suite featuring 8 gameplay modes, a third-generation replay player, and a high-performance algorithm toolbox.

[![](https://img.shields.io/github/release/eee555/Metasweeper.svg)](https://github.com/eee555/Metasweeper/releases)
[![stars](https://img.shields.io/github/stars/eee555/Metasweeper)](https://github.com/eee555/Metasweeper/stargazers)
[![forks](https://img.shields.io/github/forks/eee555/Metasweeper)](https://github.com/eee555/Metasweeper/forks)
[![](https://img.shields.io/github/downloads/eee555/Metasweeper/total.svg)](https://github.com/eee555/Metasweeper/releases)

## Introduction

**Meta Minesweeper** is developed by experienced professional Minesweeper players and software engineers. It is not a simple clone of traditional Minesweeper, but a complete modernization in **algorithms, performance, extensibility, and tooling**.

Its replay formats are officially recognized by the [Open Minesweeper Network](https://openms.top) and included in international leaderboards.

## Key Advantages & Technical Highlights

### (1) Algorithm & Engine System

Powered by the `ms_toollib` toolbox, Meta Minesweeper’s core strength comes from its highly optimized algorithm components that form a complete intelligent Minesweeper system.

* **Three inference engines**: multi-layered solving strategies from set-based deduction to full enumeration.
* **Unified board state machine**: abstracts the game board into a formal automaton, improving algorithm composability and extensibility.
* **Probability inference engine**: computes the probability of any tile containing a mine, with speed second only to JSMinesweeper.
* **Optical Board Recognition (OBR)**: reconstructs board states from screenshots of *any* Minesweeper application for cross-software intelligent analysis.

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
* **Performance metrics**: built-in 3BV/s, STNB, RQP, and custom formulas.

---

### (4) Replay System & Ecosystem Compatibility

Meta Minesweeper is not just a game but a full analysis platform.

* Advanced replay player with high-level analysis and real-time probabilities.
* Supports **avf / rmv / mvf / [evf](https://github.com/eee555/ms_toollib/blob/main/evf标准.md)** formats.
* Supports **[evfs](https://github.com/eee555/ms_toollib/blob/main/evfs标准.md)** replay-set format.
* Resistant to common cheating methods (e.g., speed-gear tools).
* Internationalization: Chinese, English, German, Polish, etc.

Meta Minesweeper is actively developed and typically releases **every 3–12 months**.
Issues, PRs, stars, and forks are all welcome.

### Reference Links

* User Guide: [https://openms.top/#/guide/[80.%E6%95%99%E7%A8%8B.%E8%BD%AF%E4%BB%B6]%E5%85%83%E6%89%AB%E9%9B%B7%E4%BD%BF%E7%94%A8%E6%95%99%E7%A8%8B](https://openms.top/#/guide/[80.%E6%95%99%E7%A8%8B.%E8%BD%AF%E4%BB%B6]%E5%85%83%E6%89%AB%E9%9B%B7%E4%BD%BF%E7%94%A8%E6%95%99%E7%A8%8B)
* Algorithm Toolbox: [https://github.com/eee555/ms_toollib](https://github.com/eee555/ms_toollib)
* Toolbox Documentation: [https://docs.rs/ms_toollib](https://docs.rs/ms_toollib)

## Installation

Supported OS: **Windows 10 / Windows 11 only**

### Option 1: Install via Official Download (Recommended)

Find the latest version in the [download section](#下载链接), unzip it, and run `main.exe` directly (click “Run anyway” if prompted).
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
|  *Song  | ¥72.60 | 2024-04-04 |  WeChat |    Pending   |
|  *Chang | ¥55.00 | 2024-07-27 |  Alipay |    Pending   |

## Download Links

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

