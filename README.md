# 元扫雷（Metasweeper）
- 包含8种模式的专业扫雷版本、第三代扫雷录像播放器及高性能算法工具箱
- project with 8 modes of minesweeper, third generation minesweeper video player and high performance algorithm toolbox
 
[![MetaSweeper](https://img.shields.io/badge/MetaSweeper-v3.2.0-brightgreen.svg)](https://github.com/eee555/Solvable-Minesweeper)
[![stars](https://img.shields.io/github/stars/eee555/Solvable-Minesweeper)](https://github.com/eee555/Solvable-Minesweeper/stargazers)
[![forks](https://img.shields.io/github/forks/eee555/Solvable-Minesweeper)](https://github.com/eee555/Solvable-Minesweeper/forks)


## 简介

**元扫雷**是由专业玩家玩家开发的扫雷游戏。这个项目并非简单重复已有的工作，而是集中了一批扫雷游戏的现代化设计。元扫雷所生成的游戏录像得到[开源扫雷网](openms.top)的承认并参与世界排名。

优势：

+ 内部集成了**三大判雷引擎+集成的局面状态机+概率计算引擎+光学局面识别（Optical Board Recognition，OBR）引擎**，具备性能优势。

+ 采用Python/PyQt5及Rust编写，模块间相互配合、融为一体，兼顾**开发效率、内存安全与执行速度**。游戏界面与算法高度分离，自研的工具箱同样开源，且遵循更为宽松的MIT协议，通过`pip install ms_toollib`命令即可安装。

+ 游戏模式方面，具有**全部6种无猜扫雷模式+标准+win7**，弱可猜、强可猜的模式都是绝无仅有的。

+ 外观上它只是一款普通的标准扫雷，但它能通过按住ctrl并滚动滚轮任意**调整大小**，能调整窗口的**透明度**。这是罕见的。

+ 按下“空格”计算局面中每一格是雷的概率。这是罕见的。

+ 按下“ctrl+空格”能**截屏识别**计算其他扫雷中每一格是雷的概率。这是绝无仅有的。

+ 其装载的录像播放器可以分析录像的高层抽象特征，并实时展示游戏局面中每一格是雷的概率。这是绝无仅有的。能够播放avf、rmv、mvf、evf四种主流格式的录像。这是罕见的。

+ 能够计算3BV/s、STNB、RQP等指标并展示，能够自定义公式。这是罕见的。

+ 完备的局面筛选功能，按用户配置来筛选。这是罕见的。

+ 对变速齿轮等多种作弊手段的防御能力。

+ 国际化，包括中、英、德、波兰等语言。

目前属于漫长的开发阶段中，约1~3月更新一个版本，欢迎提issue、star、pull request、fork。

## Introduction

Minesweeper is a mineswering game developed by players who are passionate about the game. This project is not a simple repetition of existing work, but a concentration of modern design elements for minesweeper games.

Advantages:

+ It **internally integrates three major mine-judging engines, an integrated board state machine, a probability calculation engine, and an Optical Board Recognition (OBR) engine**, offering performance advantages.

+ Written using Python/PyQt5 and Rust, the modules cooperate with each other and are integrated into one, balancing **development efficiency, memory safety, and execution speed**. The game interface is highly separated from the algorithms, and the self-developed toolbox is also open-source, following a more permissive MIT license, which can be installed via the command `pip install ms_toollib`.

+ In terms of game modes, it features **all six no-guess minesweeper modes, standard, and win7**, with unique modes for both weak and strong guesswork.

+ Aesthetically, it appears as a standard minesweeper, but it can **adjust its size** by holding down the ctrl key and scrolling the wheel, and adjust the **transparency** of the window. This is rare.

+ Pressing "space" calculates the probability of each cell being a mine in the board. This is rare.

+ Pressing "ctrl+space" enables **screenshot recognition** to calculate the probability of each cell being a mine in other minesweeper games. This is unique.

+ Its built-in video player can analyze high-level abstract features of recordings and display the probability of each cell being a mine in real-time. This is unique. It can play four mainstream formats of recordings: avf, rmv, mvf, and evf. This is rare.

+ It can calculate and display metrics such as 3BV/s, STNB, RQP, and allows for custom formulas. This is rare.

+ Comprehensive board filtering capabilities, configurable by the user. This is rare.

+ Defense capabilities against various cheating methods, including speed changers.

+ Internationalization, including languages such as Chinese, English, German, Polish, and more.

Currently in the lengthy development phase, with updates approximately every 1 to 3 months, we welcome issues, stars, pull requests, and forks.

### 开发计划

+ 使用教程：[https://openms.top/#/guide/[80.%E6%95%99%E7%A8%8B.%E8%BD%AF%E4%BB%B6]%E5%85%83%E6%89%AB%E9%9B%B7%E4%BD%BF%E7%94%A8%E6%95%99%E7%A8%8B](https://openms.top/#/guide/[80.%E6%95%99%E7%A8%8B.%E8%BD%AF%E4%BB%B6]%E5%85%83%E6%89%AB%E9%9B%B7%E4%BD%BF%E7%94%A8%E6%95%99%E7%A8%8B)
+ 算法工具箱地址：[https://github.com/eee555/ms_toollib](https://github.com/eee555/ms_toollib)
+ 算法工具箱文档：[https://docs.rs/ms_toollib](https://docs.rs/ms_toollib)

## 安装
建议在`Windows 10`或`Windows 11`下运行本游戏，其它操作系统未经测试，可能出现意想不到的问题。

### 方案1：通过官方下载链接安装(推荐)
在下面的[下载链接](#下载链接)中找到最新的版本，然后下载，解压，直接运行`main.exe`文件（如果警告请点击“仍然运行”），开箱即用。通过此方法安装的软件，是`正版`的软件，能够对录像文件进行官方的签名（签名功能打包在“metaminesweeper_checksum.pyd”中，占比很小，且是闭源的）。

### 方案2：通过Github Actions安装(最安全)
**请注意**：通过此方法安装的软件，不能对录像文件进行正确的签名。即，自行打包的软件，其生成的录像文件，无法通过`正版`的软件的校验。但其余功能保证与`正版`相同。  
在[Github Actions](https://github.com/eee555/Solvable-Minesweeper/actions)找到构建成功的最近一次提交，点击更新内容，在Artifacts页面可以找到打包好的文件，后面步骤同上。这个方法可以体验最新功能，能保证软件绿色安全无毒，但未发布的版本都不能保证稳定性。

### 方案3：从源码安装(不推荐)
**请注意**：通过此方法安装的软件，不能对录像文件进行正确的签名。即，自行打包的软件，其生成的录像文件，无法通过`正版`的软件的校验。但其余功能保证与`正版`相同。同时，如有需要，玩家可通过这种方式安装来自行制作改版，并自行实现秘密的签名。  
在编译之前，请确保自己拥有：
*   Python >=3.7, <=3.11（推荐3.10，即打包使用的版本）
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

## 实现原理

（还没写，计划弄出3.5以后回头来写）

## 贡献

[CONTRIBUTING.md](https://github.com/eee555/Solvable-Minesweeper/blob/master/CONTRIBUTING.md)

## 荣誉
被收录于Awesome Rust Repositories: 
[https://twitter.com/RustRepos/status/1636837781765799940](https://twitter.com/RustRepos/status/1636837781765799940)

开源扫雷网官方扫雷软件[https://openms.top](https://openms.top)

## 赞助
感谢您考虑支持我们的开源项目，赞助时请备注您的称呼（或Github主页）。您的赞助将有助于项目的持续发展和改进，使我们能够继续提高软件的质量（owner许诺向所有contributor按获得赞助时commit数量的比例分配赞助得到的收入）。 

### 一般赞助者
- 一次性捐款￥10或以上
- 您的名字将出现在项目的贡献者列表中

### 高级赞助者
- 一次性捐款￥50或以上
- 您的名字将出现在项目的贡献者列表中
- 独家定期报告项目进展  

![](readme_pic/微信收款码.png) ![](readme_pic/支付宝收款码.png)  


## 贡献者列表

| 赞助商 | 金额 | 时间 | 渠道 | 分配情况 |
| :------: | :-----:  | :----------: | :------: | :------: |
| *松 | ¥72.60 | 2024-04-04 | 微信 | 未分配 |
| *昌 | ¥55.00 | 2024-07-27 | 支付宝 | 未分配 |


## 下载链接

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

修复了7个bug，包括弱可猜模式可能踩雷；用设置修改尺寸时，布局出错；使用快捷键切换模式时，部分操作引发异常等。计数器中可以使用"is_offical", "is_fair"来检查录像合法性。提高了对某种作弊手段的防御能力。升级了录像格式到evf-v0.3。  
链接：[https://openms.top/download/Metaminesweeper-v3.1.9.zip](https://openms.top/download/Metaminesweeper-v3.1.9.zip)

### 正式版v3.1.7：

修复了因舍入导致的一些问题。设计了更美观的图标。升级了录像格式到evf-v0.2。  
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


