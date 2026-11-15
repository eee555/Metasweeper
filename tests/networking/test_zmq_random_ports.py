"""ZMQ 服务端全随机端口 + 命令行显式端点联动的回归测试。

「全随机」指 PUB / ROUTER 各自独立向系统申请空闲端口，不再要求二者连续，
也不再伪造一个可供 +1/+2 派生的基准端点。主进程把两个真实端点通过命令行
参数传给插件管理器，客户端必须直接使用这些显式端点连接。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

from app import plugin_process
from lib_zmq_plugins.client.zmq_client import ZMQClient
from lib_zmq_plugins.server.zmq_server import ZMQServer
from shared_types.queries import (
    BoardStateResult,
    GetBoardStateQuery,
    QUERY_RESULT_TYPES,
    QUERY_TYPES,
)


def _port(endpoint: str) -> int:
    return int(endpoint.rsplit(":", 1)[1])


def test_server_binds_independent_random_ports_and_client_connects():
    server = ZMQServer("tcp://127.0.0.1", bind_to_random_port=True)
    server.register_query_types(*QUERY_TYPES)
    server.register_query_result_types(*QUERY_RESULT_TYPES)
    server.register_query_handler(
        GetBoardStateQuery,
        lambda q: BoardStateResult(
            request_id=q.request_id, cells=[[10, 11]], rows=1, cols=2,
            mines_remaining=1, game_time=2.5, game_status="playing",
            game_status_code=2))
    server.start()
    try:
        pub, ctrl = server.pub_endpoint, server.ctrl_endpoint

        # 两个端口都由系统分配、互不相同，且不是默认固定端口
        assert _port(pub) != _port(ctrl)
        assert _port(pub) not in (5556, 5557)
        assert _port(ctrl) not in (5556, 5557)

        # 全随机模式不会把 endpoint 回写成带端口的伪基准
        assert server.endpoint == "tcp://127.0.0.1"

        # 客户端显式传入真实端点。若错误回退到 base+1/base+2 派生
        # （base 无端口 -> 5556/5557），下面的查询会超时。
        client = ZMQClient(
            server.endpoint,
            pub_endpoint=pub,
            ctrl_endpoint=ctrl,
        )
        client.register_query_types(
            *QUERY_TYPES, result_types=tuple(QUERY_RESULT_TYPES))
        client.connect()
        try:
            result = client.query(GetBoardStateQuery(), timeout=5.0)
            assert isinstance(result, BoardStateResult)
            assert result.success and result.cells == [[10, 11]]
        finally:
            client.disconnect()
    finally:
        server.stop()


def test_start_plugin_process_passes_real_endpoints_on_command_line(monkeypatch, tmp_path):
    """主进程启动插件管理器时，命令行必须带上真实 PUB/CTRL 端点。"""
    fake_bridge = SimpleNamespace(
        endpoint="tcp://127.0.0.1",
        pub_endpoint="tcp://127.0.0.1:23456",
        ctrl_endpoint="tcp://127.0.0.1:23457",
    )
    # 用假的 sys 跳过 Windows 互斥体检测，同时保留 sys.executable
    monkeypatch.setattr(
        plugin_process, "sys",
        SimpleNamespace(platform="linux", executable=sys.executable))
    monkeypatch.setattr(
        plugin_process.GameServerBridge, "instance", lambda: fake_bridge)
    monkeypatch.setattr(plugin_process, "get_runtime_mode", lambda: "source")
    monkeypatch.setattr(plugin_process, "get_env_for_subprocess", lambda: dict(os.environ))

    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return SimpleNamespace(poll=lambda: None, terminate=lambda: None)

    monkeypatch.setattr(plugin_process.subprocess, "Popen", fake_popen)

    ui = SimpleNamespace(setting_path=Path(tmp_path))
    plugin_process.start_plugin_process(ui, None, plugins_disabled=False)

    cmd = captured["cmd"]
    assert cmd[0] == sys.executable and cmd[1:3] == ["-m", "plugin_manager"]
    for flag, value in (
        ("--endpoint", fake_bridge.endpoint),
        ("--pub-endpoint", fake_bridge.pub_endpoint),
        ("--ctrl-endpoint", fake_bridge.ctrl_endpoint),
    ):
        assert flag in cmd
        assert cmd[cmd.index(flag) + 1] == value
