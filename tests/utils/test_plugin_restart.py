import subprocess
from types import SimpleNamespace

from app import plugin_process


def test_restart_reuses_endpoint_and_data_dir_and_cleans_up_latest(monkeypatch, tmp_path):
    calls = []
    bridge = SimpleNamespace(endpoint='base', pub_endpoint='pub', ctrl_endpoint='ctrl',
                             stop=lambda: calls.append('bridge-stop'))
    monkeypatch.setattr(plugin_process.GameServerBridge, 'instance', lambda: bridge)
    monkeypatch.setattr(plugin_process, 'sys', SimpleNamespace(platform='linux', executable='python'))
    monkeypatch.setattr(plugin_process, 'get_runtime_mode', lambda: 'source')
    monkeypatch.setattr(plugin_process, 'get_env_for_subprocess', lambda: {})

    class Process:
        def __init__(self, number):
            self.number = number
            self.running = True

        def poll(self):
            return None if self.running else 0

        def terminate(self):
            calls.append(('terminate', self.number))
            self.running = False

        def wait(self, timeout):
            calls.append(('wait', self.number))

    commands = []
    def popen(cmd, **kwargs):
        commands.append((cmd, kwargs))
        calls.append(('start', len(commands)))
        return Process(len(commands))

    monkeypatch.setattr(plugin_process.subprocess, 'Popen', popen)
    ui = SimpleNamespace(setting_path=tmp_path, _plugin_process=None)
    ui._plugin_process = plugin_process.start_plugin_process(ui, None, False)
    assert plugin_process.restart_plugin_process(ui, None, False)
    assert commands[0] == commands[1]
    assert commands[1][0][commands[1][0].index('--data-dir') + 1] == str(tmp_path / 'data')
    assert calls == [('start', 1), ('terminate', 1), ('wait', 1), ('start', 2)]
    plugin_process.cleanup_plugin_process(ui._plugin_process)
    assert calls[-3:] == ['bridge-stop', ('terminate', 2), ('wait', 2)]


def test_restart_skips_windows_mutex_check_for_managed_process(monkeypatch, tmp_path):
    from types import SimpleNamespace
    bridge = SimpleNamespace(endpoint='base', pub_endpoint='pub', ctrl_endpoint='ctrl')
    monkeypatch.setattr(plugin_process.GameServerBridge, 'instance', lambda: bridge)
    monkeypatch.setattr(plugin_process, 'sys', SimpleNamespace(platform='win32', executable='python'))
    monkeypatch.setattr(plugin_process, 'get_runtime_mode', lambda: 'source')
    monkeypatch.setattr(plugin_process, 'get_env_for_subprocess', lambda: {})
    mutex_calls = []
    monkeypatch.setattr(plugin_process, '_plugin_manager_is_running',
                        lambda: mutex_calls.append('checked') or False)
    started = []
    monkeypatch.setattr(plugin_process.subprocess, 'Popen',
                        lambda *args, **kwargs: started.append(args) or object())
    process = SimpleNamespace(poll=lambda: 0)
    ui = SimpleNamespace(setting_path=tmp_path, _plugin_process=process)

    assert plugin_process.restart_plugin_process(ui, None, False)
    assert len(started) == 1
    assert mutex_calls == ['checked', 'checked']


def test_restart_action_appears_next_to_open_and_triggers_restart(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMainWindow, QMenu

    window = QMainWindow()
    qtbot.addWidget(window)
    menu = QMenu(window)
    open_action = menu.addAction('插件')
    ui = SimpleNamespace(menu_4=menu, actionchajian=open_action)
    calls = []
    monkeypatch.setattr(plugin_process, 'restart_plugin_process',
                        lambda *args: calls.append(args))
    action = plugin_process.install_restart_action(ui, window, False)
    assert menu.actions() == [action, open_action]
    action.trigger()
    assert calls == [(ui, window, False)]


def test_restart_waits_for_old_mutex_to_be_released(monkeypatch):
    from types import SimpleNamespace
    process = SimpleNamespace(poll=lambda: 0)
    ui = SimpleNamespace(_plugin_process=process)
    checks = iter([True, True, False])
    sleeps = []
    replacement = object()
    monkeypatch.setattr(plugin_process, '_plugin_manager_is_running', lambda: next(checks))
    monkeypatch.setattr(plugin_process.time, 'sleep', lambda delay: sleeps.append(delay))
    monkeypatch.setattr(plugin_process, 'start_plugin_process', lambda *args: replacement)

    assert plugin_process.restart_plugin_process(ui, None, False)
    assert ui._plugin_process is replacement
    assert sleeps == [0.1, 0.1]


def test_restart_does_not_start_if_process_cannot_be_stopped(monkeypatch):
    class StuckProcess:
        def poll(self):
            return None

        def terminate(self):
            pass

        def kill(self):
            pass

        def wait(self, timeout):
            raise subprocess.TimeoutExpired('plugin_manager', timeout)

    process = StuckProcess()
    ui = SimpleNamespace(_plugin_process=process)
    monkeypatch.setattr(plugin_process, 'start_plugin_process',
                        lambda *args: (_ for _ in ()).throw(AssertionError('started')))
    assert not plugin_process.restart_plugin_process(ui, None, False)
    assert ui._plugin_process is process
    assert not plugin_process.restart_plugin_process(ui, None, True)
    assert ui._plugin_process is process
