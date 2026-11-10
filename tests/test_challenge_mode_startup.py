"""无猜闯关插件启动回归测试。"""
import pytest
from loguru import logger
from PySide6.QtWidgets import QApplication


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(
        "plugin_manager.logging_setup.get_plugin_logger",
        lambda *args, **kwargs: (logger, None),
    )
    return QApplication.instance() or QApplication([])


def test_create_widget_before_on_initialized(app):
    """_create_widget 由 initialize 同步调用，早于 on_initialized 设置状态。

    回归：曾因读取未初始化的 self._auto_next 抛 AttributeError，
    基类回滚并禁用插件，导致「无猜闯关」无法启动。
    """
    from plugins.challenge_mode.plugin import ChallengeModePlugin

    plugin = ChallengeModePlugin(ChallengeModePlugin.plugin_info())
    widget = plugin._create_widget()
    try:
        assert widget is not None
        assert plugin._auto_next is False
    finally:
        widget.deleteLater()
