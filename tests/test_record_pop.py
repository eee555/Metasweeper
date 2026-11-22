from PySide6.QtCore import Qt

from dialogs import gameRecordPop


def test_record_pop_is_application_modal(qtbot):
    popup = gameRecordPop.ui_Form([], 3, [], None)
    qtbot.addWidget(popup.Dialog)

    assert popup.Dialog.isModal()
    assert popup.Dialog.windowModality() == Qt.WindowModality.ApplicationModal
