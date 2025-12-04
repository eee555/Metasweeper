from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QListWidget,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QMessageBox,
    QScrollArea,
    QWidget,
    QLineEdit,
    QDoubleSpinBox,
    QCheckBox,
    QComboBox,
)
from PyQt5.QtCore import Qt
import sys
from typing import Dict
from mp_plugins import PluginContext

# 你的 Setting 类
from mp_plugins.base import (
    BaseSetting,
    TextSetting,
    NumberSetting,
    BoolSetting,
    SelectSetting,
)
from mp_plugins import PluginManager


class PluginManagerUI(QDialog):

    def __init__(self, plugin_contexts: list[PluginContext]):
        """
        plugin_contexts: 你传入的 plugin 列表
        get_settings_func(plugin_ctx) -> Dict[str, BaseSetting]
            你自己的函数，用来根据 PluginContext 拿到 settings
        """
        super().__init__()

        self.plugin_contexts = plugin_contexts
        self.current_settings_widgets: Dict[str, QWidget] = {}

        self.setWindowTitle("插件管理")
        self.resize(1000, 650)

        root_layout = QHBoxLayout(self)

        # ================= 左侧插件列表 =================
        self.list_widget = QListWidget()
        for ctx in self.plugin_contexts:
            self.list_widget.addItem(ctx.display_name or ctx.name)

        self.list_widget.currentRowChanged.connect(self.on_plugin_selected)
        root_layout.addWidget(self.list_widget, 1)

        # ================= 右侧 =================
        right_layout = QVBoxLayout()

        # -------- 插件详情 --------
        details_group = QGroupBox("插件详情")
        self.details_layout = QFormLayout()

        self.detail_labels = {
            "pid": QLabel(),
            "name": QLabel(),
            "display_name": QLabel(),
            "description": QLabel(),
            "version": QLabel(),
            "author": QLabel(),
            "author_email": QLabel(),
            "url": QLabel(),
            "status": QLabel(),
            "heartbeat": QLabel(),
            "subscribers": QLabel(),
        }

        for key, widget in self.detail_labels.items():
            self.details_layout.addRow(key.replace("_", " ").title() + ":", widget)

        details_group.setLayout(self.details_layout)
        right_layout.addWidget(details_group, 1)

        # -------- 设置面板（滚动） --------
        settings_group = QGroupBox("设置")
        vbox = QVBoxLayout()

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.scroll_content = QWidget()
        self.scroll_layout = QFormLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)

        vbox.addWidget(self.scroll_area, 1)

        # 保存按钮
        self.btn_save = QPushButton("保存")
        self.btn_save.clicked.connect(self.on_save_clicked)
        vbox.addWidget(self.btn_save)

        settings_group.setLayout(vbox)
        right_layout.addWidget(settings_group, 2)

        root_layout.addLayout(right_layout, 2)

        if plugin_contexts:
            self.list_widget.setCurrentRow(0)

    # ===================================================================
    # 左侧切换插件
    # ===================================================================
    def on_plugin_selected(self, index: int):
        if index < 0:
            return

        ctx = self.plugin_contexts[index]

        # --- PluginContext 原样填充 ---
        for key, label in self.detail_labels.items():
            value = getattr(ctx, key)
            if isinstance(value, list):
                value = ", ".join(value)
            label.setText(str(value))

        # --- 你自己的获取 settings 的函数 ---
        settings_dict = PluginManager.instance().Get_Settings(ctx.name)

        # --- 动态加载设置控件 ---
        self.load_settings(settings_dict)

    # ===================================================================
    # 加载 settings
    # ===================================================================
    def load_settings(self, settings: Dict[str, BaseSetting]):
        # 清空原控件
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.current_settings_widgets.clear()

        for key, setting in settings.items():
            widget = None

            if isinstance(setting, TextSetting):
                widget = QLineEdit()
                widget.setText(setting.value)

            elif isinstance(setting, NumberSetting):
                widget = QDoubleSpinBox()
                widget.setRange(setting.min_value, setting.max_value)
                widget.setSingleStep(setting.step)
                widget.setValue(setting.value)

            elif isinstance(setting, BoolSetting):
                widget = QCheckBox(setting.description)
                widget.setChecked(setting.value)

            elif isinstance(setting, SelectSetting):
                widget = QComboBox()
                widget.addItems(setting.options)
                widget.setCurrentText(setting.value)

            else:
                continue

            self.current_settings_widgets[key] = widget
            self.scroll_layout.addRow(setting.name + ":", widget)

    # ===================================================================
    # 保存按钮
    # ===================================================================
    def on_save_clicked(self):
        ctx = self.plugin_contexts[self.list_widget.currentRow()]

        # --- PluginContext 原样填充 ---
        for key, label in self.detail_labels.items():
            value = getattr(ctx, key)
            if isinstance(value, list):
                value = ", ".join(value)
            label.setText(str(value))

        # --- 你自己的获取 settings 的函数 ---
        settings_dict = PluginManager.instance().Get_Settings(ctx.name)
        for key, widget in self.current_settings_widgets.items():
            setting = settings_dict[key]
            if isinstance(widget, QLineEdit) and isinstance(setting, TextSetting):
                setting.value = widget.text()
            elif isinstance(widget, QDoubleSpinBox) and isinstance(
                setting, NumberSetting
            ):
                setting.value = widget.value()
            elif isinstance(widget, QCheckBox) and isinstance(setting, BoolSetting):
                setting.value = widget.isChecked()
            elif isinstance(widget, QComboBox) and isinstance(setting, SelectSetting):
                setting.value = widget.currentText()
            PluginManager.instance().Set_Settings(ctx.name, key, setting)
        QMessageBox.information(self, "保存成功", "设置已保存")
