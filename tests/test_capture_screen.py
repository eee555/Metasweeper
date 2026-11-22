from PySide6.QtGui import QImage, QPixmap

import captureScreen
from captureScreen import CaptureScreen


def test_get_board_reads_qimage_memoryview(qtbot, monkeypatch):
    monkeypatch.setattr(CaptureScreen, "captureFullScreen", lambda self: None)
    capture = CaptureScreen()
    qtbot.addWidget(capture)
    image = QImage(3, 2, QImage.Format.Format_ARGB32)
    image.fill(0xFF112233)
    capture.captureImage = QPixmap.fromImage(image)
    expected_size = capture.captureImage.toImage().sizeInBytes()
    received = {}

    def fake_obr_board(data, height, width):
        received.update(data=data, height=height, width=width)
        return [[0]]

    monkeypatch.setattr(captureScreen.ms_toollib, "obr_board", fake_obr_board)
    capture.getBoard()

    assert len(received["data"]) == expected_size
    assert received["height"] == 2
    assert received["width"] == 3
    assert capture.board == [[0]]
    assert capture.success_flag
