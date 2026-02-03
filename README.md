# 元扫雷（Metasweeper）

**[English version is here.](README_EN.md)**

- 包含8种模式的专业扫雷版本、第三代扫雷录像播放器及高性能算法工具箱
 
[![](https://img.shields.io/github/release/eee555/Metasweeper.svg)](https://github.com/eee555/Metasweeper/releases)
[![stars](https://img.shields.io/github/stars/eee555/Metasweeper)](https://github.com/eee555/Metasweeper/stargazers)
[![forks](https://img.shields.io/github/forks/eee555/Metasweeper)](https://github.com/eee555/Metasweeper/forks)
[![](https://img.shields.io/github/downloads/eee555/Metasweeper/total.svg)](https://github.com/eee555/Metasweeper/releases)

## 简介

**元扫雷（Meta Minesweeper）**由资深扫雷专业玩家与软件工程师共同打造——不是对传统扫雷的简单重复，而是在**算法、性能、可扩展性与工具链层面**的全面现代化。

元扫雷生成的录像格式已获得[开源扫雷网](https://openms.top)官方认可，并参与国际排行榜。


## 项目优势与技术亮点

### （1）算法与引擎体系

元扫雷由`ms_toollib`工具箱赋能，核心竞争力来自后者高度优化的算法组件，构成完整的扫雷智能算法系统。

* **三大判雷引擎**：提供多层次策略推理，覆盖从简单集合到枚举法求解。
* **统一局面状态机**：将游戏局面抽象为自动状态机，提升算法集成度与可扩展性。
* **概率推断引擎**：支持计算局面中任意一格是雷的概率，求解速度仅次于JSMinesweeper。
* **光学局面识别（OBR）引擎**：可从任意扫雷应用的截屏中重建局面，实现跨游戏智能分析。

---

### （2）架构与技术栈

项目在性能、安全性、工具链友好度之间取得扎实平衡。

* **Python / PyQt5 + Rust 复合架构**：

  * Python 负责 UI、生态扩展；
  * Rust 提供核心算法计算的高性能与内存安全。
* **界面与算法完全解耦**，使 UI和工具链可独立推进。
* 完全开源的工具链 **`ms_toollib`（MIT License）**，可通过 `pip install ms_toollib` 直接安装并在其他项目中复用。

---

### （3）游戏模式与交互能力

具备目前扫雷软件生态中覆盖度最广、交互方式最现代化的功能。

* 支持 **全部 6 种无猜模式 + 标准 + Win7 模式**；弱可猜 / 强可猜模式均为独家实现。
* **Ctrl + 滚轮** 自由缩放界面尺寸，提供罕见的 UI 灵活度。
* **Space**：即时计算当前盘面每一格的雷概率。
* **Ctrl + Space**：截屏识别并对任何外部扫雷应用执行概率计算（OBR）。
* **局面筛选器**：基于自定义策略的复杂条件过滤。
* **性能指标系统**：内置 3BV/s、STNB、RQP 等指标，并支持自定义公式。

---

### （4）录像系统与生态兼容

元扫雷不仅是游戏本体，也是一套专业分析平台。

* 高级录像播放器：支持高层抽象分析，并实时呈现格子概率。
* 兼容 **avf / rmv / mvf / [evf](https://github.com/eee555/ms_toollib/blob/main/evf%E6%A0%87%E5%87%86.md)** 四大主流录像格式。
* 兼容[**evfs**](https://github.com/eee555/ms_toollib/blob/main/evfs%E6%A0%87%E5%87%86.md)录像集格式。
* 对常见作弊手段（如变速齿轮）具备对抗能力。
* 国际化支持：中文、英文、德文、波兰文等语言。

元扫雷正处于持续演进阶段，通常 **3~12 个月发布一个版本**。
欢迎提交 **Issue / PR / Star / Fork** ——您的参与将决定一个开源扫雷生态的未来走向。


## 参考连接

+ 使用教程：[https://openms.top/#/guide/[80.%E6%95%99%E7%A8%8B.%E8%BD%AF%E4%BB%B6]%E5%85%83%E6%89%AB%E9%9B%B7%E4%BD%BF%E7%94%A8%E6%95%99%E7%A8%8B](https://openms.top/#/guide/[80.%E6%95%99%E7%A8%8B.%E8%BD%AF%E4%BB%B6]%E5%85%83%E6%89%AB%E9%9B%B7%E4%BD%BF%E7%94%A8%E6%95%99%E7%A8%8B)
+ 算法工具箱地址：[https://github.com/eee555/ms_toollib](https://github.com/eee555/ms_toollib)
+ 算法工具箱文档：[https://docs.rs/ms_toollib](https://docs.rs/ms_toollib)

## 安装

操作系统：仅支持`Windows 10`或`Windows 11`。

### 方案1：通过官方下载链接安装(推荐)
在下面的[下载链接](#下载链接)中找到最新的版本，然后下载，解压，直接运行`main.exe`文件（如果警告请点击“仍然运行”），开箱即用。通过此方法安装的软件，是`正版`的软件，能够对录像文件进行官方的签名（签名功能打包在“metaminesweeper_checksum.pyd”中，占比很小，且是闭源的）。

### 方案2：通过Github Actions安装(最安全)
**请注意**：通过此方法安装的软件，不能对录像文件进行正确的签名。即，自行打包的软件，其生成的录像文件，无法通过`正版`的软件的校验。但其余功能保证与`正版`相同。  
在[Github Actions](https://github.com/eee555/Solvable-Minesweeper/actions)找到构建成功的最近一次提交，点击更新内容，在Artifacts页面可以找到打包好的文件，后面步骤同上。这个方法可以体验最新功能，能保证软件绿色安全无毒，但未发布的版本都不能保证稳定性。

### 方案3：从源码安装(不推荐)
**请注意**：通过此方法安装的软件，不能对录像文件进行正确的签名。即，自行打包的软件，其生成的录像文件，无法通过`正版`的软件的校验。但其余功能保证与`正版`相同。同时，如有需要，玩家可通过这种方式安装来自行制作改版，并自行实现秘密的签名。  
在编译之前，请确保自己拥有：
*   Python >=3.10, <=3.12（推荐3.12，即打包使用的版本）
*   会用Powershell或者其它命令行工具的能力

以下为安装步骤：
*   克隆这个仓库到本地
```sh
    git clone https://github.com/eee555/Solvable-Minesweeper.git
```

*   方案一：从pypi.org安装Python依赖（安装ms_toollib的release版本，简单但不一定成功，因为底层api可能有调整。如果不成功，需要往前翻到合适的版本，或直接联系作者）
```sh
    pip install -r requirements.txt # Windows
    pip3 install -r requirements.txt # *nix
```

*   方案二：从github安装Python依赖（安装ms_toollib的nightly版本，复杂但一定成功。复杂之处在于需要安装rust工具链）
```sh
    git clone https://github.com/eee555/ms_toollib.git
    cd ms_toollib\python_package
    cargo build --release
    将ms_toollib\python_package\target\release下的ms_toollib.dll重命名为ms_toollib.pyd，复制到Solvable-Minesweeper\src下
    安装requirements.txt中除ms_toollib外剩余的依赖
```

*   为了跑通全部功能，从下载的以往版本中找到en_US.qm、de_DE.qm、pl_PL.qm等语言文件，复制到Solvable-Minesweeper下

*   为了跑通全部功能，从下载的以往版本中找到params.onnx神经网络模型数据，复制到Solvable-Minesweeper\src下

*   运行程序，大功告成了~
```sh
    py -3 src/main.py # Windows
    python3 src/main.py # *nix
```

## 贡献

参见[CONTRIBUTING.md](https://github.com/eee555/Solvable-Minesweeper/blob/master/CONTRIBUTING.md)。

# 协议须知
项目使用了附带额外条款的GPLv3协议，尤其禁止了项目未经授权的商用行为，也规定了项目的收益分配方式。细节参见[LICENSE](LICENSE)。

## 荣誉
收录于Awesome Rust Repositories: 
[https://twitter.com/RustRepos/status/1636837781765799940](https://twitter.com/RustRepos/status/1636837781765799940)

收录于llamasweeper.com，评分4.5星：
[https://llamasweeper.com/#/others](https://llamasweeper.com/#/others)

开源扫雷网官方扫雷软件[https://openms.top](https://openms.top)

[![Star History Chart](https://api.star-history.com/svg?repos=eee555/Metasweeper&type=Date)](https://star-history.com/?repos=eee555/Metasweeper#repos=eee555/Metasweeper&eee555/Metasweeper&Date)

## 赞助
感谢您考虑支持我们的开源项目，赞助时请备注**项目名称+您的昵称+其他要求**，例如`元扫雷+张先生+建议添加**功能`。您的赞助将有助于项目的持续发展和改进，使我们能够继续提高软件的质量。此外，按照本项目协议协议，赞助得到的收入将由贡献者按commit数量的比例进行分配。

### 一般赞助者
- 一次性捐款 **￥3** 及以上
- 您的名字将永久出现在项目的贡献者列表中（按照您要求的形式）

### 重要赞助者
- 一次性捐款 **￥50** 及以上
- 一般赞助者的所有的权益
- 独家定期报告项目进展

### 核心赞助者
- 累计捐款 **￥1000** 及以上
- 重要赞助者的所有的权益
- 可行的前提下，按照您的要求来制定开发计划

![](readme_pic/微信收款码.png) ![](readme_pic/支付宝收款码.png)  


## 贡献者列表

| 赞助商 | 金额 | 时间 | 渠道 | 分配情况 |
| :------: | :-----:  | :----------: | :------: | :------: |
| *松 | ¥72.60 | 2024-04-04 | 微信 | 未分配 |
| *昌 | ¥55.00 | 2024-07-27 | 支付宝 | 未分配 |


## 下载链接

### 正式版v3.2.1：
可以保存evfs录像集，可以选择其中任意录像播放，可以多选并另存为evf文件。增加pluck指标，刻画了运气的好坏。增加迟延模式，可以在标识前增加“[lag]”，获取更宽松的作弊判定。录像播放控制、计数器等子窗口可以保存位置坐标。升级了录像播放器，可以多标签切换。将录像格式升级至evf4。调整法埋雷算法升级。回车等于窗口确定。播放器进度条时间修改为3位小数。可以通过拖入文件来进行播放。给计数器添加log, sin, tan, cos, row, column, minenum等函数和变量。优化了国家下拉框的补全交互。删除设置中的透明度属性。修复了计数器公式不能包含百分号%、回放时脸不动、窗口超出屏幕后无法移回、文件权限相关问题等已经发现的bug。  
链接：[https://gitee.com/ee55/Metasweeper/releases/download/3.2.1/Metaminesweeper-3.2.1.exe](https://gitee.com/ee55/Metasweeper/releases/download/3.2.1/Metaminesweeper-3.2.1.exe)、[https://github.com/eee555/Metasweeper/releases/download/3.2.1/Metaminesweeper-3.2.1.exe](https://github.com/eee555/Metasweeper/releases/download/3.2.1/Metaminesweeper-3.2.1.exe)

### 正式版v3.2.0：
修改为安装包安装。“竞速无猜”更名为“经典无猜”。修复了游戏开始前点“保存”会崩溃，标准模式pb不能正常保存，标雷后缩放窗口导致异常，不同缩放下窗口尺寸不同，切屏引发崩溃等问题。现在任务栏只会出现一个主窗口，能够正确处理盲扫和标雷相关的弹窗逻辑。增加了自动更新的模块，可以在游戏内选择服务器自动更新。  
链接：[https://gitee.com/ee55/Metasweeper/releases/download/3.2.0/Metaminesweeper-3.2.0.exe](https://gitee.com/ee55/Metasweeper/releases/download/3.2.0/Metaminesweeper-3.2.0.exe)、[https://github.com/eee555/Metasweeper/releases/download/3.2.0/Metaminesweeper-3.2.0.exe](https://github.com/eee555/Metasweeper/releases/download/3.2.0/Metaminesweeper-3.2.0.exe)

### 正式版v3.1.11：
修复了若干严重问题。计数器标题可以翻译。兼容高清屏。  
链接：[https://openms.top/download/Metaminesweeper-v3.1.11.zip](https://openms.top/download/Metaminesweeper-v3.1.11.zip)

### 正式版v3.1.10：
修复了快捷键切换难度后局面约束不能变化、研究模式中快捷键切换难度后卡死、鼠标设置阻塞进程、回放时切换难度崩溃等、标错雷时概率计算错误、回放时右上角时间不变化等问题。现在回放时可以显示正确的国旗。可以设置唯一性标识。录像可以回放、手动保存。每个级别的模式、尺寸可以分别保存。双击猜雷可以起作用。可以限制鼠标移动范围为游戏局面区域。  
链接：无（不安全，已下架）

### 正式版v3.1.9：

修复了7个bug，包括弱可猜模式可能踩雷；用设置修改尺寸时，布局出错；使用快捷键切换模式时，部分操作引发异常等。计数器中可以使用"is_offical", "is_fair"来检查录像合法性。提高了对某种作弊手段的防御能力。升级了录像格式到evf3。  
链接：[https://openms.top/download/Metaminesweeper-v3.1.9.zip](https://openms.top/download/Metaminesweeper-v3.1.9.zip)

### 正式版v3.1.7：

修复了因舍入导致的一些问题。设计了更美观的图标。升级了录像格式到evf2。  
链接：[https://eee555.lanzn.com/iQ4C11p34mqh](https://eee555.lanzn.com/iQ4C11p34mqh)

### 正式版v3.1.6：
修复了拖动录像进度条时，指标不变化的bug。新增德语和波兰语。提高了对某两种作弊手段的防御能力。  
链接：[https://eee555.lanzouw.com/iCNsT1a7qiqj](https://eee555.lanzouw.com/iCNsT1a7qiqj)

### 正式版v3.1.5：
修复了十几个bug。弹窗功能、独一无二的pb弹窗功能。像arbiter一样的鼠标设置，但只要点一层，而且快捷键是“M”。在设置界面可以选择国旗，可以用8种语言设置自己的国家名称。在主界面显示国旗。截屏计算概率不再像之前那样轻易闪退。截屏得到局面后，可以用滚轮修改指向的格子，修复错误的结果，雷数的上下限等都是联动的，满足一切预期。现在可以点击计数器下方的按钮来增加指标，可以删掉计数器的指标的名称从而把这条指标删掉。  
链接：[https://eee555.lanzouw.com/imY6g0w9qfha](https://eee555.lanzouw.com/imY6g0w9qfha)

### 正式版v3.1.3：
修复了6个bug。现在已经支持国际化，支持汉语和英语。提高了对某两种作弊手段的防御能力。改进了软件的架构，将有用的文件全部放到目录外层，软件本体放到目录内层。现在能够给录像添加校验码并验证录像来源。此外也精简了部分功能。  
链接：[https://wwwl.lanzouw.com/i36LJ0upglmf](https://wwwl.lanzouw.com/i36LJ0upglmf)

### 正式版v3.1.1：
修复了8个bug。现在能够播放mvf录像。提高了对变速齿轮的防御能力。  
链接：[https://wwwl.lanzouw.com/itjCR0p24hdc](https://wwwl.lanzouw.com/itjCR0p24hdc)

### 测试版v3.1.0_beta：
修复了若干bug。增添了游戏时的计数器，其表达式支持任意python语法。游戏结束后，可以自动保存.evf录像。现在能够播放avf、rmv、evf三种录像。无猜埋雷可以支持任意雷数。  
链接：[https://wwwl.lanzouw.com/imdWO0joyzra](https://wwwl.lanzouw.com/imdWO0joyzra)

### 正式版v3.0.2：
修复了3个特别影响游戏体验的bug。  
链接：[https://wwb.lanzouw.com/iuhs904cfj0b](https://wwb.lanzouw.com/iuhs904cfj0b)

### 正式版v3.0.1：
修复了两个bug。现在可以将元扫雷设置为arbiter的avf文件的默认打开方式。  
链接：[https://wwb.lanzouw.com/iHaNm02ane7c](https://wwb.lanzouw.com/iHaNm02ane7c)

### 正式版v3.0：
修复了一些bug。黑猫扫雷更名为元扫雷（MetaSweeper）。首次装载第三代录像播放器，能够播放avf录像。分析出并报告抽象的录像事件。录像播放时，按下空格键可以实时地展示每格是雷的概率。  
链接：[https://wwb.lanzouw.com/i8ypL026p1za](https://wwb.lanzouw.com/i8ypL026p1za)

### 正式版v2.4.2：
软件整体重构。修复了若干bug。ui界面开始采用矢量贴图。游戏开始前，按住ctrl并滚动滚轮可以缩放界面；对雷数滚动滚轮可以调整雷数。预告：即将升级到3.0，从3.0开始，黑猫扫雷将更名为元扫雷（Meta Sweeper）。  
链接：[https://wwb.lanzouw.com/i3Bpc01vfsab](https://wwb.lanzouw.com/i3Bpc01vfsab)

### 正式版v2.4.1：
修复了若干bug。部分优化的ui界面。光学局面识别引擎开始支持自定义局面。  
链接：[https://wwe.lanzoui.com/i5Sswsq0uva](https://wwe.lanzoui.com/i5Sswsq0uva)

### 正式版v2.3.1：
修复了若干bug。  
链接：[https://wwe.lanzoui.com/ifH4Cryp3aj](https://wwe.lanzoui.com/ifH4Cryp3aj)

### 正式版v2.3：
修复了若干bug。现在可以设置自动重开、自动弹窗、结束后标雷。按住空格键可以计算每格是雷的概率。组合键“Ctrl+空格”可以通过截图+光学局面识别（Optical Board Recognition，OBR）计算每格是雷的概率。  
链接：[https://wwe.lanzoui.com/i2axoq686kb](https://wwe.lanzoui.com/i2axoq686kb)

### 测试版v2.2.6-alpha：
修复了若干bug。算法优化：(16,16,72)无猜局面埋雷速度提高200%。新功能：快捷键4、5、6可以快速设置三种不同的自定义的自定义模式。对自定义模式的优化，提高了稳定性。对局面刷新的优化。  
链接：[https://wwe.lanzoui.com/igPFFo7mwxi](https://wwe.lanzous.com/igPFFo7mwxi)

### 正式版v2.2.5：
算法优化：高级无猜局面埋雷速度达到约252局/秒。修复了上一个版本的严重bug。  
链接：[https://wws.lanzoui.com/iS3wImv2y5e](https://wws.lanzous.com/iS3wImv2y5e)  

### 正式版v2.2：
算法优化：高级埋雷速度达到37525局/秒，相当于Arbiter的三倍左右，高级无猜局面埋雷速度15.7局/秒。游戏结束按空格可以显示实力指标的极坐标图。删去了一些无用的功能。  
链接：[https://wws.lanzoui.com/iq9Ocm8zdtc](https://wws.lanzous.com/iq9Ocm8zdtc)


