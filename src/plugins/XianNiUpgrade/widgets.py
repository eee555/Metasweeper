"""
修仙升级界面组件
"""

from __future__ import annotations

import struct
from datetime import datetime
from pathlib import Path

_XOR_KEY = b"XianNiAssetKey2026!"

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QGroupBox, QHeaderView, QProgressBar,
    QFrame, QAbstractItemView, QPushButton, QFileDialog,
    QMessageBox, QDialog, QLineEdit, QTextBrowser, QDialogButtonBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QCoreApplication, QTimer

_translate = QCoreApplication.translate
from PyQt5.QtGui import QPixmap, QResizeEvent, QPainter, QShowEvent

from .config import DEFAULT_API_URL
from .models import LEVEL_NAMES, LEVEL_LABELS, MODE_LABELS


class AspectLabel(QLabel):
    """按物理像素缩放仙躯图，保证清晰"""

    ASPECT = 688 / 1024

    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw: bytes | None = None

    def set_raw(self, data: bytes | None):
        self._raw = data
        self._update_pixmap()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        h = self.height()
        if h > 0:
            self.setFixedWidth(int(h * self.ASPECT))
        self._update_pixmap()

    def _update_pixmap(self):
        if not self._raw:
            super().setPixmap(QPixmap())
            return
        try:
            src = QPixmap()
            if not src.loadFromData(self._raw):
                super().setPixmap(QPixmap())
                return
            dpr = self.devicePixelRatioF()
            pw = int(self.width() * dpr)
            ph = int(self.height() * dpr)
            if pw <= 0 or ph <= 0:
                return
            scaled = src.scaled(pw, ph, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            canvas = QPixmap(pw, ph)
            canvas.fill(Qt.transparent)
            p = QPainter(canvas)
            x = (pw - scaled.width()) // 2
            y = (ph - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
            p.end()
            canvas.setDevicePixelRatio(dpr)
            super().setPixmap(canvas)
        except Exception:
            super().setPixmap(QPixmap())


class AbsorbDialog(QDialog):
    """吸收灵气对话框：选择校验程序+录像目录后直接确认"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle(_translate("Form", "吸收灵气"))
        self.resize(500, 210)
        layout = QVBoxLayout(self)

        sep_old = QLabel(_translate("Form", "━━━ 元扫雷 3.2.2 ━━━"))
        sep_old.setStyleSheet("color: #9E9E9E; font-size: 11px; font-weight: bold;")
        layout.addWidget(sep_old)

        exe_row = QHBoxLayout()
        self._exe_edit = QLineEdit()
        self._exe_edit.setPlaceholderText(_translate("Form", "选择验证法器..."))
        browse_exe = QPushButton(_translate("Form", "浏览"))
        browse_exe.clicked.connect(self._browse_exe)
        exe_row.addWidget(QLabel(_translate("Form", "验证法器:")))
        exe_row.addWidget(self._exe_edit)
        exe_row.addWidget(browse_exe)
        layout.addLayout(exe_row)

        replay_row = QHBoxLayout()
        self._replay_edit = QLineEdit()
        self._replay_edit.setPlaceholderText(_translate("Form", "选择灵箓目录..."))
        browse_replay = QPushButton(_translate("Form", "浏览"))
        browse_replay.clicked.connect(self._browse_replay)
        replay_row.addWidget(QLabel(_translate("Form", "灵箓目录:")))
        replay_row.addWidget(self._replay_edit)
        replay_row.addWidget(browse_replay)
        layout.addLayout(replay_row)

        sep_new = QLabel(_translate("Form", "━━━ 元扫雷 3.3.1+ ━━━"))
        sep_new.setStyleSheet("color: #9E9E9E; font-size: 11px; font-weight: bold;")
        layout.addWidget(sep_new)

        save_row = QHBoxLayout()
        self._save_edit = QLineEdit()
        self._save_edit.setPlaceholderText(_translate("Form", "选择道藏目录..."))
        browse_save = QPushButton(_translate("Form", "浏览"))
        browse_save.clicked.connect(self._browse_save_dir)
        save_row.addWidget(QLabel(_translate("Form", "导入道行存档:")))
        save_row.addWidget(self._save_edit)
        save_row.addWidget(browse_save)
        layout.addLayout(save_row)

        hint = QLabel(_translate("Form", "提示：请选择旧版安装目录下 data/plugin_data/XianNiUpgrade/ 文件夹"))
        hint.setStyleSheet("color: #9E9E9E; font-size: 10px;")
        layout.addWidget(hint)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton(_translate("Form", "确认"))
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(_translate("Form", "取消"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _browse_exe(self):
        path, _ = QFileDialog.getOpenFileName(self, _translate("Form", "选择验证法器"), "", _translate("Form", "法器 (*.exe);;所有文件 (*)"))
        if path:
            self._exe_edit.setText(path)

    def _browse_replay(self):
        path = QFileDialog.getExistingDirectory(self, _translate("Form", "选择灵箓目录"))
        if path:
            self._replay_edit.setText(path)

    def _browse_save_dir(self):
        path = QFileDialog.getExistingDirectory(self, _translate("Form", "选择道藏目录"))
        if path:
            self._save_edit.setText(path)

    def get_paths(self) -> tuple[str, str]:
        return self._exe_edit.text().strip(), self._replay_edit.text().strip()

    def get_save_dir(self) -> str:
        return self._save_edit.text().strip()


class RulesDialog(QDialog):
    """天地法则——用法与规则说明"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_translate("Form", "天地法则"))
        self.resize(660, 520)
        layout = QVBoxLayout(self)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet(
            "QTextBrowser { font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif; "
            "font-size: 13px; background: #FEFEFE; padding: 12px; }"
        )
        browser.setHtml(self._build_content())
        layout.addWidget(browser)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)

    @staticmethod
    def _build_content() -> str:
        rank_url = DEFAULT_API_URL
        return _translate("Form", """\
<style>
h2 { color: #6A1B9A; border-bottom: 2px solid #CE93D8; padding-bottom: 4px; }
h3 { color: #8E24AA; margin-top: 16px; }
b { color: #4A148C; }
code { background: #F3E5F5; padding: 1px 4px; border-radius: 2px; }
ul { margin: 4px 0; }
li { margin: 2px 0; }
ol { margin: 4px 0; padding-left: 22px; }
table { border-collapse: collapse; margin: 8px 0; }
td, th { border: 1px solid #E1BEE7; padding: 4px 10px; text-align: center; }
th { background: #F3E5F5; color: #6A1B9A; }
</style>

<div style="color:#4A148C; font-style:italic; font-size:14px; line-height:1.8; padding:12px 16px; border-radius:6px; margin-bottom:16px;">
<p style="margin:8px 0;">顺则凡，逆则仙，只在心中一念间。<br>
吾辈修士，逆天而行，与天争命。</p>
<p style="margin:8px 0;">扫雷一途，亦如修道——<br>
步步惊心，一念生，一念死；<br>
勘破迷障，洞悉本源，方得超脱。</p>
<p style="margin:8px 0;">今有《仙逆》之法则，立此天地道统：<br>
胜则增道行，积修为，破境界，证长生；<br>
败则归凡尘，从头越，砺道心。</p>
<p style="margin:8px 0; text-align:right;">—— 道不可须臾离也</p>
</div>

<h2>📜 天地法则 · 修仙要义</h2>

<h3>一、道行修为</h3>
<p>每局<b>扫雷胜利</b>（游戏状态转为胜利）后获得道行经验。经验累计提升境界等级，共<b>100级</b>：</p>
<table>
<tr><th>等级</th><th>境界名称</th></tr>
<tr><td>Lv.0</td><td>凡人</td></tr>
<tr><td>Lv.1-15</td><td>凝气一层 ~ 凝气十五层</td></tr>
<tr><td>Lv.16-19</td><td>筑基初期 ~ 筑基大圆满</td></tr>
<tr><td>Lv.20-23</td><td>结丹初期 ~ 结丹大圆满</td></tr>
<tr><td>Lv.24-27</td><td>元婴初期 ~ 元婴大圆满</td></tr>
<tr><td>Lv.28-31</td><td>化神初期 ~ 化神大圆满</td></tr>
<tr><td>Lv.32-35</td><td>婴变初期 ~ 婴变大圆满</td></tr>
<tr><td>Lv.36-39</td><td>问鼎初期 ~ 问鼎大圆满</td></tr>
<tr><td>Lv.40-41</td><td>阴虚 ~ 阳实</td></tr>
<tr><td>Lv.42-45</td><td>窥涅初期 ~ 窥涅大圆满</td></tr>
<tr><td>Lv.46-49</td><td>净涅初期 ~ 净涅大圆满</td></tr>
<tr><td>Lv.50-53</td><td>碎涅初期 ~ 碎涅大圆满</td></tr>
<tr><td>Lv.54-58</td><td>天人一衰 ~ 天人五衰</td></tr>
<tr><td>Lv.59-62</td><td>空涅初期 ~ 空涅大圆满</td></tr>
<tr><td>Lv.63-66</td><td>空灵初期 ~ 空灵大圆满</td></tr>
<tr><td>Lv.67-79</td><td>空玄初期 ~ 空玄九劫</td></tr>
<tr><td>Lv.80-83</td><td>空劫初期 ~ 空劫大圆满</td></tr>
<tr><td>Lv.84-88</td><td>大尊 ~ 大天尊</td></tr>
<tr><td>Lv.89-100</td><td>踏天一桥 ~ 煌天境</td></tr>
</table>

<h3>二、经验计算公式</h3>

<p><b>基础经验</b>（所有模式/难度均有效）：</p>
<ul>
<li>若雷密度 ≤ 80％（标准/Win7/弱无猜）或 ≤ 30％（经典无猜/强无猜）：<br>
  <code>基础 = k × 1.08^(雷数/格数 × 341) × min(行,列)^1.2 × max(行,列)^1.6 / 17411</code></li>
<li>其余情况：基础 = 0</li>
<li>k 为模式系数：标准=1、Win7=0.8、经典无猜=0.2、强无猜=0.25、弱无猜=2，其他=0（无经验）</li>
</ul>

<p><b>稀有局面经验</b>（仅标准模式·标准难度）：</p>
<ul>
<li>统计 3BV、Op、Isl、Cell1~Cell8 共 11 个指标在分布中的罕见程度</li>
<li>对每个指标，取 <code>p = min(P(X≤v), P(X≥v))</code>（双向累积概率），<br>
  累加 <code>(0.5 / p)^1.2</code></li>
<li>高级：<code>稀有经验 = 累加值</code>；中级：<code>累加值 / 8</code>；初级：<code>累加值 / 100</code></li>
</ul>

<p><b>竞速经验</b>（仅标准模式·标准难度）：</p>
<ul>
<li>初级：<code>(1/100) × (10/rtime)^3.5</code></li>
<li>中级：<code>(1/8) × (60/rtime)^3.5</code></li>
<li>高级：<code>(240/rtime)^3.5</code></li>
</ul>

<p><b>效率经验</b>（仅标准模式·标准难度）：</p>
<ul>
<li>效率指标 <code>IOE = 3BV / (lefts + rights + chordings)</code></li>
<li>初级：IOE ≥ 0.95 时 <code>IOE^3.5</code></li>
<li>中级：IOE ≥ 0.9 时 <code>10 × IOE^4</code>（标雷）/ <code>20 × IOE^5</code>（盲扫）</li>
<li>高级：IOE ≥ 0.8 时 <code>1 × IOE^20</code>（标雷）/ <code>1200 × IOE^50</code>（盲扫）</li>
</ul>

<p><b>总经验</b> = 基础 + 稀有 + 竞速 + 效率，上限 99999/局。</p>

<h3>三、多修分身</h3>
<p>插件支持<b>多玩家标识</b>。每局游戏会根据主标识独立计算等级和道行。修改标识将自动切换对应玩家各自的修行数据。</p>

<h3>四、吸收灵气</h3>
<p>可通过导入其他扫雷版本的录像获得经验：</p>
<ol>
<li>点击「吸收灵气」按钮</li>
<li>选择对应版本的 <b>exe 校验程序</b>（如 metasweeper.exe）</li>
<li>选择 <b>录像目录</b>（replay 文件夹）</li>
<li>插件自动校验 exe MD5 → 运行 exe 生成报告 → 解析有效录像 → 去重后加经验</li>
</ol>
<p>目前支持的版本：</p>
<table>
<tr><th>版本</th><th>MD5</th></tr>
<tr><td>Metasweeper 3.2.2</td><td><code>3271d11bab9afc8b0a2b9546e13d46cd</code></td></tr>
</table>

<h3>五、存档说明</h3>
<p>存档文件 <code>player_data.dat</code> 保存在插件数据目录，包含多玩家信息、修行日志和已导入录像记录（最多保存 1000 条）。不可轻易删除，否则只能在下个版本中用“吸收灵气”重新导入录像。</p>

<h3>六、排行榜</h3>
<p>排行榜地址：<a href="{rank_url}">{rank_url}</a></p>

<h3>第一步：改游戏玩家标识</h3>
<ol>
<li>打开主进程「<b>设置</b>」→「<b>游戏设置</b>」→「<b>标识</b>」</li>
<li>默认「匿名玩家」<b>不能上榜</b>，请先改成你自己的标识</li>
<li>在开源扫雷网个人主页「概览」底部<b>添加并绑定</b>相同标识</li>
</ol>

<h3>第二步：上传方式</h3>
<ul>
<li><b>手动</b>：点击「<b>上传排行</b>」按钮</li>
<li><b>自动</b>：设置里勾选「<b>自动上传排行</b>」→ 每局公平胜利后静默上传</li>
<li>首次实际上传时会自动生成「<b>上传令牌</b>」并保存到设置</li>
<li>手动上传时，可设置「<b>上传成功后打开排行榜页</b>」</li>
</ul>

<h3>务必注意</h3>
<ul>
<li>须启用插件管理器中的「<b>SaoleiWebsite</b>」插件以解析网内昵称</li>
<li><b>换电脑</b>须在设置里点「复制」拷贝「上传令牌」，粘贴到新电脑设置，否则无法继续更新同一标识</li>
<li>建议生成后立即点「<b>复制</b>」备份；如果不慎丢失，可加入开源扫雷网公测群（群号832072126）联系管理员找回</li>
<li>令牌丢失则无法覆盖已有排行记录</li>
</ul>
""").replace("{rank_url}", rank_url)


class LevelDisplay(QWidget):
    """等级和仙躯形象展示区"""

    absorb_clicked = pyqtSignal()
    law_clicked = pyqtSignal()
    upload_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 左侧：等级信息
        info_frame = QFrame()
        info_frame.setStyleSheet("QFrame { background: white; padding: 8px; }")
        info_frame.setMinimumWidth(400)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(4)

        self._player_label = QLabel("")
        self._player_label.setStyleSheet("color: #01579B; font-size: 15px; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif;")
        self._player_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self._player_label)

        self._rank_label = QLabel(_translate("Form", "凡人"))
        self._rank_label.setStyleSheet("color: #01579B; font-size: 28px; font-weight: bold; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif;")
        self._rank_label.setAlignment(Qt.AlignCenter)
        self._rank_label.setWordWrap(True)
        info_layout.addWidget(self._rank_label)

        self._level_label = QLabel("Lv.0")
        self._level_label.setStyleSheet("color: #0277BD; font-size: 16px; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif;")
        self._level_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self._level_label)

        self._total_xp_label = QLabel(_translate("Form", "修为: 0"))
        self._total_xp_label.setStyleSheet("color: #0288D1; font-size: 14px; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif;")
        self._total_xp_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self._total_xp_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFixedHeight(26)
        self._progress.setStyleSheet(
            "QProgressBar { border: none; "
            " background: #BBDEFB; text-align: center; font-size: 11px; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            " stop:0 #42A5F5, stop:1 #1E88E5);}"
        )
        info_layout.addWidget(self._progress)

        btn_row = QHBoxLayout()
        self._law_btn = QPushButton(_translate("Form", "天地法则"))
        self._law_btn.setFixedHeight(22)
        self._law_btn.setCursor(Qt.PointingHandCursor)
        self._law_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #AB47BC; border: none; "
            "font-size: 12px; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif; }"
            "QPushButton:hover { color: #8E24AA; }"
        )
        self._law_btn.clicked.connect(self.law_clicked.emit)
        btn_row.addWidget(self._law_btn)

        self._absorb_btn = QPushButton(_translate("Form", "吸收灵气"))
        self._absorb_btn.setFixedHeight(22)
        self._absorb_btn.setCursor(Qt.PointingHandCursor)
        self._absorb_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #64B5F6; border: none; "
            "font-size: 12px; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif; }"
            "QPushButton:hover { color: #42A5F5; }"
        )
        self._absorb_btn.clicked.connect(self.absorb_clicked.emit)
        btn_row.addWidget(self._absorb_btn)

        self._upload_btn = QPushButton(_translate("Form", "上传排行"))
        self._upload_btn.setFixedHeight(22)
        self._upload_btn.setCursor(Qt.PointingHandCursor)
        self._upload_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #26A69A; border: none; "
            "font-size: 12px; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif; }"
            "QPushButton:hover { color: #00897B; }"
            "QPushButton:disabled { color: #BDBDBD; }"
        )
        self._upload_btn.clicked.connect(self.upload_clicked.emit)
        btn_row.addWidget(self._upload_btn)
        info_layout.addLayout(btn_row)

        layout.addWidget(info_frame, stretch=1)

        # 右侧：仙躯形象
        self._image_label = AspectLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setStyleSheet(
            "QLabel { background: #E1F5FE; "
            " border: 2px solid #4FC3F7; color: #0277BD; font-size: 14px; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif; }"
        )
        self._image_label.setText(_translate("Form", "等待仙躯\n形象加载..."))
        layout.addWidget(self._image_label)

    def retranslateUi(self):
        self._law_btn.setText(_translate("Form", "天地法则"))
        self._absorb_btn.setText(_translate("Form", "吸收灵气"))
        self._upload_btn.setText(_translate("Form", "上传排行"))
        self._image_label.setText(_translate("Form", "等待仙躯\n形象加载..."))

    def set_upload_enabled(self, enabled: bool):
        self._upload_btn.setEnabled(enabled)

    def set_image(self, raw_bytes: bytes | None):
        if raw_bytes:
            self._image_label.set_raw(raw_bytes)
            return
        self._image_label.set_raw(None)
        self._image_label.setText(_translate("Form", "暂无仙躯\n形象"))

    def update_info(self, player_name: str, rank: str, level: int, total_xp: int, xp_curr: int, xp_need: int):
        self._player_label.setText(player_name)
        self._rank_label.setText(rank)
        self._level_label.setText(f"Lv.{level}")
        self._total_xp_label.setText(_translate("Form", "修为: %1").replace("%1", str(total_xp)))
        if xp_need > 0:
            pct = min(xp_curr * 100 // xp_need, 100)
            self._progress.setValue(pct)
            self._progress.setFormat(_translate("Form", "%1% | 还需 %2 道行").replace("%1", str(pct)).replace("%2", str(xp_need - xp_curr)))
        else:
            self._progress.setValue(100)
            self._progress.setFormat(_translate("Form", "已圆满"))


class XianNiUpgradeUI(QWidget):
    """修仙升级主界面"""

    _signal_update = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_dir: Path | None = None
        self._assets: dict[int, bytes] = {}
        self._validate_cb = None
        self._absorb_cb = None
        self._validate_save_cb = None
        self._absorb_save_cb = None
        self._upload_cb = None
        self._first_visible_cb = None
        self._first_visible_scheduled = False
        self._setup_ui()
        self._signal_update.connect(self._do_update)

    def set_absorb_callbacks(self, validate_cb, absorb_cb):
        self._validate_cb = validate_cb
        self._absorb_cb = absorb_cb

    def set_save_callbacks(self, validate_cb, absorb_cb):
        self._validate_save_cb = validate_cb
        self._absorb_save_cb = absorb_cb

    def set_upload_callback(self, cb):
        self._upload_cb = cb

    def set_first_visible_callback(self, cb):
        self._first_visible_cb = cb

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if (
            self._first_visible_cb
            and not self._first_visible_scheduled
            and self.isVisible()
        ):
            self._first_visible_scheduled = True
            # 勿在 showEvent 栈内同步 exec_()；延迟到布局/绘制完成后再弹
            QTimer.singleShot(150, self._invoke_first_visible_cb)

    def _invoke_first_visible_cb(self) -> None:
        cb = self._first_visible_cb
        if cb is None or not self.isVisible():
            return
        cb()

    def set_upload_enabled(self, enabled: bool):
        self._level_display.set_upload_enabled(enabled)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self._level_display = LevelDisplay()
        self._level_display.setStyleSheet("margin-bottom: 4px;")
        self._level_display.absorb_clicked.connect(self._on_absorb_clicked)
        self._level_display.law_clicked.connect(self._on_law_clicked)
        self._level_display.upload_clicked.connect(self._on_upload_clicked)
        layout.addWidget(self._level_display, 3)

        self._log_group = QGroupBox(_translate("Form", "修行日志"))
        self._log_group.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif; }")
        group_layout = QVBoxLayout(self._log_group)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setMinimumHeight(130)
        self._table.setStyleSheet("QTableWidget { font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif; } QTableWidget::item { border-bottom: 1px solid #E0E0E0; } QHeaderView::section { font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif; border: none; }")
        self._table.setShowGrid(False)
        self._table.setHorizontalHeaderLabels([_translate("Form", "时刻"), _translate("Form", "境阶"), _translate("Form", "法式"), _translate("Form", "耗时"), _translate("Form", "衍数"), _translate("Form", "道行")])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self._table.setColumnWidth(0, 150)
        for c in range(1, 6):
            self._table.horizontalHeader().setSectionResizeMode(c, QHeaderView.Stretch)
        self._table.verticalHeader().setDefaultSectionSize(22)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        group_layout.addWidget(self._table)

        layout.addWidget(self._log_group, 2)

    def retranslateUi(self):
        self._log_group.setTitle(_translate("Form", "修行日志"))
        self._table.setHorizontalHeaderLabels([
            _translate("Form", "时刻"),
            _translate("Form", "境阶"),
            _translate("Form", "法式"),
            _translate("Form", "耗时"),
            _translate("Form", "衍数"),
            _translate("Form", "道行"),
        ])
        self._level_display.retranslateUi()

    def set_image_dir(self, image_dir: Path):
        self._image_dir = image_dir
        self._assets.clear()
        fp = image_dir / "assets.dat"
        if fp.exists():
            try:
                raw = bytearray(fp.read_bytes())
                for j in range(len(raw)):
                    raw[j] ^= _XOR_KEY[j % len(_XOR_KEY)]
                raw = bytes(raw)
                count = struct.unpack_from('>I', raw, 0)[0]
                off = 4
                for i in range(count):
                    length = struct.unpack_from('>I', raw, off)[0]
                    off += 4
                    self._assets[i + 1] = raw[off:off + length]
                    off += length
            except Exception:
                self._assets.clear()

    def _on_upload_clicked(self):
        if not self._upload_cb:
            QMessageBox.warning(self, _translate("Form", "提示"), _translate("Form", "插件未就绪"))
            return
        self.set_upload_enabled(False)
        self._upload_cb()

    def _on_law_clicked(self):
        dialog = RulesDialog(self)
        dialog.exec_()

    def _on_absorb_clicked(self):
        if not self._validate_cb or not self._absorb_cb:
            QMessageBox.warning(self, _translate("Form", "提示"), _translate("Form", "插件未就绪"))
            return
        dialog = AbsorbDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return

        msgs = []
        total_gained = 0

        # ── 方式一：3.2.2 录像吸收 ──
        exe_path, replay_path = dialog.get_paths()
        if exe_path and replay_path:
            preview = self._validate_cb(exe_path, replay_path)
            if preview is None:
                msgs.append(_translate("Form", "3.2.2 验证失败，查看日志"))
            elif not preview["new_files"]:
                msgs.append(_translate("Form", "3.2.2 没有新的灵箓"))
            else:
                gained = self._absorb_cb(preview)
                total_gained += gained
                msgs.append(_translate("Form", "3.2.2 新增 %1 道灵箓，获 %2 道行").replace("%1", str(len(preview['new_files']))).replace("%2", str(gained)))

        # ── 方式二：3.3.1+ 存档导入 ──
        save_dir = dialog.get_save_dir()
        if save_dir and self._validate_save_cb and self._absorb_save_cb:
            preview = self._validate_save_cb(save_dir)
            if preview is None:
                msgs.append(_translate("Form", "3.3.1+ 未找到有效道藏"))
            else:
                p = preview["preview"]
                ret = QMessageBox.question(
                    self, _translate("Form", "导入道藏"),
                    _translate("Form", "发现 %1 位道友，共 %2 道行，确认导入？").replace("%1", str(p["total_players"])).replace("%2", str(p["total_xp"])),
                    QMessageBox.Yes | QMessageBox.No
                )
                if ret == QMessageBox.Yes:
                    gained = self._absorb_save_cb(preview)
                    total_gained += gained
                    msgs.append(_translate("Form", "3.3.1+ 导入 %1 位道友，获 %2 道行").replace("%1", str(p["total_players"])).replace("%2", str(gained)))

        if not msgs:
            QMessageBox.information(self, _translate("Form", "提示"), _translate("Form", "请填写至少一种吸收方式"))
        else:
            QMessageBox.information(self, _translate("Form", "吸收灵气完成"), "\n".join(msgs))

    def _do_update(self, data: dict):
        rank = LEVEL_NAMES.get(data["level"], "")
        self._level_display.update_info(
            data.get("player_name", ""), rank, data["level"],
            data["total_xp"], data["xp_curr"], data["xp_need"]
        )
        idx = data["image_index"]
        self._level_display.set_image(self._assets.get(idx))

        history = data["history"]
        self._table.setRowCount(len(history))
        for i, h in enumerate(history):
            time_value = h["time"]
            if isinstance(time_value, (int, float)):
                time_value = datetime.fromtimestamp(int(time_value)).strftime("%Y-%m-%d %H:%M:%S")
            level_str = LEVEL_LABELS.get(h["level"], str(h["level"]))
            mode_str = MODE_LABELS.get(h["mode"], str(h["mode"]))
            for col, val in [(0, str(time_value)), (1, level_str), (2, mode_str),
                             (3, f'{h["rtime"]:.3f}'), (4, str(h["bbbv"])), (5, str(h["xp"]))]:
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(i, col, item)
