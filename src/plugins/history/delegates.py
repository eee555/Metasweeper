"""
表格代理组件
"""

from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import Qt, QModelIndex
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import (
    QComboBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QDateTimeEdit,
    QStyledItemDelegate,
    QStyle,
    QApplication,
)

from shared_types.widgets import EditableComboBox

from .models import HistoryData, CompareSymbol


class ComboBoxDelegate(QStyledItemDelegate):
    """通用的 ComboBox 代理"""

    def __init__(self, items: list[str], parent=None):
        super().__init__(parent)
        self._items = items

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItems(self._items)
        return editor

    def setEditorData(self, editor: QComboBox, index):
        value = index.model().data(index, Qt.EditRole)
        if value:
            idx = editor.findText(value)
            if idx >= 0:
                editor.setCurrentIndex(idx)

    def setModelData(self, editor: QComboBox, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class EditableComboBoxDelegate(QStyledItemDelegate):
    """可编辑的 ComboBox 代理（带补全）"""

    def __init__(self, items: list[str], parent=None):
        super().__init__(parent)
        self._items = items

    def createEditor(self, parent, option, index):
        editor = EditableComboBox(self._items, parent)
        return editor

    def setEditorData(self, editor: EditableComboBox, index):
        value = index.model().data(index, Qt.EditRole)
        if value:
            editor.setCurrentText(value)

    def setModelData(self, editor: EditableComboBox, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class FilterValueDelegate(QStyledItemDelegate):
    """值列的智能代理，根据同行字段类型动态决定编辑器"""

    COL_FIELD = 1  # FilterModel.COL_FIELD
    COL_COMPARE = 2  # FilterModel.COL_COMPARE

    def __init__(self, float_decimals: int = 2, parent=None):
        super().__init__(parent)
        self._float_decimals = float_decimals
        self._editor_widgets = []  # 缓存创建的编辑器widget

    def paint(self, painter, option, index):
        """根据字段类型绘制单元格"""
        # 检查选中状态
        is_selected = option.state & QStyle.State_Selected

        if is_selected:  # type: ignore
            # 选中时绘制背景
            painter.fillRect(option.rect, option.palette.highlight())
            # 使用高亮文本颜色
            text_role = QPalette.HighlightedText
        else:
            text_role = QPalette.WindowText

        field_value, _, _ = self._get_field_info(index)
        raw_value = index.data(Qt.EditRole)

        if field_value is None or raw_value is None:
            super().paint(painter, option, index)
            return

        display_text = str(raw_value)

        if isinstance(field_value, datetime):
            # 日期类型显示为可读格式
            try:
                ts = int(raw_value)
                if ts > 1e15:  # 微秒
                    ts = ts / 1_000_000
                elif ts > 1e12:  # 毫秒
                    ts = ts / 1_000
                dt = datetime.fromtimestamp(ts)
                display_text = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError, OSError):
                display_text = raw_value
        elif isinstance(field_value, float):
            # 浮点数显示带小数位
            try:
                display_text = f"{float(raw_value):.{self._float_decimals}f}"
            except (ValueError, TypeError):
                display_text = raw_value

        # 使用 QStyle 绘制文本
        style = QApplication.style()
        style.drawItemText(
            painter,
            option.rect,
            Qt.AlignCenter | Qt.AlignVCenter,  # type: ignore
            option.palette,
            True,
            display_text,
            text_role
        )

    def _get_field_info(self, index: QModelIndex) -> tuple:
        """获取同行的字段信息和比较符"""
        model = index.model()
        row = index.row()

        # 获取字段名
        field_index = model.index(row, self.COL_FIELD)
        field_name = model.data(field_index, Qt.EditRole)

        # 获取比较符
        compare_index = model.index(row, self.COL_COMPARE)
        compare_text = model.data(compare_index, Qt.EditRole)

        if not field_name:
            return None, None, None

        try:
            field_value = HistoryData.get_field_value(field_name)
        except (KeyError, IndexError):
            return None, None, None

        compare = None
        if compare_text:
            try:
                compare = CompareSymbol.from_display_name(compare_text)
            except ValueError:
                pass

        return field_value, compare, field_name

    def _create_editor_by_type(self, parent, field_value, compare, field_name):
        """根据字段类型创建编辑器"""
        from shared_types.enums import BaseDiaPlayEnum

        # 如果是包含/不包含比较符，使用 LineEdit
        if compare.value in (CompareSymbol.Contains, CompareSymbol.NotContains):
            return QLineEdit(parent)

        if isinstance(field_value, BaseDiaPlayEnum):
            editor = QComboBox(parent)
            editor.addItems([e.display_name for e in field_value.__class__])
            return editor
        elif isinstance(field_value, int):
            return QSpinBox(parent)
        elif isinstance(field_value, float):
            editor = QDoubleSpinBox(parent)
            editor.setDecimals(self._float_decimals)
            editor.setRange(-1e15, 1e15)
            return editor
        elif isinstance(field_value, datetime):
            editor = QDateTimeEdit(parent)
            editor.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            editor.setCalendarPopup(True)
            return editor
        else:
            return QLineEdit(parent)

    def createEditor(self, parent, option, index):
        field_value, compare, field_name = self._get_field_info(index)
        if field_value is None:
            return QLineEdit(parent)
        return self._create_editor_by_type(parent, field_value, compare, field_name)

    def setEditorData(self, editor, index):
        field_value, compare, field_name = self._get_field_info(index)
        if field_value is None:
            return

        raw_value = index.model().data(index, Qt.EditRole)

        from shared_types.enums import BaseDiaPlayEnum
        if isinstance(field_value, BaseDiaPlayEnum) and isinstance(editor, QComboBox):
            if raw_value:
                idx = editor.findText(raw_value)
                if idx >= 0:
                    editor.setCurrentIndex(idx)
        elif isinstance(field_value, int) and isinstance(editor, QSpinBox):
            try:
                editor.setValue(int(raw_value) if raw_value else 0)
            except (ValueError, TypeError):
                editor.setValue(0)
        elif isinstance(field_value, float) and isinstance(editor, QDoubleSpinBox):
            try:
                editor.setValue(float(raw_value) if raw_value else 0.0)
            except (ValueError, TypeError):
                editor.setValue(0.0)
        elif isinstance(field_value, datetime) and isinstance(editor, QDateTimeEdit):
            try:
                if raw_value:
                    # raw_value 可能是 int/float 时间戳，或字符串形式的时间戳
                    if isinstance(raw_value, (int, float)):
                        dt = datetime.fromtimestamp(raw_value / 1_000_000)
                    else:
                        # 先尝试作为字符串时间戳解析
                        try:
                            ts = int(raw_value)
                            if ts > 1e15:  # 微秒
                                ts = ts / 1_000_000
                            elif ts > 1e12:  # 毫秒
                                ts = ts / 1_000
                            dt = datetime.fromtimestamp(ts)
                        except (ValueError, TypeError):
                            # 再尝试解析日期时间字符串
                            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                                try:
                                    dt = datetime.strptime(raw_value, fmt)
                                    break
                                except ValueError:
                                    continue
                            else:
                                dt = datetime.now()
                else:
                    dt = datetime.now()
                editor.setDateTime(dt)
            except (ValueError, TypeError):
                editor.setDateTime(datetime.now())
        else:
            if isinstance(editor, QLineEdit):
                editor.setText(raw_value or "")

    def setModelData(self, editor, model, index):
        field_value, compare, field_name = self._get_field_info(index)
        if field_value is None:
            if isinstance(editor, QLineEdit):
                model.setData(index, editor.text(), Qt.EditRole)
            return

        from shared_types.enums import BaseDiaPlayEnum
        if isinstance(field_value, BaseDiaPlayEnum) and isinstance(editor, QComboBox):
            model.setData(index, editor.currentText(), Qt.EditRole)
        elif isinstance(field_value, (int, float)) and isinstance(editor, (QSpinBox, QDoubleSpinBox)):
            model.setData(index, str(editor.value()), Qt.EditRole)
        elif isinstance(field_value, datetime) and isinstance(editor, QDateTimeEdit):
            ts = int(editor.dateTime().toPyDateTime().timestamp() * 1_000_000)
            model.setData(index, str(ts), Qt.EditRole)
        else:
            if isinstance(editor, QLineEdit):
                model.setData(index, editor.text(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)
