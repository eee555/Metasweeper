"""全局快捷键注册、持久化与应用。

所有界面快捷键都在此处登记；默认值与界面里显示的名字保持一致。
绑定以 ``gameSetting.ini`` 的 ``[KEYBINDINGS]`` 节保存，值为
``QKeySequence.toString()`` 形式（例如 ``Ctrl+Space``），空串表示禁用。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, Optional

from PySide6 import QtCore, QtGui


def _translate(context: str, text: str) -> str:
    """保留源文本供 lupdate 提取，实际翻译在界面创建时完成。"""
    return text


SECTION = "KEYBINDINGS"
WHEEL_MODIFIER_KEY = "board_wheel_modifier"
PROBABILITY_ID = "show_probability"


@dataclass(frozen=True)
class KeyBinding:
    """一条可自定义快捷键。"""

    id: str
    label: str
    default: str
    target: str            # shortcut / action
    attr: str              # Ui_MainWindow 上的对象属性名
    category: str          # game / menu
    platform: Optional[str] = None

    def available(self) -> bool:
        return self.platform is None or self.platform == sys.platform


# 棋盘与全局功能（superGUI 中构建的 QShortcut）
# 菜单项（ui_main_board 中构建的 QAction）
KEY_BINDINGS: tuple[KeyBinding, ...] = (
    KeyBinding("preset_beginner", _translate("KeyBindings", "初级局面 (1)"), "1", "shortcut", "frameShortcut1", "game"),
    KeyBinding("preset_intermediate", _translate("KeyBindings", "中级局面 (2)"), "2", "shortcut", "frameShortcut2", "game"),
    KeyBinding("preset_expert", _translate("KeyBindings", "高级局面 (3)"), "3", "shortcut", "frameShortcut3", "game"),
    KeyBinding("preset_4", _translate("KeyBindings", "自定义局面 4"), "4", "shortcut", "frameShortcut5", "game"),
    KeyBinding("preset_5", _translate("KeyBindings", "自定义局面 5"), "5", "shortcut", "frameShortcut6", "game"),
    KeyBinding("preset_6", _translate("KeyBindings", "自定义局面 6"), "6", "shortcut", "frameShortcut7", "game"),
    KeyBinding("restart", _translate("KeyBindings", "重新开始一局"), "F2", "shortcut", "frameShortcut4", "game"),
    KeyBinding("replay_current", _translate("KeyBindings", "回放当前局面"), "F3", "shortcut", "frameShortcutF3", "game"),
    KeyBinding(PROBABILITY_ID, _translate("KeyBindings", "显示每格雷的概率"), "Space", "shortcut", "frameShortcut8", "game"),
    KeyBinding("screen_shot", _translate("KeyBindings", "截屏识别概率 (OBR)"), "Ctrl+Space", "shortcut", "frameShortcut9", "game"),
    KeyBinding("screen_shot_mac", _translate("KeyBindings", "截屏识别概率 (macOS 备用)"), "Ctrl+Shift+A",
               "shortcut", "frameShortcut9_mac", "game", "darwin"),
    KeyBinding("toggle_counter", _translate("KeyBindings", "隐藏/显示计数器"), "/", "shortcut",
               "shortcut_hidden_score_board", "game"),
    KeyBinding("copy_board", _translate("KeyBindings", "复制局面"), "Ctrl+C", "shortcut", "shortcut_copy_board", "game"),
    KeyBinding("paste_board", _translate("KeyBindings", "粘贴局面"), "Ctrl+V", "shortcut", "shortcut_paste_board", "game"),

    KeyBinding("menu_new_game", _translate("KeyBindings", "菜单：新游戏"), "N", "action", "actionnew_game", "menu"),
    KeyBinding("menu_beginner", _translate("KeyBindings", "菜单：初级"), "B", "action", "actionchu_ji", "menu"),
    KeyBinding("menu_intermediate", _translate("KeyBindings", "菜单：中级"), "I", "action", "actionzhogn_ji", "menu"),
    KeyBinding("menu_expert", _translate("KeyBindings", "菜单：高级"), "E", "action", "actiongao_ji", "menu"),
    KeyBinding("menu_custom", _translate("KeyBindings", "菜单：自定义"), "C", "action", "actionzi_ding_yi", "menu"),
    KeyBinding("menu_quit", _translate("KeyBindings", "菜单：退出"), "Ctrl+X", "action", "actiontui_chu", "menu"),
    KeyBinding("menu_settings", _translate("KeyBindings", "菜单：游戏设置"), "S", "action", "actionyouxi_she_zhi", "menu"),
    KeyBinding("menu_about", _translate("KeyBindings", "菜单：关于"), "A", "action", "actiongaun_yv", "menu"),
    KeyBinding("menu_keybindings", _translate("KeyBindings", "菜单：快捷键设置"), "Z", "action", "action_kuaijiejian", "menu"),
    KeyBinding("menu_open", _translate("KeyBindings", "菜单：打开录像"), "O", "action", "actionopen", "menu"),
    KeyBinding("menu_mouse", _translate("KeyBindings", "菜单：鼠标设置"), "M", "action", "action_mouse", "menu"),
    KeyBinding("menu_save", _translate("KeyBindings", "菜单：保存录像"), "Ctrl+S", "action", "action_save", "menu"),
    KeyBinding("menu_replay", _translate("KeyBindings", "菜单：播放录像"), "R", "action", "action_replay", "menu"),
    KeyBinding("menu_open_replay", _translate("KeyBindings", "菜单：打开录像目录"), "W", "action", "action_open_replay", "menu"),
    KeyBinding("menu_achievements", _translate("KeyBindings", "菜单：成就"), "L", "action", "action_level", "menu"),
    KeyBinding("menu_records", _translate("KeyBindings", "菜单：个人记录"), "P", "action", "action_best", "menu"),
    KeyBinding("menu_plugins", _translate("KeyBindings", "菜单：插件管理"), "F1", "action", "actionchajian", "menu"),
)

WHEEL_MODIFIERS: tuple[tuple[str, QtCore.Qt.KeyboardModifier], ...] = (
    ("Ctrl", QtCore.Qt.KeyboardModifier.ControlModifier),
    ("Shift", QtCore.Qt.KeyboardModifier.ShiftModifier),
    ("Alt", QtCore.Qt.KeyboardModifier.AltModifier),
)


def available_bindings() -> tuple[KeyBinding, ...]:
    return tuple(binding for binding in KEY_BINDINGS if binding.available())


def default_values() -> Dict[str, str]:
    return {binding.id: binding.default for binding in available_bindings()}


def normalize(text: str) -> str:
    """把用户录入的按键转成规范字符串；空串表示禁用该快捷键。"""
    if not text:
        return ""
    return QtGui.QKeySequence(text).toString()


def load_bindings(game_setting) -> Dict[str, str]:
    values = default_values()
    for binding in available_bindings():
        stored = game_setting.value(f"{SECTION}/{binding.id}", None, str)
        if stored is not None:
            values[binding.id] = normalize(stored)
    return values


def save_bindings(game_setting, values: Dict[str, str]) -> None:
    for binding in available_bindings():
        game_setting.set_value(
            f"{SECTION}/{binding.id}", normalize(values.get(binding.id, "")))
    game_setting.set_value(
        f"{SECTION}/{WHEEL_MODIFIER_KEY}",
        values.get(WHEEL_MODIFIER_KEY, WHEEL_MODIFIERS[0][0]))
    game_setting.sync()


def apply_bindings(target, values: Dict[str, str]) -> None:
    """把绑定应用到主窗口上的 QShortcut 与 QAction。"""
    for binding in available_bindings():
        obj = getattr(target, binding.attr, None)
        if obj is None:
            continue
        sequence = QtGui.QKeySequence(values.get(binding.id, binding.default))
        if binding.target == "shortcut":
            obj.setKey(sequence)
            if binding.id == PROBABILITY_ID:
                obj.setAutoRepeat(False)
        elif binding.target == "action":
            obj.setShortcut(sequence)

    probability_key = values.get(PROBABILITY_ID, "Space")
    main_window = getattr(target, "mainWindow", None)
    if main_window is not None and hasattr(main_window, "set_probability_key"):
        main_window.set_probability_key(probability_key)


def wheel_modifier(game_setting) -> QtCore.Qt.KeyboardModifier:
    name = game_setting.value(
        f"{SECTION}/{WHEEL_MODIFIER_KEY}", WHEEL_MODIFIERS[0][0], str)
    for label, modifier in WHEEL_MODIFIERS:
        if label == name:
            return modifier
    return WHEEL_MODIFIERS[0][1]


def event_matches_sequence(event: QtGui.QKeyEvent,
                           sequence: QtGui.QKeySequence) -> bool:
    """判断一次按键释放是否匹配指定绑定（含修饰键）。"""
    if sequence.isEmpty():
        return False
    return QtGui.QKeySequence(
        event.key() | event.modifiers().value) == sequence


def find_conflicts(values: Dict[str, str]) -> dict[str, list[str]]:
    """返回重复绑定：按键字符串 -> 重复的显示名列表。"""
    grouped: dict[str, list[str]] = {}
    for binding in available_bindings():
        key = normalize(values.get(binding.id, ""))
        if not key:
            continue
        grouped.setdefault(key, []).append(binding.label)
    return {key: names for key, names in grouped.items() if len(names) > 1}
