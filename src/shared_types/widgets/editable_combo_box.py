"""
可编辑的组合框控件

支持补全但不允许新增，焦点移开后验证输入
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter


class EditableComboBox(QComboBox):
    """可编辑的组合框，支持补全但不允许新增，焦点移开后验证输入"""

    def __init__(
        self,
        items: list[str],
        parent=None,
        default_index: int = 0,
        case_sensitive: bool = False,
        filter_mode: str = "contains",
    ):
        """
        Args:
            items: 下拉选项列表
            parent: 父控件
            default_index: 默认选中的索引
            case_sensitive: 补全时是否大小写敏感
            filter_mode: 补全过滤模式，"contains" 包含匹配，"startswith" 前缀匹配
        """
        super().__init__(parent)
        self._items = list(items)
        self._default_index = default_index

        self.setEditable(True)
        self.addItems(items)
        if items and 0 <= default_index < len(items):
            self.setCurrentIndex(default_index)

        # 设置补全器
        completer = QCompleter(items, self)
        completer.setCaseSensitivity(
            Qt.CaseSensitive if case_sensitive else Qt.CaseInsensitive
        )
        completer.setFilterMode(
            Qt.MatchStartsWith if filter_mode == "startswith" else Qt.MatchContains
        )
        completer.setCompletionMode(QCompleter.PopupCompletion)  # 改为弹出式，更高效
        self.setCompleter(completer)

        # 焦点移开时验证输入
        self.lineEdit().editingFinished.connect(self._validate_input)

    def _validate_input(self):
        """验证输入，如果不在有效列表中则恢复默认值"""
        current_text = self.currentText()
        if current_text not in self._items:
            # 恢复为默认值
            if self._items:
                self.setCurrentIndex(self._default_index)
            else:
                self.setCurrentText("")

    def setItems(self, items: list[str]):
        """动态更新选项列表"""
        old_text = self.currentText()
        self._items = list(items)
        self.clear()
        self.addItems(items)
        # 尝试恢复之前的选中项
        if old_text in items:
            self.setCurrentText(old_text)
        elif items and 0 <= self._default_index < len(items):
            self.setCurrentIndex(self._default_index)

    def currentData(self) -> str:
        """返回当前选中的值（始终返回有效值）"""
        return self.currentText()
