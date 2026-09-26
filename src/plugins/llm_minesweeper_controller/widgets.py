"""
llm_minesweeper_controller - UI 组件
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton,
    QHBoxLayout, QGroupBox, QSplitter, QDialog, QTextBrowser,
    QDialogButtonBox,
)
from PySide6.QtCore import Signal, Slot, Qt, QCoreApplication
from PySide6.QtGui import QTextCursor

_translate = QCoreApplication.translate


class TutorialDialog(QDialog):
    """配置教程弹窗"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_translate("Form", "使用教程"))
        self.resize(640, 520)
        layout = QVBoxLayout(self)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet(
            "QTextBrowser { font-family: 'Microsoft YaHei', 'Segoe UI', Arial, sans-serif; "
            "font-size: 13px; background: #FEFEFE; padding: 12px; }"
        )
        browser.setHtml(self._build_content())
        layout.addWidget(browser)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)

    @staticmethod
    def _build_content() -> str:
        return _translate("Form", """\
<style>
h3 { color: #4CAF50; border-bottom: 2px solid #A5D6A7; padding-bottom: 4px; }
b { color: #2E7D32; }
code { background: #E8F5E9; padding: 1px 5px; border-radius: 3px; font-size: 12px; }
ol { margin: 4px 0; padding-left: 22px; }
ul { margin: 4px 0; }
li { margin: 6px 0; }
</style>

<h3>🔧 手把手配置教程</h3>
<ol>
<li><b>搞到 API Key</b><br>
打开 <a href='https://open.bigmodel.cn'>open.bigmodel.cn</a>（此处以智谱 AI 的免费小模型为例，你也可以用其他任意兼容 OpenAI 的 API）→ 点右上角「注册」→ 手机号或邮箱注册 → 登录后进控制台 → 左侧点「API Keys」→ 点「创建 API Key」→ 复制那串乱码</li>

<li><b>填进插件（通过界面修改，无需改文件）</b><br>
游戏菜单 →「插件管理器」→「插件列表」→ 找到「llm_minesweeper_controller」→ 右键点击 →「设置...」→ 在弹窗的「插件配置」区域填写：
<ul>
<li><b>API 密钥</b>：粘贴刚才复制的那串乱码</li>
<li><b>API 基础 URL</b>：<code>https://open.bigmodel.cn/api/paas/v4/</code></li>
<li><b>模型名称</b>：<code>glm-4-flash</code>（这里只是拿智谱举例，你可以换成其他任何模型）</li>
<li><b>深度思考</b>：选「关闭」（小模型不支持，否则会报错）</li>
</ul>
</li>

<li><b>测试能不能用</b><br>
回到本插件界面，点「🔗 测试连接」，日志区显示「连接成功」就说明配置对了</li>

<li><b>授权给插件</b><br>
插件管理器 →「控制授权」→ 把「新游戏」和「鼠标点击」都选上本插件 → 保存</li>

<li><b>勾选允许反控</b><br>
游戏菜单 →「高级设置」→ 把「允许鼠标点击」和「允许重新开局」勾上（不勾的话插件点不动格子）</li>

<li><b>开玩</b><br>
回到本插件界面，点「🤖 分析并操作」就开始自动扫雷了</li>
</ol>

<p style='color:#999; margin-top:16px;'>💡 <code>glm-4-flash</code> 是智谱 AI 的永久免费模型，128K 上下文，支持自动调用工具。用完赠送额度后仍然免费，只是速度会慢一些。</p>
""")


class LlmMinesweeperControllerWidget(QWidget):
    """插件 UI"""

    _log_signal = Signal(str)
    _chat_signal = Signal(str, str)  # role, text
    _status_signal = Signal(str)
    _enable_buttons_signal = Signal(bool)
    _summary_signal = Signal(str)
    _stop_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # 状态显示
        self._status_group = QGroupBox(_translate("Form", "状态"))
        status_layout = QHBoxLayout()
        self._status_label = QLabel(_translate("Form", "就绪"))
        self._status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self._status_label)
        self._status_group.setLayout(status_layout)
        layout.addWidget(self._status_group)

        # 上下文摘要 + 对话区（水平布局）
        main_splitter = QSplitter(Qt.Horizontal)

        # 上下文摘要（左侧）
        self._summary_text = QTextEdit()
        self._summary_text.setReadOnly(True)
        self._summary_text.setMaximumWidth(280)
        self._summary_text.setMinimumWidth(200)
        self._summary_text.setStyleSheet("""
            QTextEdit {
                font-family: Consolas, 'Microsoft YaHei', monospace;
                font-size: 11px;
                color: #0078d4;
                background-color: #f0f6ff;
            }
        """)

        # 对话显示区（右侧，宽）
        self._chat_text = QTextEdit()
        self._chat_text.setReadOnly(True)
        self._chat_text.setStyleSheet("""
            QTextEdit {
                font-family: Consolas, 'Microsoft YaHei', monospace;
                font-size: 13px;
            }
        """)

        main_splitter.addWidget(self._summary_text)
        main_splitter.addWidget(self._chat_text)
        main_splitter.setStretchFactor(0, 0)  # 摘要不拉伸
        main_splitter.setStretchFactor(1, 1)  # 对话拉伸

        layout.addWidget(main_splitter, stretch=1)

        # 日志显示区
        self._log_group = QGroupBox(_translate("Form", "日志"))
        log_layout = QVBoxLayout()
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(80)
        self._log_text.setStyleSheet("font-size: 11px; color: #666;")
        log_layout.addWidget(self._log_text)
        self._log_group.setLayout(log_layout)
        layout.addWidget(self._log_group)

        # 控制按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        def make_btn(text: str) -> QPushButton:
            btn = QPushButton(text)
            btn.setSizePolicy(
                btn.sizePolicy().horizontalPolicy(),
                btn.sizePolicy().verticalPolicy(),
            )
            btn.setStyleSheet(
                "QPushButton { padding: 5px 16px; font-size: 13px; }"
                "QPushButton:disabled { color: #999; }"
            )
            return btn

        self._analyze_button = make_btn(_translate("Form", "🤖 分析并操作"))
        self._stop_button = make_btn(_translate("Form", "⏹ 停止"))
        self._stop_button.setEnabled(False)
        self._test_button = make_btn(_translate("Form", "🔗 测试"))
        self._tutorial_button = make_btn(_translate("Form", "📖 教程"))
        self._clear_chat_button = make_btn(_translate("Form", "🗑 清除对话"))
        self._clear_log_button = make_btn(_translate("Form", "🗑 清除日志"))
        button_layout.addWidget(self._analyze_button)
        button_layout.addWidget(self._stop_button)
        button_layout.addWidget(self._test_button)
        button_layout.addWidget(self._tutorial_button)
        button_layout.addWidget(self._clear_chat_button)
        button_layout.addWidget(self._clear_log_button)
        layout.addLayout(button_layout)

        # 信号连接
        self._log_signal.connect(self._on_log)
        self._chat_signal.connect(self._on_chat)
        self._status_signal.connect(self._on_status)
        self._enable_buttons_signal.connect(self._on_enable_buttons)
        self._summary_signal.connect(self._on_summary)

        # 按钮事件
        self._clear_log_button.clicked.connect(self._clear_log)
        self._clear_chat_button.clicked.connect(self._clear_chat)
        self._tutorial_button.clicked.connect(self._show_tutorial)

    def retranslateUi(self):
        self._status_group.setTitle(_translate("Form", "状态"))
        self._log_group.setTitle(_translate("Form", "日志"))
        self._status_label.setText(_translate("Form", "就绪"))
        self._analyze_button.setText(_translate("Form", "🤖 分析并操作"))
        self._stop_button.setText(_translate("Form", "⏹ 停止"))
        self._test_button.setText(_translate("Form", "🔗 测试"))
        self._tutorial_button.setText(_translate("Form", "📖 教程"))
        self._clear_chat_button.setText(_translate("Form", "🗑 清除对话"))
        self._clear_log_button.setText(_translate("Form", "🗑 清除日志"))

    @Slot(str)
    def _on_log(self, text: str) -> None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_text.append(f"[{timestamp}] {text}")

    @Slot(str, str)
    def _on_chat(self, role: str, text: str) -> None:
        color_map = {
            "system": "#2196F3",
            "assistant": "#4CAF50",
            "tool": "#FF9800",
            "user": "#9C27B0",
            "error": "#F44336",
        }
        color = color_map.get(role, "#333")
        self._chat_text.append(
            f'<span style="color:{color}; font-weight:bold;">[{role}]</span> '
            f'{text}'
        )
        # 滚动到底部
        scrollbar = self._chat_text.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    @Slot(str)
    def _on_status(self, text: str) -> None:
        self._status_label.setText(text)

    @Slot(bool)
    def _on_enable_buttons(self, enabled: bool) -> None:
        self._analyze_button.setEnabled(enabled)
        self._test_button.setEnabled(enabled)
        self._stop_button.setEnabled(not enabled)  # 停止按钮与主按钮相反

    def _on_stop_clicked(self) -> None:
        """停止按钮点击处理"""
        self._stop_signal.emit()

    def _show_tutorial(self) -> None:
        dialog = TutorialDialog(self)
        dialog.exec()

    def _clear_log(self) -> None:
        self._log_text.clear()

    def _clear_chat(self) -> None:
        self._chat_text.clear()

    @Slot(str)
    def _on_summary(self, text: str) -> None:
        """更新上下文摘要显示"""
        self._summary_text.setPlainText(text)
        # 滚动到顶部
        self._summary_text.moveCursor(QTextCursor.MoveOperation.Start)

    # ── 线程安全的公开方法（由插件调用） ──

    @Slot(str)
    def log_message(self, text: str) -> None:
        self._log_signal.emit(text)

    @Slot(str, str)
    def add_chat_message(self, role: str, text: str) -> None:
        self._chat_signal.emit(role, text)

    def update_status(self, text: str) -> None:
        self._status_signal.emit(text)

    def set_buttons_enabled(self, enabled: bool) -> None:
        self._enable_buttons_signal.emit(enabled)

    @Slot(str)
    def update_summary(self, text: str) -> None:
        self._summary_signal.emit(text)

    def set_analyze_callback(self, callback) -> None:
        self._analyze_button.clicked.connect(callback)

    def set_test_button_callback(self, callback) -> None:
        self._test_button.clicked.connect(callback)

    def set_stop_button_callback(self, callback) -> None:
        self._stop_button.clicked.connect(callback)
