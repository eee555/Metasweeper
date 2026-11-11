"""插件详情对话框（只读展示）

展示插件的两类信息：
- 订阅的事件（来自 EventDispatcher 的订阅注册表）
- 权限（来自 plugin.info.required_controls 声明，
  结合 ControlAuthorizationManager 授权记录标注授予状态）
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLayout,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from plugin_sdk.control_auth import ControlAuthorizationManager
from shared_types import EVENT_TYPES
from shared_types.commands import (
    COMMAND_HINTS, COMMAND_LABELS, COMMANDS_I18N_CONTEXT,
    command_hint, command_label,
)
from shared_types.widgets import ConfirmDialog

from .icons import action_icon, set_button_box_icons

if TYPE_CHECKING:
    from plugin_sdk.plugin_base import BasePlugin


_translate = QCoreApplication.translate


def _get_struct_tag(cls) -> str | None:
    """读取 msgspec Struct 类的 tag 字符串"""
    cfg = getattr(cls, "__struct_config__", None)
    tag = getattr(cfg, "tag", None)
    if tag is None:
        return None
    return str(tag)


def _build_tag_name_map(classes) -> dict[str, str]:
    """构建 tag -> 类名 映射（用于展示友好名称）"""
    result = {}
    for cls in classes:
        tag = _get_struct_tag(cls)
        if tag:
            result[tag] = cls.__name__
    return result


# tag -> 类名（事件与命令共用同一 msgspec tag 机制）
_EVENT_TAG_NAMES = _build_tag_name_map(EVENT_TYPES)


class PluginInfoDialog(ConfirmDialog):
    """插件详情对话框（只读）"""

    def __init__(self, plugin: BasePlugin, parent=None):
        # 基类 __init__ 期间会调用 _create_content()，需先持有插件引用
        self._plugin = plugin
        title = QCoreApplication.translate(
            "PluginInfoDialog", "插件详情 - {name}").format(name=plugin.name)
        super().__init__(parent, title=title, buttons=QDialogButtonBox.Close)
        self.setWindowIcon(action_icon("app"))
        set_button_box_icons(self.button_box)
        self.setMinimumSize(560, 540)

        self._load_data()

    # ── UI ─────────────────────────────────────────────

    def _create_content(self) -> QLayout:
        root = QVBoxLayout()

        # 基本信息
        info = self._plugin.info
        basic_box = QGroupBox(self.tr("基本信息"))
        form = QFormLayout(basic_box)
        form.addRow(self.tr("名称"), QLabel(info.name))
        form.addRow(self.tr("版本"), QLabel(info.version))
        form.addRow(self.tr("作者"), QLabel(info.author or "-"))

        desc_label = QLabel(info.description or self.tr("暂无描述"))
        desc_label.setWordWrap(True)
        form.addRow(self.tr("描述"), desc_label)
        root.addWidget(basic_box)

        # 两类信息：订阅事件 / 权限（声明 + 授权状态）
        self._events_list, events_box = self._make_list_group(
            self.tr("订阅的事件"))
        self._permission_list, permission_box = self._make_list_group(
            self.tr("权限"))
        root.addWidget(events_box)
        root.addWidget(permission_box)

        return root

    def _make_list_group(
        self, title: str
    ) -> tuple[QListWidget, QGroupBox]:
        """创建分组框 + 只读列表"""
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        lst = QListWidget()
        lst.setEditTriggers(QListWidget.NoEditTriggers)
        lst.setSelectionMode(QListWidget.NoSelection)
        lst.setMaximumHeight(120)
        lay.addWidget(lst)
        return lst, box

    def _add_items(self, lst: QListWidget, texts: list[str]) -> None:
        """填充列表；空列表显示灰色占位「无」"""
        if not texts:
            item = QListWidgetItem(self.tr("无"))
            item.setForeground(QColor("#9e9e9e"))
            lst.addItem(item)
            return
        for text in texts:
            lst.addItem(QListWidgetItem(text))

    # ── 数据 ───────────────────────────────────────────

    def _load_data(self) -> None:
        # 1. 订阅的事件
        tags = self._collect_subscribed_events()
        self._add_items(self._events_list, [
            self._display_tag(tag, _EVENT_TAG_NAMES) for tag in tags
        ])

        # 2. 权限：声明 + 授权记录 并集，逐项标注授予状态
        declared = self._plugin.info.required_controls or []
        authorized_tags: set[str] = set(self._collect_authorized_tags())
        self._add_permission_items(
            self._permission_list, declared, authorized_tags)

    def _collect_subscribed_events(self) -> list[str]:
        """从 EventDispatcher 的订阅注册表收集该插件订阅的事件 tag（只读快照）"""
        dispatcher = getattr(self._plugin, "_event_dispatcher", None)
        if dispatcher is None:
            return []
        tags: set[str] = set()
        try:
            with dispatcher._lock:
                for tag, entries in dispatcher._handlers.items():
                    if any(entry.plugin is self._plugin for entry in entries):
                        tags.add(str(tag))
        except Exception:
            pass
        return sorted(tags)

    def _collect_authorized_tags(self) -> list[str]:
        """收集该插件已被授予的控制命令 tag"""
        try:
            auth = ControlAuthorizationManager.instance()
            return sorted(
                str(tag)
                for tag, plugin_name in auth._authorizations.items()
                if plugin_name == self._plugin.name
            )
        except Exception:
            return []

    def _display_tag(self, tag: str, name_map: dict[str, str]) -> str:
        """tag 优先显示为「类名 (tag)」，未知 tag 直接显示"""
        cls_name = name_map.get(tag)
        return f"{cls_name} ({tag})" if cls_name else tag

    def _add_permission_items(
        self,
        lst: QListWidget,
        declared: list,
        authorized_tags: set[str],
    ) -> None:
        """填充权限列表：声明权限与授权记录取并集，逐项标注授予状态。

        已授予/未授予项使用同套确认/取消图标与文字；未授予项另以灰色区分。
        每项 tooltip 给出一句话说明与类名，避免只剩英文类名看不出用途。
        """
        items = self._permission_texts(declared, authorized_tags)
        if not items:
            item = QListWidgetItem(self.tr("无"))
            item.setForeground(QColor("#9e9e9e"))
            lst.addItem(item)
            return
        for text, granted, hint in items:
            icon_name = "confirm" if granted else "cancel"
            item = QListWidgetItem(
                QIcon(action_icon(icon_name)),
                f"{text} {self.tr('已授予')}" if granted
                else f"{text} {self.tr('未授予')}"
            )
            if hint:
                item.setToolTip(hint)
            if not granted:
                item.setForeground(QColor("#9e9e9e"))
            lst.addItem(item)

    def _permission_texts(
        self, declared: list, authorized_tags: set[str]
    ) -> list[tuple[str, bool, str]]:
        """返回 [(显示文本, 是否已授予, tooltip)]，声明与授权记录取并集"""
        result: list[tuple[str, bool, str]] = []
        shown: set[str] = set()
        for cls in declared:
            tag = _get_struct_tag(cls)          # 真 tag 或 None
            label = command_label(cls)
            text = f"{label} ({tag})" if tag else label
            tooltip = (f"{label}\n{command_hint(cls)}\n"
                       f"类名: {getattr(cls, '__name__', cls)}")
            result.append((text, bool(tag) and tag in authorized_tags,
                           tooltip))
            shown.add(tag if tag else label)
        # 已授权但未在声明中的命令，直接以中文名补充展示
        for tag in sorted(authorized_tags):
            if tag not in shown:
                label_src = COMMAND_LABELS.get(tag)
                hint_src = COMMAND_HINTS.get(tag)
                if label_src is not None:
                    label = _translate(COMMANDS_I18N_CONTEXT, label_src)
                else:
                    label = tag
                hint = (_translate(COMMANDS_I18N_CONTEXT, hint_src)
                        if hint_src else "")
                tooltip = f"{label}\n{hint}" if hint else label
                text = label if label == tag else f"{label} ({tag})"
                result.append((text, True, tooltip))
                shown.add(tag)
        return result
