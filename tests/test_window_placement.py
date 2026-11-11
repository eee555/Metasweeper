"""分离窗口（计数器、录像控制台）位置放置与屏幕钳制测试。

场景：用户上次在扩展屏使用面板，本次切到单显示器启动时，
记忆位置整体落在屏幕外；无边框面板抓不到，会不可见也移不动。
"""
import pytest
from PySide6.QtWidgets import QApplication, QWidget

from utils.helpers import clamp_widget_to_screen, place_detached_panel


@pytest.fixture
def screen_rect():
    return QApplication.primaryScreen().availableGeometry()


def _make_panel(qtbot, width=200, height=400):
    panel = QWidget()
    panel.resize(width, height)
    qtbot.addWidget(panel)
    return panel


def test_clamp_pulls_offscreen_widget_back(qtbot):
    # 模拟记忆位置留在已断开的扩展屏上（远超屏幕右边界）。
    # 断言以 widget 自己的屏幕为准（多显示器环境下 widget.screen() 可能
    # 归属外接屏，位置在该屏内则本就不越界；环境无关）
    panel = _make_panel(qtbot)
    avail = panel.screen().availableGeometry()
    panel.move(avail.right() + 800, 100)
    clamp_widget_to_screen(panel)
    assert avail.contains(panel.geometry())


def test_clamp_pulls_below_bottom_back(qtbot, screen_rect):
    panel = _make_panel(qtbot)
    panel.move(screen_rect.left() + 50, screen_rect.bottom() + 600)
    clamp_widget_to_screen(panel)
    assert screen_rect.contains(panel.geometry())


def test_clamp_keeps_valid_position_untouched(qtbot, screen_rect):
    panel = _make_panel(qtbot)
    x = screen_rect.left() + 60
    y = screen_rect.top() + 70
    panel.move(x, y)
    clamp_widget_to_screen(panel)
    assert (panel.x(), panel.y()) == (x, y)


def test_first_launch_attaches_left_of_anchor(qtbot, screen_rect):
    # 首次启动（无记忆位置）：贴合主窗口左侧、顶边对齐
    anchor = QWidget()
    anchor.resize(400, 300)
    qtbot.addWidget(anchor)
    anchor.move(screen_rect.left() + 100, screen_rect.top() + 100)
    panel = _make_panel(qtbot)

    pos = place_detached_panel(panel, anchor)
    assert pos == panel.pos()
    # 面板右缘贴住主窗口左缘；因左侧空间不足被钳制到屏幕左缘
    assert panel.x() == screen_rect.left()
    assert panel.y() == anchor.y()
    assert screen_rect.contains(panel.geometry())


def test_first_launch_with_room_keeps_exact_left_attach(qtbot, screen_rect):
    anchor = QWidget()
    anchor.resize(200, 200)
    qtbot.addWidget(anchor)
    anchor.move(screen_rect.left() + 500, screen_rect.top() + 50)
    panel = _make_panel(qtbot, width=200, height=100)

    place_detached_panel(panel, anchor)
    assert panel.x() == anchor.x() - panel.width()
    assert panel.y() == anchor.y()


def test_saved_offscreen_position_is_clamped(qtbot, screen_rect):
    # 有记忆位置但整体在屏幕外：恢复后必须钳制回主窗口所在屏幕
    anchor = QWidget()
    qtbot.addWidget(anchor)
    anchor.move(screen_rect.left() + 200, screen_rect.top() + 200)
    panel = _make_panel(qtbot)

    place_detached_panel(panel, anchor,
                         screen_rect.right() + 900, screen_rect.top() + 10)
    # 生产路径按主窗口所在屏钳制（place_detached_panel 传 anchor.screen()），
    # 断言同样以该屏为准，环境无关
    assert anchor.screen().availableGeometry().contains(panel.geometry())


def test_saved_position_partly_on_screen_is_kept(qtbot, screen_rect):
    # 面板部分在屏幕内（能抓到边缘拖动）：原样保留，不强行吸回屏幕
    anchor = QWidget()
    qtbot.addWidget(anchor)
    anchor.move(screen_rect.left() + 200, screen_rect.top() + 200)
    panel = _make_panel(qtbot, width=200, height=100)

    saved_x = screen_rect.right() - 100  # 一半在屏内
    saved_y = screen_rect.top() + 20
    place_detached_panel(panel, anchor, saved_x, saved_y)
    assert (panel.x(), panel.y()) == (saved_x, saved_y)


def test_saved_position_on_second_screen_is_kept(qtbot, screen_rect):
    # 双屏环境（offscreen 平台提供多个虚拟屏）：落在任一屏幕内的记忆位置
    # 不被强行拉回主屏
    screens = QApplication.screens()
    if len(screens) < 2:
        pytest.skip("需要多屏幕环境")
    other = screens[1]
    other_avail = other.availableGeometry()
    anchor = QWidget()
    qtbot.addWidget(anchor)
    anchor.move(screen_rect.left() + 200, screen_rect.top() + 200)
    panel = _make_panel(qtbot)

    saved_x = other_avail.left() + 30
    saved_y = other_avail.top() + 30
    place_detached_panel(panel, anchor, saved_x, saved_y)
    assert (panel.x(), panel.y()) == (saved_x, saved_y)
