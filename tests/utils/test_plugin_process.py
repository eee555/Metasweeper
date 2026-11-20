import subprocess
from types import SimpleNamespace

from app import plugin_process


def test_start_passes_endpoints_and_data_dir_and_cleanup_stops_child(monkeypatch, tmp_path):
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
    ui = SimpleNamespace(setting_path=tmp_path)
    process = plugin_process.start_plugin_process(ui, None, False)
    command, _ = commands[0]
    assert command[command.index('--data-dir') + 1] == str(tmp_path / 'data')
    assert command[command.index('--endpoint') + 1] == 'base'
    assert command[command.index('--pub-endpoint') + 1] == 'pub'
    assert command[command.index('--ctrl-endpoint') + 1] == 'ctrl'
    assert plugin_process.cleanup_plugin_process(process)
    assert calls == [('start', 1), 'bridge-stop', ('terminate', 1), ('wait', 1)]


def test_start_does_not_duplicate_running_manager(monkeypatch, tmp_path):
    monkeypatch.setattr(plugin_process, 'sys', SimpleNamespace(platform='win32', executable='python'))
    mutex_calls = []
    monkeypatch.setattr(plugin_process, '_plugin_manager_is_running',
                        lambda: mutex_calls.append('checked') or True)
    started = []
    monkeypatch.setattr(plugin_process.subprocess, 'Popen',
                        lambda *args, **kwargs: started.append(args) or object())
    ui = SimpleNamespace(setting_path=tmp_path)
    assert plugin_process.start_plugin_process(ui, None, False) is None
    assert started == []
    assert mutex_calls == ['checked']


def test_cleanup_reports_process_that_cannot_be_stopped(monkeypatch):
    class StuckProcess:
        def poll(self):
            return None

        def terminate(self):
            pass

        def kill(self):
            pass

        def wait(self, timeout):
            raise subprocess.TimeoutExpired('plugin_manager', timeout)

    bridge = SimpleNamespace(stop=lambda: None)
    monkeypatch.setattr(plugin_process.GameServerBridge, 'instance', lambda: bridge)
    assert not plugin_process.cleanup_plugin_process(StuckProcess())
