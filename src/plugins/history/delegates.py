"""
表格代理组件
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QModelIndex, QPersistentModelIndex
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QComboBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QDateTimeEdit,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QApplication,
)

from shared_types.widgets import EditableComboBox

from .models import HistoryData, CompareSymbol
from .computed_column import ComputedColumn


class ComboBoxDelegate(QStyledItemDelegate):
    """通用的 ComboBox 代理"""

    def __init__(self, items: list[str], parent=None):
        super().__init__(parent)
        self._items = items
        self._editor_indexes = []  # 缓存创建的编辑器索引

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItems(self._items)
        self._editor_indexes.append(index)
        return editor

    def destroyEditor(self, editor, index):
        if index in self._editor_indexes:
            self._editor_indexes.remove(index)
        return super().destroyEditor(editor, index)

    def paint(self, painter, option, index):
        if index in self._editor_indexes:
            return
        return super().paint(painter, option, index)

    def setEditorData(self, editor: QComboBox, index):
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        if value:
            idx = editor.findText(value)
            if idx >= 0:
                editor.setCurrentIndex(idx)

    def setModelData(self, editor: QComboBox, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class EditableComboBoxDelegate(QStyledItemDelegate):
    """可编辑的 ComboBox 代理（带补全）"""

    def __init__(self, items: list[str], parent=None):
        super().__init__(parent)
        self._items = items
        self._editor_indexes = []  # 缓存创建的编辑器索引

    def createEditor(self, parent, option, index):
        editor = EditableComboBox(self._items, parent)
        self._editor_indexes.append(index)
        return editor

    def setEditorData(self, editor: EditableComboBox, index):
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        if value:
            editor.setCurrentText(value)

    def paint(self, painter, option, index):
        if index in self._editor_indexes:
            return
        return super().paint(painter, option, index)

    def destroyEditor(self, editor, index):
        self._editor_indexes.remove(index)
        return super().destroyEditor(editor, index)

    def setModelData(self, editor: EditableComboBox, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class FilterValueDelegate(QStyledItemDelegate):
    """值列的智能代理，根据同行字段类型动态决定编辑器"""

    COL_FIELD = 1  # FilterModel.COL_FIELD
    COL_COMPARE = 2  # FilterModel.COL_COMPARE

    def __init__(self, float_decimals: int = 2, computed_columns: list[ComputedColumn] | None = None, parent=None):
        super().__init__(parent)
        self._float_decimals = float_decimals
        self._computed_columns = computed_columns or []
        self._editor_widgets = []  # 缓存创建的编辑器widget
        self._editor_indexes = []  # 缓存创建的编辑器索引

    def paint(self, painter, option, index):
        """根据字段类型绘制单元格"""
        if index in self._editor_indexes:
            return

        # 检查选中状态
        is_selected = option.state & QStyle.StateFlag.State_Selected

        if is_selected:  # type: ignore
            # 选中时绘制背景
            painter.fillRect(option.rect, option.palette.highlight())
            # 使用高亮文本颜色
            text_role = QPalette.ColorRole.HighlightedText
        else:
            text_role = QPalette.ColorRole.WindowText

        field_value, _, _ = self._get_field_info(index)
        raw_value = index.data(Qt.ItemDataRole.EditRole)

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
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter,
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
        field_name = model.data(field_index, Qt.ItemDataRole.EditRole)

        # 获取比较符
        compare_index = model.index(row, self.COL_COMPARE)
        compare_text = model.data(compare_index, Qt.ItemDataRole.EditRole)

        if not field_name:
            return None, None, None

        # 先尝试物理字段
        field_value = HistoryData.get_field_value(field_name)
        if field_value is None:
            # 再尝试计算列（用类型样本值区分 int / float / string）
            for col in self._computed_columns:
                if col.name == field_name:
                    field_value = col.sample_value
                    break

        if field_value is None:
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
        # 模糊匹配输入的是子串，必须用 LineEdit：数值/枚举/日期控件都输不出子串
        if compare is not None and compare.value in (
                CompareSymbol.Like, CompareSymbol.NotLike):
            return QLineEdit(parent)

        editor = None
        if isinstance(field_value, BaseDiaPlayEnum):
            editor = QComboBox(parent)
            editor.addItems([e.display_name for e in field_value.__class__])
        elif isinstance(field_value, int):
            editor = QSpinBox(parent)
            editor.setRange(-2147483648, 2147483647)
        elif isinstance(field_value, float):
            editor = QDoubleSpinBox(parent)
            editor.setDecimals(self._float_decimals)
            editor.setRange(-1e15, 1e15)
        elif isinstance(field_value, datetime):
            editor = QDateTimeEdit(parent)
            editor.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            editor.setCalendarPopup(True)
        else:
            editor = QLineEdit(parent)
        return editor

    def createEditor(self, parent, option, index):
        field_value, compare, field_name = self._get_field_info(index)
        if field_value is None:
            editor = QLineEdit(parent)
        else:
            editor = self._create_editor_by_type(
                parent, field_value, compare, field_name)
        editor.setAutoFillBackground(True)
        self._editor_indexes.append(index)
        return editor

    def destroyEditor(self, editor, index):
        if index in self._editor_indexes:
            self._editor_indexes.remove(index)
        return super().destroyEditor(editor, index)

    def setEditorData(self, editor, index):
        field_value, compare, field_name = self._get_field_info(index)
        if field_value is None:
            return

        raw_value = index.model().data(index, Qt.ItemDataRole.EditRole)

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
                model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)
            return

        from shared_types.enums import BaseDiaPlayEnum
        if isinstance(field_value, BaseDiaPlayEnum) and isinstance(editor, QComboBox):
            model.setData(index, editor.currentText(),
                          Qt.ItemDataRole.EditRole)
        elif isinstance(field_value, (int, float)) and isinstance(editor, (QSpinBox, QDoubleSpinBox)):
            model.setData(index, str(editor.value()), Qt.ItemDataRole.EditRole)
        elif isinstance(field_value, datetime) and isinstance(editor, QDateTimeEdit):
            ts = int(editor.dateTime().toPython().timestamp() * 1_000_000)
            model.setData(index, str(ts), Qt.ItemDataRole.EditRole)
        else:
            if isinstance(editor, QLineEdit):
                model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)
