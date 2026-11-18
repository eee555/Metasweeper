from PySide6 import QtCore, QtGui

from dialogs.keyBindingsEditor import _ShortcutEdit
from mainWindowGUI import MainWindow


def test_shortcut_edit_preserves_comma_keys(qtbot):
    edit = _ShortcutEdit()
    qtbot.addWidget(edit)

    for text in (",", "Ctrl+,"):
        edit.setKeySequence(QtGui.QKeySequence(text))
        assert edit.keySequence().toString() == text


def test_probability_shortcut_release_survives_modifier_released_first(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.set_probability_key("Ctrl+A")
    released = []
    window.keyRelease.connect(released.append)

    event = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyRelease,
        QtCore.Qt.Key.Key_A,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    window.keyReleaseEvent(event)

    assert released == ["Space"]
