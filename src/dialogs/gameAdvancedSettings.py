from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QCheckBox
from ui.ui_advanced import Ui_Form
from ui.uiComponents import RoundQDialog
from shared_types.commands import (
    COMMAND_TYPES, command_label, command_tag,
)

# 外观命令（换肤 / 音效）不是作弊开关：它们不改变局面、不影响官方录像，
# 授权由插件管理器的 ControlAuthorizationManager 独立管理。此前把它们列进
# allowed_controls，勾选后会让 any((board_constraint, _allowed_controls))
# 把第一击判成 JOKING，官方录像作废。
APPEARANCE_TAGS = frozenset({"set_skin", "set_sound"})


def _get_tag(cmd_type: type) -> str:
    return command_tag(cmd_type)


class ui_Form(Ui_Form):
    def __init__(self, mainWindow):
        self.game_setting = mainWindow.game_setting
        self.r_path = mainWindow.r_path
        self.filter_forever = mainWindow.filter_forever

        self.alter = False
        self._allowed_controls: set[str] = self._load_allowed_controls()

        self.Dialog = RoundQDialog(mainWindow.mainWindow)
        self.setupUi(self.Dialog)

        self.pushButton_yes.clicked.connect(self._on_accept)
        self.pushButton_no.clicked.connect(self.Dialog.close)
        self.label_info_text.linkActivated.connect(self._open_plugin_auth)

        self._build_allow_ui()
        self.setParameter()

    # ── 允许控制命令 ──────────────────────────────────

    def _load_allowed_controls(self) -> set[str]:
        raw = self.game_setting.value('DEFAULT/allowed_controls', '', str)
        tags = set(raw.split(',')) if raw else set()
        # 清理历史 ini 里残留的外观命令 tag，避免旧配置继续把局面判成 JOKING。
        return tags - APPEARANCE_TAGS

    def _save_allowed_controls(self) -> None:
        raw = ','.join(sorted(self._allowed_controls))
        self.game_setting.set_value('DEFAULT/allowed_controls', raw)

    def _build_allow_ui(self) -> None:
        # 命令类：外观命令不生成 checkbox（详见 APPEARANCE_TAGS 注释）。
        for cmd_type in COMMAND_TYPES:
            tag = _get_tag(cmd_type)
            if tag in APPEARANCE_TAGS:
                continue
            label = command_label(cmd_type)
            cb = QCheckBox()
            cb.setChecked(tag in self._allowed_controls)
            # Qt 翻译占位符用 %1，不能用 Python str.format 风格的 {label}：
            # 译者改写/省略词条时会残留字面量或丢掉命令名。
            cb.setText(QCoreApplication.translate(
                "Form", "允许 %1").arg(label))

            cb.stateChanged.connect(
                lambda checked, t=tag: self._on_allow_toggled(t, bool(checked))
            )
            self.verticalLayout_auth_items.addWidget(cb)

        # 事件类（与命令同等视为作弊）
        for tag in ("board_update",):
            cb = QCheckBox()
            cb.setChecked(tag in self._allowed_controls)
            cb.setText(QCoreApplication.translate(
                "Form", "允许 %1").arg(tag))

            cb.stateChanged.connect(
                lambda checked, t=tag: self._on_allow_toggled(t, bool(checked))
            )
            self.verticalLayout_auth_items.addWidget(cb)

    def _on_allow_toggled(self, tag: str, checked: bool) -> None:
        if tag in APPEARANCE_TAGS:
            return
        if checked:
            self._allowed_controls.add(tag)
        else:
            self._allowed_controls.discard(tag)

    def _open_plugin_auth(self) -> None:
        from shared_types.events import ShowPluginManagerEvent
        from plugin_sdk.server_bridge import GameServerBridge
        GameServerBridge.instance().send_event(ShowPluginManagerEvent())
        self.Dialog.close()

    # ── 基本参数 ────────────────────────────────────────

    def setParameter(self) -> None:
        self.checkBox_filter_forever.setChecked(self.filter_forever)

    def _on_accept(self) -> None:
        self.alter = True

        self.filter_forever = self.checkBox_filter_forever.isChecked()
        self.game_setting.set_value(
            "DEFAULT/filter_forever", self.filter_forever)
        self._save_allowed_controls()

        self.game_setting.sync()
        self.Dialog.close()
